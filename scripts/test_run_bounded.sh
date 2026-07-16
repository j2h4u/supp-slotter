#!/usr/bin/env bash
set -euo pipefail

declare TEMP_DIR=''

function die {
    local -r message="${1:-}"

    echo "FATAL: ${message}" 1>&2
    exit 1
}

function cleanup {
    exec 9>&- || true
    if [[ -n "$TEMP_DIR" ]]; then
        rm -rf -- "$TEMP_DIR"
    fi
}

function assert_equal {
    local -r expected="$1"
    local -r actual="$2"
    local -r description="$3"

    # assert: the probe produced its expected result
    [[ "$actual" == "$expected" ]] || die "${description}: expected ${expected@Q}, got ${actual@Q}"
}

function main {
    local -r script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
    local -r repo_root="$(cd -- "$script_dir/.." && pwd -P)"
    local -r runner="$script_dir/run_bounded.sh"
    local config_output stdout_output stderr_output lock_output
    local cgroup_output unit_output interrupt_output interrupt_unit_output
    local interrupt_hold_fifo interrupt_competing_output
    local status unit_name first_pid second_pid lock_value load_state

    cd "$repo_root"
    TEMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/supp-slotter-bounded-test.XXXXXX")
    trap cleanup EXIT
    config_output="$TEMP_DIR/config"
    stdout_output="$TEMP_DIR/stdout"
    stderr_output="$TEMP_DIR/stderr"
    lock_output="$TEMP_DIR/lock"
    cgroup_output="$TEMP_DIR/cgroup"
    unit_output="$TEMP_DIR/unit"
    interrupt_output="$TEMP_DIR/interrupt"
    interrupt_unit_output="$TEMP_DIR/interrupt-unit"
    interrupt_hold_fifo="$TEMP_DIR/interrupt-hold"
    interrupt_competing_output="$TEMP_DIR/interrupt-competing"

    # assert: defaults are visible without starting a service
    "$runner" --print-config >"$config_output"
    assert_equal $'MemoryHigh=450M\nMemoryMax=500M\nMemorySwapMax=0' "$(<"$config_output")" "default properties"

    # assert: malformed and inverted overrides fail closed
    if "$runner" --memory-high nope --print-config >/dev/null 2>&1; then
        die "malformed size was accepted"
    fi
    if "$runner" --memory-high 700M --memory-max 650M --print-config >/dev/null 2>&1; then
        die "MemoryHigh > MemoryMax was accepted"
    fi

    # assert: child status and both output streams are preserved
    if "$runner" -- bash -c 'printf stdout; printf stderr >&2; exit 23' >"$stdout_output" 2>"$stderr_output"; then
        status=0
    else
        status=$?
    fi
    assert_equal '23' "$status" "child exit status"
    assert_equal 'stdout' "$(<"$stdout_output")" "child stdout"
    assert_equal 'stderr' "$(<"$stderr_output")" "child stderr"

    # assert: a caller-controlled marker cannot bypass the exact unit and
    # effective-limit checks used for nested execution
    if SUPP_SLOTTER_BOUNDED_RUNNER=1 SUPP_SLOTTER_BOUNDED_UNIT=bogus \
        "$runner" -- true >/dev/null 2>&1; then
        die "spoofed bounded-runner marker was accepted"
    fi

    # assert: the child is in this transient unit with the requested limits,
    # rather than merely in some finite/no-swap ancestor cgroup
    "$runner" -- bash -c '
        relative=$(awk -F: '\''$1 == "0" { print $3; exit }'\'' /proc/self/cgroup)
        root=/sys/fs/cgroup"$relative"
        printf "%s\n%s\n%s\n%s\n" \
            "$(basename -- "$relative")" \
            "$(<"$root/memory.high")" \
            "$(<"$root/memory.max")" \
            "$(<"$root/memory.swap.max")"
    ' >"$cgroup_output"
    mapfile -t cgroup_values <"$cgroup_output"
    [[ "${cgroup_values[0]}" =~ ^supp-slotter-bounded-[[:xdigit:]]{32}\.service$ ]] || die "child cgroup is not the exact transient unit: ${cgroup_values[0]@Q}"
    assert_equal '471859200' "${cgroup_values[1]}" "effective MemoryHigh"
    assert_equal '524288000' "${cgroup_values[2]}" "effective MemoryMax"
    assert_equal '0' "${cgroup_values[3]}" "effective MemorySwapMax"

    # assert: conventional 128+signal status is preserved by the relay
    if "$runner" -- bash -c 'kill -TERM "$$"' 2>/dev/null; then
        status=0
    else
        status=$?
    fi
    assert_equal '143' "$status" "child signal status"

    # assert: --collect removes the unique transient unit after completion
    "$runner" -- bash -c 'printf "%s" "$SUPP_SLOTTER_BOUNDED_UNIT" > "$1"' -- "$unit_output"
    unit_name=$(<"$unit_output")
    if [[ "$(systemctl --user show "$unit_name" -p LoadState --value 2>/dev/null)" == loaded ]]; then
        die "completed transient unit still exists: $unit_name"
    fi

    # assert: interrupting the client synchronously stops and collects the
    # exact service and its lock-holding command, instead of releasing the
    # lock behind a live test
    mkfifo -- "$interrupt_hold_fifo"
    # Keep a writer open without supplying data, so the child can block on a
    # read until the service is stopped. This is deterministic and avoids a
    # timing-dependent sleep in the interruption probe.
    exec 9<>"$interrupt_hold_fifo"
    : >"$interrupt_output"
    "$runner" -- bash -c 'printf "%s" "$SUPP_SLOTTER_BOUNDED_UNIT" > "$1"; printf start > "$2"; read -r _ < "$3"; printf done >> "$2"' -- \
        "$interrupt_unit_output" "$interrupt_output" "$interrupt_hold_fifo" &
    first_pid=$!
    for _ in {1..100}; do
        [[ -s "$interrupt_output" && -s "$interrupt_unit_output" ]] && break
        sleep 0.05
    done
    [[ -s "$interrupt_output" && -s "$interrupt_unit_output" ]] || die "interrupted-client probe never started"
    unit_name=$(<"$interrupt_unit_output")
    [[ "$unit_name" =~ ^supp-slotter-bounded-[[:xdigit:]]{32}$ ]] || die "interrupted probe reported an invalid unit: ${unit_name@Q}"
    kill -TERM "$first_pid"

    # Start a competing gate before waiting for the interrupted client. It can
    # acquire the checkout lock only after the exact interrupted service has
    # stopped, proving that cleanup is synchronous with client interruption.
    : >"$interrupt_competing_output"
    "$runner" -- bash -c 'printf acquired > "$1"' -- "$interrupt_competing_output" &
    second_pid=$!
    if wait "$first_pid"; then
        status=0
    else
        status=$?
    fi
    assert_equal '143' "$status" "interrupted client status"
    assert_equal 'start' "$(<"$interrupt_output")" "interrupted service cleanup"
    exec 9>&-
    for _ in {1..100}; do
        [[ -s "$interrupt_competing_output" ]] && break
        sleep 0.05
    done
    if [[ ! -s "$interrupt_competing_output" ]]; then
        kill -TERM "$second_pid" 2>/dev/null || true
        wait "$second_pid" 2>/dev/null || true
        systemctl --user stop "$unit_name" >/dev/null 2>&1 || true
        die "competing gate did not acquire after interrupted service cleanup"
    fi
    wait "$second_pid"
    assert_equal 'acquired' "$(<"$interrupt_competing_output")" "competing gate acquisition"
    for _ in {1..100}; do
        load_state=$(systemctl --user show "$unit_name" -p LoadState --value 2>/dev/null || true)
        [[ "$load_state" != loaded ]] && break
        sleep 0.05
    done
    [[ "$load_state" != loaded ]] || die "interrupted transient unit still exists: $unit_name"

    # assert: a nested invocation does not create a second service or deadlock
    "$runner" -- bash -c "$runner -- bash -c 'printf nested'" >"$stdout_output"
    assert_equal 'nested' "$(<"$stdout_output")" "nested invocation"

    # assert: two concurrent gates are serialized by the checkout lock
    : >"$lock_output"
    # shellcheck disable=SC2016
    "$runner" -- bash -c 'printf A1 >> "$1"; sleep 0.05; printf A2 >> "$1"' -- "$lock_output" &
    first_pid=$!
    # shellcheck disable=SC2016
    "$runner" -- bash -c 'printf B1 >> "$1"; sleep 0.05; printf B2 >> "$1"' -- "$lock_output" &
    second_pid=$!
    wait "$first_pid"
    wait "$second_pid"
    lock_value=$(<"$lock_output")
    if [[ "$lock_value" != A1A2B1B2 && "$lock_value" != B1B2A1A2 ]]; then
        die "checkout lock did not serialize gates: ${lock_value@Q}"
    fi

    echo "bounded runner probes passed"
}

main "$@"
