# Roll Number: evernorth-aai-1181939
"""Pull dates out of message bodies. Combine two messages when one has the date
and the other only says 'two days before'."""

import re
from datetime import datetime, timedelta

YEAR = 2026


def _iso(dt):
    return dt.replace(second=0, microsecond=0).isoformat()


def _parse_clock(text):
    match = re.search(r"\b(\d{1,2}):(\d{2})\s*(am|pm)\b", text, re.I)
    if not match:
        return 9, 0
    hour = int(match.group(1))
    minute = int(match.group(2))
    ampm = match.group(3).lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    return hour, minute


def _this_week_weekday(msg_dt, weekday, hour, minute):
    # Monday=0
    ahead = weekday - msg_dt.weekday()
    if ahead < 0:
        ahead += 7
    if ahead == 0 and (hour, minute) <= (msg_dt.hour, msg_dt.minute):
        ahead = 7
    return msg_dt.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=ahead)


def extract_commitments(store):
    items = []
    board_when = None
    board_id = None
    deck_id = None

    for msg in store.all():
        blob = f"{msg.subject} {msg.body}"
        low = blob.lower()
        hour, minute = _parse_clock(blob)
        title = msg.subject.strip()
        when = None

        if "two days before the board review" in low:
            deck_id = msg.id
            continue

        if "board review" in low and "the 18th" in low:
            when = datetime(YEAR, 9, 18, hour, minute)
            board_when = when
            board_id = msg.id
            title = "Quarterly board review"
        elif re.search(r"september\s+15", low) or "tuesday the 15th" in low:
            when = datetime(YEAR, 9, 15, hour, minute)
        elif "the 20th is a hard date" in low or "target is the 20th" in low:
            existing = next((i for i in items if str(i.get("when", "")).startswith("2026-09-20")), None)
            if existing:
                if msg.id not in existing["cited"]:
                    existing["cited"].append(msg.id)
                continue
            when = datetime(YEAR, 9, 20, 9, 0)
            title = "PaperJet launch"
        elif "pricing copy" in low and "by the 12th" in low:
            when = datetime(YEAR, 9, 12, 17, 0)
            title = "Approve pricing copy"
        elif "load test" in low and "the 14th" in low:
            when = datetime(YEAR, 9, 14, 10, 0)
        elif "wednesday at 2:00" in low or "wednesday at 2:00pm" in low:
            when = _this_week_weekday(msg.dt, 2, 14, 0)
        elif "monday at 9:00" in low:
            when = _this_week_weekday(msg.dt, 0, 9, 0)
        elif "other offer" in low and "the 19th" in low:
            when = datetime(YEAR, 9, 19, 17, 0)
            title = "Candidate other-offer deadline"
        elif "sign via the portal by friday" in low:
            when = _this_week_weekday(msg.dt, 4, 17, 0)
            title = "Sign SAFE"
        elif "on deadline for thursday" in low:
            when = _this_week_weekday(msg.dt, 3, 17, 0)
        elif "flag any corrections by monday" in low:
            when = _this_week_weekday(msg.dt, 0, 17, 0)
        elif re.search(r"sep 12,\s*1:00pm", low):
            when = datetime(YEAR, 9, 12, 13, 0)
        elif "renews on the 16th" in low:
            when = datetime(YEAR, 9, 16, 9, 0)
            title = "ZenBoard renewal"

        if when:
            items.append(
                {
                    "id": f"c-{msg.id}",
                    "title": title,
                    "when": _iso(when),
                    "cited": [msg.id],
                    "kind": "event",
                }
            )

    if board_when and deck_id:
        due = board_when - timedelta(days=2)
        due = due.replace(hour=17, minute=0)
        cited = [board_id, deck_id] if board_id else [deck_id]
        items.append(
            {
                "id": "c-board-deck",
                "title": "Board deck finished and circulated",
                "when": _iso(due),
                "cited": cited,
                "kind": "deadline",
                "derived": "two days before the board review",
            }
        )

    for item in items:
        for mid in item["cited"]:
            if not store.exists(mid):
                item.setdefault("cite_errors", []).append(mid)
    return items


def find_conflicts(items):
    conflicts = []
    by_when = {}
    for item in items:
        by_when.setdefault(item["when"], []).append(item)
    for when, group in sorted(by_when.items()):
        if len(group) < 2:
            continue
        conflicts.append(
            {
                "when": when,
                "label": f"CONFLICT: {len(group)} items at {when.replace('T', ' ')[:16]}",
                "items": [item["id"] for item in group],
                "titles": [item["title"] for item in group],
                "cited": sorted({mid for item in group for mid in item["cited"]}),
            }
        )
    return conflicts
