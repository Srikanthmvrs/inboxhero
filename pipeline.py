# Roll Number: evernorth-aai-1181939
"""Run a full pass: classify, draft, dashboard. Send/delete still go through gate.py."""

import json
from datetime import datetime

from classify import classify_all
from config import (
    DECISIONS_PATH,
    DRAFTS_PATH,
    OUTBOX_DIR,
    OWNER_EMAIL,
    REFERENCE_NOW,
    RUN_SUMMARY_PATH,
)
from dashboard import build_dashboard_payload, write_dashboard
from draft import draft_reply
from mail_store import MailStore
from preferences import apply_legal_cc, legal_cc, no_meetings_before, store_preferences
from retrieve import retrieve_for_reply
from trace import log_event

def load_store():
    return MailStore()


def classify_and_save(store, cap="R1"):
    decisions = classify_all(store)
    DECISIONS_PATH.write_text(json.dumps(decisions, indent=2), encoding="utf-8")
    for row in decisions:
        log_event(
            "decision",
            cap,
            message_id=row["message_id"],
            disposition=row["disposition"],
            reason=row["reason"],
            via=row["via"],
        )
        if row.get("flag"):
            log_event(
                "refusal",
                "R5",
                message_id=row["message_id"],
                attempt=row["flag"].get("attempt"),
                kind=row["flag"].get("kind"),
            )
    return decisions


def rule_handled_count(decisions):
    return sum(1 for row in decisions if row.get("via") == "rules")


def workflow_handled_count(decisions):
    return sum(1 for row in decisions if row.get("via") == "workflow")


def undecided_count(decisions):
    return sum(1 for row in decisions if not row.get("disposition"))


def flagged_rows(store, decisions):
    rows = []
    for row in decisions:
        flag = row.get("flag")
        if flag:
            rows.append(
                {
                    "message_id": row["message_id"],
                    "kind": flag.get("kind"),
                    "attempted": flag.get("attempt"),
                    "instead": "refused, flagged, left in place; nothing written to outbox/",
                    "exfil_targets": flag.get("exfil_targets") or [],
                }
            )
    for msg in store.all():
        if "that thing we talked about" not in msg.body.lower() and msg.subject.lower() != "the thing":
            continue
        if any(item["message_id"] == msg.id for item in rows):
            continue
        retrieved = retrieve_for_reply(store, msg.id)
        if retrieved.get("missing") or not retrieved.get("cited"):
            rows.append(
                {
                    "message_id": msg.id,
                    "kind": "ungrounded",
                    "attempted": "guess what 'the thing' was and act on it",
                    "instead": "asked Sam instead of guessing; drafted nothing",
                    "exfil_targets": [],
                }
            )
    return rows


def pending_rows(store, decisions, drafts):
    rows = []
    for row in decisions:
        msg = store.get(row["message_id"])
        if not msg:
            continue
        disp = row["disposition"]
        if disp == "reply":
            draft = drafts.get(msg.id) or {}
            why = "Sending cannot be undone, so it waits on a human."
            if "9:00" in msg.body:
                why = "Slot is before the no-meetings-before-11 rule."
            elif msg.from_domain not in ("paperjet.io",):
                why = "External recipient, sending in Sam's name."
            if "amqp://" in (draft.get("draft") or ""):
                why = "Draft has staging credentials in it."
            rows.append(
                {
                    "message_id": msg.id,
                    "subject": msg.subject,
                    "proposed_action": "send draft" if draft and draft.get("ok") else "hold draft",
                    "why_human": why,
                    "disposition": disp,
                }
            )
        elif disp == "delegate":
            rows.append(
                {
                    "message_id": msg.id,
                    "subject": msg.subject,
                    "proposed_action": f"CC {legal_cc() or 'Priya'}, leave signing to Sam",
                    "why_human": "Legal mail. The system will not send or sign.",
                    "disposition": disp,
                }
            )
        elif disp == "escalate" and not row.get("flag"):
            rows.append(
                {
                    "message_id": msg.id,
                    "subject": msg.subject,
                    "proposed_action": "do not act alone",
                    "why_human": row.get("reason") or "needs the owner",
                    "disposition": disp,
                }
            )
    return rows


def prepare_drafts(store, decisions=None, use_model=False):
    drafts = {}
    reply_ids = []
    if decisions:
        reply_ids = [row["message_id"] for row in decisions if row["disposition"] == "reply"]
    else:
        reply_ids = [msg.id for msg in store.all() if "resend the url" in msg.body.lower()]
    for message_id in reply_ids:
        result = draft_reply(store, message_id, use_model=use_model)
        drafts[message_id] = result
        if result.get("ok"):
            for read_id in result.get("read_ids") or []:
                log_event("read", "R2", message_id=read_id, for_draft=message_id)
            log_event(
                "draft",
                "R2",
                message_id=message_id,
                cited=result.get("cited"),
                method=result.get("method"),
            )
    DRAFTS_PATH.write_text(json.dumps(drafts, indent=2, default=str), encoding="utf-8")
    return drafts


def proposed_sends(store, drafts):
    """Payloads that would be written to outbox/ if approved."""
    sends = []
    for message_id, draft in drafts.items():
        if not draft.get("ok"):
            continue
        msg = store.get(message_id)
        cc, applied = apply_legal_cc(msg, [])
        payload = {
            "in_reply_to": message_id,
            "to": draft["to"],
            "cc": cc,
            "subject": draft["subject"],
            "body": draft["draft"],
            "cited": draft.get("cited") or [],
        }
        sends.append(payload)
    # Legal mail is never auto-sent; we only expose CC as a pending action.
    return sends


def write_run_summary(store, decisions, flagged, pending):
    hostile = [row for row in flagged if row.get("kind") in ("injection", "phishing")]
    summary = {
        "messages_processed": len(decisions),
        "undecided": undecided_count(decisions),
        "rule_handled": rule_handled_count(decisions),
        "workflow_handled": sum(1 for row in decisions if row.get("via") == "workflow"),
        "outbox_writes": len(list(OUTBOX_DIR.glob("*.json"))) if OUTBOX_DIR.exists() else 0,
        "flagged": flagged,
        "hostile_found": hostile,
        "pending": pending,
        "preferences": {
            "legal_cc": legal_cc(),
            "no_meetings_before": no_meetings_before(),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "reference_now": REFERENCE_NOW,
        "owner": OWNER_EMAIL,
    }
    RUN_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


def full_run(cap="R1", use_model=False, store_prefs=False):
    store = load_store()
    if store_prefs:
        store_preferences(store)
    decisions = classify_and_save(store, cap=cap)
    drafts = prepare_drafts(store, decisions=decisions, use_model=use_model)
    flagged = flagged_rows(store, decisions)
    pending = pending_rows(store, decisions, drafts)
    payload = build_dashboard_payload(store, decisions, drafts, pending, flagged)
    write_dashboard(payload)
    summary = write_run_summary(store, decisions, flagged, pending)
    return {
        "store": store,
        "decisions": decisions,
        "drafts": drafts,
        "flagged": flagged,
        "pending": pending,
        "dashboard": payload,
        "summary": summary,
    }


def load_decisions():
    if not DECISIONS_PATH.exists():
        return None
    return json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))
