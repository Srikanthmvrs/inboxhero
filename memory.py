# Roll Number: evernorth-aai-1181939
"""File-backed preference store. Last-write-wins on the same key. Reused from SkyVault."""

import json
from datetime import datetime

from config import PREFS_PATH


def load_memory():
    if not PREFS_PATH.exists():
        return {}
    with PREFS_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_memory(memory):
    with PREFS_PATH.open("w", encoding="utf-8") as handle:
        json.dump(memory, handle, indent=2)


def remember(key, value, source="user"):
    memory = load_memory()
    previous_value = None
    conflict = False

    if key in memory:
        previous_value = memory[key].get("value")
        if str(previous_value) != str(value):
            conflict = True

    entry = {
        "value": value,
        "source": source,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if conflict:
        entry["previous_value"] = previous_value

    memory[key] = entry
    save_memory(memory)
    return {
        "status": "updated" if conflict else "stored",
        "conflict": conflict,
        "key": key,
        "value": value,
        "previous_value": previous_value if conflict else None,
        "rule": "last-write-wins: a restated key overwrites the old value",
    }


def recall(query=None):
    memory = load_memory()
    if not query:
        return memory
    needle = str(query).lower()
    matched = {}
    for key, entry in memory.items():
        value_text = str(entry.get("value", "")).lower()
        if needle in key.lower() or needle in value_text:
            matched[key] = entry
    return matched


def memory_summary():
    memory = load_memory()
    if not memory:
        return "No saved preferences."
    return "\n".join(f"{key}: {entry.get('value')}" for key, entry in memory.items())
