"""Schedule output: action points, placement notes, summary."""

from __future__ import annotations


def build_action_points(warnings: list[dict]) -> list[str]:
    subjects_by_action: dict[str, set[str]] = {}
    for warning in warnings:
        concern = warning.get("concern")
        if concern == "manual review":
            continue
        product = warning.get("product")
        substance = warning.get("substance") or warning.get("source")
        action = warning.get("action")
        if not isinstance(action, str):
            continue
        if warning.get("category") == "Unresolved active concern":
            subject = "Unresolved active concerns"
        else:
            subject = product or substance or "Stack"
        subjects_by_action.setdefault(action, set()).add(str(subject))

    points: list[str] = []
    for action, subjects in subjects_by_action.items():
        subject_list = sorted(subjects, key=str.casefold)
        if len(subject_list) == 1:
            points.append(f"{subject_list[0]}: {action}")
        else:
            points.append(f"{'; '.join(subject_list)}: {action}")
    return points[:8]

def build_placement_notes(schedule: dict) -> list[dict]:
    notes: list[dict] = []
    for product_name, explanation in schedule.get("explanations", {}).items():
        why_here = [
            note
            for note in explanation.get("why_here", [])
            if isinstance(note, str) and "tradeoff" in note.lower()
        ]
        if not why_here:
            continue
        notes.append(
            {
                "product": product_name,
                "pillbox": explanation.get("pillbox"),
                "slot": explanation.get("slot"),
                "notes": why_here,
            }
        )
    return sorted(notes, key=lambda entry: str(entry["product"]).casefold())

def build_schedule_summary(schedule: dict) -> dict:
    take: dict[str, list[str]] = {}
    for pillbox_name, pillbox in schedule.get("pillboxes", {}).items():
        lines: list[str] = []
        for slot in pillbox.get("slots", {}).values():
            if not slot.get("products"):
                continue
            lines.append(f"{slot['label']}: {', '.join(slot['products'])}")
        if lines:
            take[pillbox_name] = lines
    return {"take": take}

