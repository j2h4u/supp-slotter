#!/usr/bin/env bash
set -euo pipefail

# Run one canonical test/type command in a bounded, serialized cgroup.

declare -r DEFAULT_MEMORY_HIGH='900M'
declare -r DEFAULT_MEMORY_MAX='1G'
declare -r DEFAULT_MEMORY_SWAP_MAX='0'
declare -r MARKER_VARIABLE='SUPP_SLOTTER_BOUNDED_RUNNER'
declare -r UNIT_VARIABLE='SUPP_SLOTTER_BOUNDED_UNIT'

function die {
    local -r message="${1:-}"
    local -ri code="${2:-1}"

    echo "FATAL: ${message}" 1>&2
    exit "$code"
}

function usage {
    cat <<'EOF'
Usage: scripts/run_bounded.sh [OPTIONS] -- COMMAND [ARGUMENT ...]

Run COMMAND in a systemd user service with a per-checkout lock and cgroup
limits. Explicit overrides apply to this invocation only.

Options:
  --memory-high SIZE       MemoryHigh (default: 900M)
  --memory-max SIZE        MemoryMax (default: 1G)
  --memory-swap-max SIZE   MemorySwapMax (default: 0)
  --print-config           Print the effective properties and exit
  -h, --help               Show this help

Environment overrides (CLI options take precedence):
  SUPP_SLOTTER_MEMORY_HIGH, SUPP_SLOTTER_MEMORY_MAX,
  SUPP_SLOTTER_MEMORY_SWAP_MAX
EOF
}

# shellcheck disable=SC2034
function parse_size {
    local -r value="$1"
    local -n result_ref="$2"
    local number suffix multiplier base bytes

    # assert: a size is a decimal integer with a supported binary suffix
    if [[ ! "$value" =~ ^([0-9]+)([KMGTP]i?B?|B)?$ ]]; then
        return 1
    fi
    number="${BASH_REMATCH[1]}"
    suffix="${BASH_REMATCH[2]:-B}"

    # assert: arithmetic stays inside Bash's signed 64-bit range
    if (( ${#number} > 18 )); then
        return 1
    fi
    base=$(( 10#${number} ))
    case "$suffix" in
        B) multiplier=1 ;;
        K|KB|KiB) multiplier=1024 ;;
        M|MB|MiB) multiplier=$(( 1024 ** 2 )) ;;
        G|GB|GiB) multiplier=$(( 1024 ** 3 )) ;;
        T|TB|TiB) multiplier=$(( 1024 ** 4 )) ;;
        P|PB|PiB) multiplier=$(( 1024 ** 5 )) ;;
        *) return 1 ;;
    esac
    # assert: multiplication cannot overflow the signed 64-bit byte count
    if (( base > 9223372036854775807 / multiplier )); then
        return 1
    fi
    bytes=$(( base * multiplier ))
    result_ref="$bytes"
}

function check_limits {
    local -r high="$1"
    local -r maximum="$2"
    local -r swap_max="$3"
    local high_bytes max_bytes swap_bytes

    parse_size "$high" high_bytes || die "invalid SUPP_SLOTTER_MEMORY_HIGH/--memory-high size: $high"
    parse_size "$maximum" max_bytes || die "invalid SUPP_SLOTTER_MEMORY_MAX/--memory-max size: $maximum"
    parse_size "$swap_max" swap_bytes || die "invalid SUPP_SLOTTER_MEMORY_SWAP_MAX/--memory-swap-max size: $swap_max"

    # assert: a bounded service has positive memory limits and no swap escape
    (( high_bytes > 0 )) || die "MemoryHigh must be greater than zero: $high"
    (( max_bytes > 0 )) || die "MemoryMax must be greater than zero: $maximum"
    (( swap_bytes == 0 )) || die "MemorySwapMax must remain 0 (swap is not an allowed escape): $swap_max"
    # assert: MemoryHigh cannot exceed MemoryMax
    (( high_bytes <= max_bytes )) || die "MemoryHigh must not exceed MemoryMax: $high > $maximum"
}

function cgroup_path {
    local relative_path

    relative_path=$(awk -F: '$1 == "0" { print $3; exit }' /proc/self/cgroup)
    [[ -n "$relative_path" ]] || return 1
    printf '/sys/fs/cgroup%s\n' "$relative_path"
}

function in_bounded_cgroup {
    local -r expected_marker="$1"
    local -r expected_unit="$2"
    local -r expected_high="$3"
    local -r expected_max="$4"
    local -r expected_swap_max="$5"
    local root relative_path unit high maximum swap_max
    local high_bytes max_bytes swap_bytes

    relative_path=$(awk -F: '$1 == "0" { print $3; exit }' /proc/self/cgroup) || return 1
    [[ -n "$relative_path" ]] || return 1
    unit=$(basename -- "$relative_path")
    # The cgroup path must prove that this process is in the exact transient
    # service created by this runner, and the marker must be bound to its name.
    [[ "$expected_marker" =~ ^[[:xdigit:]]{32}$ ]] || return 1
    [[ "$expected_unit" == "supp-slotter-bounded-${expected_marker}" ]] || return 1
    [[ "$unit" == "${expected_unit}.service" ]] || return 1
    root="/sys/fs/cgroup${relative_path}"
    [[ -r "$root/memory.high" && -r "$root/memory.max" && -r "$root/memory.swap.max" ]] || return 1
    high=$(<"$root/memory.high")
    maximum=$(<"$root/memory.max")
    swap_max=$(<"$root/memory.swap.max")

    parse_size "$expected_high" high_bytes || return 1
    parse_size "$expected_max" max_bytes || return 1
    parse_size "$expected_swap_max" swap_bytes || return 1
    # assert: nested calls retain this runner's exact finite limits and no swap escape
    [[ "$high" == "$high_bytes" && "$maximum" == "$max_bytes" && "$swap_max" == "$swap_bytes" ]]
}

function new_marker_token {
    local token

    token=$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')
    [[ "$token" =~ ^[[:xdigit:]]{32}$ ]] || die "could not generate a bounded-runner identity token"
    printf '%s\n' "$token"
}

function check_prerequisites {
    # assert: cgroup v2 is mounted, so systemd properties cover descendants
    [[ "$(stat -fc %T /sys/fs/cgroup 2>/dev/null)" == cgroup2fs ]] || die "cgroup v2 is unavailable at /sys/fs/cgroup; refusing an unbounded run"
    command -v systemctl >/dev/null 2>&1 || die "systemctl is unavailable; refusing an unbounded run"
    command -v systemd-run >/dev/null 2>&1 || die "systemd-run is unavailable; refusing an unbounded run"
    command -v flock >/dev/null 2>&1 || die "flock is unavailable; refusing an unserialized run"
    # assert: the systemd user manager is reachable.  `is-system-running` is
    # intentionally not used here: a manager may report `degraded` while still
    # being fully capable of owning and collecting this transient service.
    systemctl --user show-environment >/dev/null 2>&1 || die "systemd user manager is unavailable; start it before running bounded gates"
}

function worktree_lock_path {
    local -r root="$1"
    local digest runtime_dir

    digest=$(printf '%s' "$root" | sha256sum | awk '{ print $1 }')
    [[ -n "$digest" ]] || die "could not derive a worktree-specific lock name"
    runtime_dir="${XDG_RUNTIME_DIR:-/tmp}"
    printf '%s/supp-slotter-bounded-%s.lock\n' "$runtime_dir" "$digest"
}

# shellcheck disable=SC2034
function parse_args {
    local -n high_ref="$1"
    local -n max_ref="$2"
    local -n swap_ref="$3"
    local -n print_ref="$4"
    local -n command_ref="$5"
    shift 5
    local option value

    while (( $# > 0 )); do
        option="$1"
        case "$option" in
            --memory-high|--memory-max|--memory-swap-max)
                (( $# >= 2 )) || die "missing value for $option"
                value="$2"
                shift 2
                case "$option" in
                    --memory-high) high_ref="$value" ;;
                    --memory-max) max_ref="$value" ;;
                    --memory-swap-max) swap_ref="$value" ;;
                esac
                ;;
            --memory-high=* ) high_ref="${option#*=}"; shift ;;
            --memory-max=* ) max_ref="${option#*=}"; shift ;;
            --memory-swap-max=* ) swap_ref="${option#*=}"; shift ;;
            --print-config) print_ref=1; shift ;;
            -h|--help) usage; exit 0 ;;
            --) shift; command_ref=("$@"); return ;;
            *) die "unknown option: $option (put the command after --)" ;;
        esac
    done
}

function main {
    local memory_high memory_max memory_swap_max
    local -i print_config=0
    local -a command=()
    local repo_root lock_path flock_path marker_token unit_name path_value
    local client_pid
    local -i runner_active=0 runner_status=0

    memory_high="${SUPP_SLOTTER_MEMORY_HIGH:-$DEFAULT_MEMORY_HIGH}"
    memory_max="${SUPP_SLOTTER_MEMORY_MAX:-$DEFAULT_MEMORY_MAX}"
    memory_swap_max="${SUPP_SLOTTER_MEMORY_SWAP_MAX:-$DEFAULT_MEMORY_SWAP_MAX}"
    parse_args memory_high memory_max memory_swap_max print_config command "$@"
    check_limits "$memory_high" "$memory_max" "$memory_swap_max"

    if (( print_config )); then
        printf 'MemoryHigh=%s\nMemoryMax=%s\nMemorySwapMax=%s\n' "$memory_high" "$memory_max" "$memory_swap_max"
        return 0
    fi
    ((${#command[@]} > 0)) || die "no command supplied; use -- COMMAND [ARGUMENT ...]"

    # Nested invocation stays inside the already bounded service and lock.  A
    # caller-controlled marker alone is never sufficient: the cgroup path and
    # all effective limits must match the exact transient unit identity.
    if [[ -n "${!MARKER_VARIABLE:-}" || -n "${!UNIT_VARIABLE:-}" ]]; then
        [[ -n "${!MARKER_VARIABLE:-}" && -n "${!UNIT_VARIABLE:-}" ]] || die "incomplete bounded-runner identity; refusing an unbounded run"
        in_bounded_cgroup "${!MARKER_VARIABLE}" "${!UNIT_VARIABLE}" "$memory_high" "$memory_max" "$memory_swap_max" || die "bounded-runner identity or effective cgroup limits do not match; refusing an unbounded run"
        exec "${command[@]}"
    fi

    check_prerequisites
    repo_root=$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null) || die "not inside a git checkout; cannot serialize the bounded gate"
    lock_path=$(worktree_lock_path "$repo_root")
    flock_path=$(command -v flock) || die "flock is unavailable; refusing to run the gate"
    path_value="$PATH"
    marker_token=$(new_marker_token)
    unit_name="supp-slotter-bounded-${marker_token}"

    function stop_runner_unit {
        (( runner_active )) || return 0
        # systemd-run may have been interrupted while the service survived.
        # Stop synchronously and wait until the complete transient unit is gone
        # so its service-held lock cannot be released behind our back.
        systemctl --user stop "$unit_name" >/dev/null 2>&1 || true
        while systemctl --user is-active --quiet "$unit_name"; do
            sleep 0.05
        done
        if [[ -n "${client_pid:-}" ]]; then
            wait "$client_pid" 2>/dev/null || true
            client_pid=''
        fi
        runner_active=0
    }

    function handle_runner_signal {
        local -r signal="$1"
        local -i code

        case "$signal" in
            HUP) code=129 ;;
            INT) code=130 ;;
            QUIT) code=131 ;;
            TERM) code=143 ;;
            *) code=1 ;;
        esac
        stop_runner_unit
        exit "$code"
    }

    trap 'handle_runner_signal HUP' HUP
    trap 'handle_runner_signal INT' INT
    trap 'handle_runner_signal QUIT' QUIT
    trap 'handle_runner_signal TERM' TERM
    trap stop_runner_unit EXIT
    runner_active=1

    # The service itself owns the checkout lock for the entire command
    # lifetime. This remains serialized even if the systemd-run client dies.
    # --wait/--collect normally waits for and unloads the service; signal traps
    # above synchronously stop it if the client is interrupted.
    systemd-run --user --unit="$unit_name" --wait --collect --quiet --pipe --expand-environment=no \
        --working-directory="$PWD" \
        -p "MemoryHigh=$memory_high" \
        -p "MemoryMax=$memory_max" \
        -p "MemorySwapMax=$memory_swap_max" \
        --setenv="${MARKER_VARIABLE}=${marker_token}" \
        --setenv="${UNIT_VARIABLE}=${unit_name}" \
        --setenv="SUPP_SLOTTER_MEMORY_HIGH=${memory_high}" \
        --setenv="SUPP_SLOTTER_MEMORY_MAX=${memory_max}" \
        --setenv="SUPP_SLOTTER_MEMORY_SWAP_MAX=${memory_swap_max}" \
        --setenv="PATH=${path_value}" \
        -- "$flock_path" --exclusive "$lock_path" "${command[@]}" &
    client_pid=$!
    wait "$client_pid" || runner_status=$?
    client_pid=''
    stop_runner_unit
    trap - EXIT
    return "$runner_status"
}

main "$@"
