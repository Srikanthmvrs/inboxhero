# Roll Number: evernorth-aai-1181939

import json
from datetime import datetime

from config import TRACE_PATH


def reset_trace():
    TRACE_PATH.write_text("", encoding="utf-8")


def log_event(event, cap, **fields):
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "cap": cap,
        "event": event,
    }
    record.update(fields)
    with TRACE_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")


def events_for(cap=None, event=None):
    if not TRACE_PATH.exists():
        return []
    rows = []
    for line in TRACE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if cap and row.get("cap") != cap:
            continue
        if event and row.get("event") != event:
            continue
        rows.append(row)
    return rows
