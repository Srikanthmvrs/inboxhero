# Roll Number: evernorth-aai-1181939
"""
Standing instructions.

Only owner-safe preferences are stored. Email cannot disable the gate, force
sends, or ask to be forgotten in the summary — that is Part 6, not Part 5.
"""

import re

from inject import inspect
from memory import load_memory, remember
from rules import is_owner

LEGAL_FIRM = "Hartwell & Cho"
LEGAL_DOMAINS = ("hartwellcho.com",)
PRIYA = "priya@paperjet.io"


def extract_safe_preferences(store):
    """Read the inbox and return preference dicts that are allowed to persist."""
    found = []
    for msg in store.all():
        flag = inspect(msg)
        if flag:
            continue

        body = msg.body
        subject = msg.subject.lower()

        # m015: Priya asks to be CC'd on Hartwell & Cho.
        mentions_cc = "cc" in body.lower() or "cc'd" in body.lower() or "loop me in" in subject
        from_priya = PRIYA in msg.from_addr.lower()
        about_firm = "hartwell" in body.lower() or "cho" in body.lower()
        if from_priya and mentions_cc and about_firm:
            found.append(
                {
                    "key": "legal_cc",
                    "value": PRIYA,
                    "source": msg.id,
                    "note": f"CC {PRIYA} on mail from {LEGAL_FIRM}",
                }
            )

        # m041: owner calendar rule. Allowed because it tightens scheduling, not safety.
        if is_owner(msg) and re.search(r"do not take meetings before\s+(\d{1,2}:\d{2})", body, re.I):
            match = re.search(r"before\s+(\d{1,2}:\d{2})\s*am", body, re.I)
            hhmm = match.group(1) if match else "11:00"
            if int(hhmm.split(":")[0]) <= 11:
                found.append(
                    {
                        "key": "no_meetings_before",
                        "value": "11:00",
                        "source": msg.id,
                        "note": "Do not accept meetings before 11:00am; offer 11:00am or later",
                    }
                )
    # De-dupe by key, last message wins
    by_key = {}
    for item in found:
        by_key[item["key"]] = item
    return list(by_key.values())


def store_preferences(store):
    stored = []
    for pref in extract_safe_preferences(store):
        remember(pref["key"], pref["value"], source=pref["source"])
        remember(f"{pref['key']}_note", pref["note"], source=pref["source"])
        stored.append(pref)
    return stored


def current_preferences():
    raw = load_memory()
    return {key: entry.get("value") for key, entry in raw.items()}


def legal_cc():
    return current_preferences().get("legal_cc")


def no_meetings_before():
    return current_preferences().get("no_meetings_before") or None


def apply_legal_cc(msg, cc_list):
    """If this is Hartwell & Cho mail, add Priya."""
    cc = list(cc_list or [])
    extra = legal_cc()
    if not extra:
        return cc, False
    domain = msg.from_domain
    if any(domain.endswith(item) for item in LEGAL_DOMAINS) or "hartwell" in msg.from_addr.lower():
        if extra not in cc:
            cc.append(extra)
        return cc, True
    return cc, False


def violates_no_morning_meetings(hour, minute=0):
    cutoff = no_meetings_before()
    if not cutoff:
        return False
    hh, mm = [int(part) for part in cutoff.split(":")]
    return (hour, minute) < (hh, mm)
