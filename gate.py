# Roll Number: evernorth-aai-1181939
"""
The only functions that can send or delete.

A draft can be rewritten. An archive can be undone. A send cannot be unsent,
and this mock store has no trash, so delete is irreversible too.
"""

import json
from datetime import datetime

from config import OUTBOX_DIR
from trace import log_event


def proposed_label(action, payload):
    target = payload.get("to") or payload.get("message_id")
    return f"{action} -> {target}"


def require_approval(action, payload, dry_run=False, cap="R3"):
    """
    Gate an irreversible action.
    Returns True only when the human approved and dry-run is off.
    """
    proposed = {
        "action": action,
        "payload": payload,
        "label": proposed_label(action, payload),
    }
    log_event(
        "gate",
        cap,
        proposed=proposed,
        message_id=payload.get("in_reply_to") or payload.get("message_id"),
        dry_run=dry_run,
    )

    if dry_run:
        print(f"  [dry-run] would {proposed['label']}")
        log_event(
            "gate",
            cap,
            decision="dry-run",
            happened="suppressed",
            message_id=payload.get("in_reply_to") or payload.get("message_id"),
            proposed_action=action,
        )
        return False

    prompt = (
        f"\nIRREVERSIBLE: {action}\n"
        f"  to:      {payload.get('to')}\n"
        f"  cc:      {payload.get('cc')}\n"
        f"  subject: {payload.get('subject')}\n"
        f"  body:    {(payload.get('body') or '')[:240]}\n"
        "Approve this send/delete? [y/N]: "
    )
    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        answer = "n"

    approved = answer in ("y", "yes")
    log_event(
        "gate",
        cap,
        decision="approved" if approved else "denied",
        human_said=answer or "n",
        happened="send" if approved and action == "send" else "no-op",
        message_id=payload.get("in_reply_to") or payload.get("message_id"),
        proposed_action=action,
    )
    print(f"  human said {answer or 'n'} -> {'allowed' if approved else 'blocked'}")
    return approved


def send_message(payload, dry_run=False, cap="R3"):
    """Write one file to outbox/ and nowhere else. Gated."""
    OUTBOX_DIR.mkdir(exist_ok=True)
    if not require_approval("send", payload, dry_run=dry_run, cap=cap):
        return {"written": False, "path": None}

    message_id = payload.get("in_reply_to") or payload.get("id") or "unknown"
    path = OUTBOX_DIR / f"{message_id}.json"
    record = dict(payload)
    record["sent_at"] = datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    log_event("send", cap, message_id=message_id, path=str(path))
    return {"written": True, "path": str(path)}


def delete_message(message_id, dry_run=False, cap="R3"):
    """Deletes are irreversible here (no trash). Always gated. inboxHero never proposes them."""
    payload = {"message_id": message_id, "action": "delete"}
    allowed = require_approval("delete", payload, dry_run=dry_run, cap=cap)
    log_event(
        "delete",
        cap,
        message_id=message_id,
        happened="would-delete" if allowed else "not-implemented-left-in-place",
    )
    # Nothing is removed even on approval: the mock store has no trash to restore from.
    return False


def outbox_count():
    if not OUTBOX_DIR.exists():
        return 0
    return len(list(OUTBOX_DIR.glob("*.json")))
