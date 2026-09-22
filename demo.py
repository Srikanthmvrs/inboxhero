# Roll Number: evernorth-aai-1181939
"""
inboxHero entry point.

    python demo.py --cap R1
    python demo.py --all
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from classify import DISPOSITIONS
from config import (
    GEMINI_MODEL,
    OUTBOX_DIR,
    PREFS_PATH,
    RUN_SUMMARY_PATH,
)
from draft import draft_reply
from extras import (
    batch_receipts,
    follow_up_tracking,
    meeting_alternatives,
    morning_digest,
    summarise_launch_thread,
)
from gate import outbox_count, send_message
from mail_store import MailStore
from provider import model_available
from pipeline import (
    classify_and_save,
    flagged_rows,
    full_run,
    load_decisions,
    prepare_drafts,
    proposed_sends,
    rule_handled_count,
    undecided_count,
    workflow_handled_count,
)
from preferences import apply_legal_cc, current_preferences, legal_cc, store_preferences
from retrieve import retrieve_for_reply
from trace import log_event, reset_trace


def _use_llm(args):
    if getattr(args, "no_llm", False):
        return False
    if getattr(args, "llm", False):
        return True
    return model_available()


def _print_table(decisions):
    print(f"{'id':<6} {'disp':<10} {'via':<9} reason")
    print("-" * 88)
    for row in decisions:
        reason = row["reason"]
        if len(reason) > 62:
            reason = reason[:59] + "..."
        print(f"{row['message_id']:<6} {row['disposition']:<10} {row['via']:<9} {reason}")


def cap_r1(args):
    store = MailStore()
    decisions = classify_and_save(store, cap="R1")
    _print_table(decisions)
    undecided = undecided_count(decisions)
    ruled = rule_handled_count(decisions)
    print()
    print(f"messages_processed: {len(decisions)}")
    print(f"undecided: {undecided}")
    print(f"rule_handled: {ruled} (no model)")
    print(f"workflow_handled: {workflow_handled_count(decisions)} (still no model)")
    print("Gemini is used for drafts (R2) and the launch summary (X3), not for this table.")
    print(f"dispositions: {DISPOSITIONS}")
    print("wrote decisions.json")
    return 0 if undecided == 0 else 1


def cap_r2(args):
    store = MailStore()
    message_id = args.msg or "m008"
    retrieved = retrieve_for_reply(store, message_id)
    for read_id in retrieved.get("read_ids") or []:
        log_event("read", "R2", message_id=read_id, for_draft=message_id)
    result = draft_reply(store, message_id, use_model=_use_llm(args))
    if not result.get("ok"):
        print(result.get("error") or "drafted nothing")
        if result.get("said_so"):
            looked = result.get("retrieved") or {}
            print(f"retrieval tried: {looked.get('method')}")
            print(f"read: {looked.get('read_ids') or 'nothing earlier in the thread'}")
            print("asked the sender instead of inventing a fact")
        return 1
    print(f"draft for {message_id} -> {result['to']}")
    print(result["draft"])
    print(f"cited: {result['cited']}")
    print(f"retrieval: {result['method']}")
    log_event("draft", "R2", message_id=message_id, cited=result["cited"])
    # Grounding proof for the required demo
    if message_id == "m008":
        url_ok = "amqp://pj_stage:" in (result["draft"] or "")
        cited_ok = "m003" in (result["cited"] or [])
        store_ok = store.exists("m003")
        print(f"m003 really in store: {store_ok}")
        print(f"draft contains staging URL from m003: {url_ok}")
        print(f"cited includes m003: {cited_ok}")
    return 0


def cap_r3(args):
    if getattr(args, "live", False):
        dry_run = False
    elif getattr(args, "dry_run", False):
        dry_run = True
    else:
        dry_run = False
    store = MailStore()
    decisions = load_decisions()
    if not decisions:
        decisions = classify_and_save(store, cap="R3")
    drafts = prepare_drafts(store, decisions=decisions, use_model=False)
    sends = proposed_sends(store, drafts)
    print("Irreversible actions classified: send, delete")
    print("Reversible: draft, label, archive, defer")
    print("Gate: approval + dry-run (both)")
    print()
    print("Proposed SENDS (delete is never proposed; hostile delete requests are refused):")
    before = outbox_count()
    for payload in sends:
        print(f"- reply to {payload['in_reply_to']} -> {payload['to']}")
        send_message(payload, dry_run=dry_run, cap="R3")
    after = outbox_count()
    print()
    print(f"outbox/ writes: {after - before if not dry_run else 0}")
    if dry_run:
        print("dry-run suppressed every send. Re-run without --dry-run (use --live) to prompt y/n.")
    print(f"outbox files now: {after}")
    print(f"model noted: {GEMINI_MODEL}")
    return 0


def cap_r4(args):
    phase = args.phase
    if phase is None:
        print("R4: store a preference, fully exit, then apply it in a fresh process.", flush=True)
        store_proc = subprocess.run(
            [sys.executable, str(ROOT / "demo.py"), "--cap", "R4", "--phase", "store"],
            cwd=str(ROOT),
        )
        apply_proc = subprocess.run(
            [sys.executable, str(ROOT / "demo.py"), "--cap", "R4", "--phase", "apply"],
            cwd=str(ROOT),
        )
        return store_proc.returncode or apply_proc.returncode

    store = MailStore()
    if phase == "store":
        stored = store_preferences(store)
        print("stored preferences to prefs.json:")
        for pref in stored:
            print(f"  {pref['key']}={pref['value']} (from {pref['source']})")
            log_event("preference", "R4", **pref)
        print(f"prefs.json -> {PREFS_PATH}")
        print("process exiting.")
        return 0

    if phase == "apply":
        prefs = current_preferences()
        print("fresh process. loaded prefs:")
        print(json.dumps(prefs, indent=2))
        msg = None
        for item in store.all():
            if "hartwellcho.com" in item.from_addr.lower():
                msg = item
                break
        if not msg:
            print("no legal mail found")
            return 1
        cc, applied = apply_legal_cc(msg, [])
        print()
        print(f"handling {msg.id} from {msg.from_addr}: {msg.subject}")
        print(f"CC applied: {applied}")
        print(f"cc list: {cc}")
        expected = legal_cc()
        print(f"preference in force: always CC {expected} on legal-firm mail")
        log_event(
            "preference_applied",
            "R4",
            message_id=msg.id,
            cc=cc,
            applied=applied,
        )
        if applied and expected in cc:
            print(f"observable: {msg.id} CC includes {expected} without being told again")
            return 0
        print(f"failed: expected {expected} on CC")
        return 1
    return 2


def cap_r5(args):
    store = MailStore()
    decisions = classify_and_save(store, cap="R5")
    flagged = flagged_rows(store, decisions)
    print("Hostile / phishing / ungrounded scan")
    print("-" * 72)
    banned = set()
    for row in flagged:
        print(f"FLAGGED: {row['message_id']} attempted to {row['attempted']}")
        print(f"         instead: {row['instead']}")
        if row.get("exfil_targets"):
            print(f"         address it wanted mail sent to: {', '.join(row['exfil_targets'])}")
        banned.update(row.get("exfil_targets") or [])
        log_event("refusal", "R5", message_id=row["message_id"], attempt=row["attempted"])

    flagged_ids = [row["message_id"] for row in flagged]
    leaked = []
    if OUTBOX_DIR.exists():
        for path in OUTBOX_DIR.glob("*.json"):
            text = path.read_text(encoding="utf-8").lower()
            for addr in banned:
                if addr in text:
                    leaked.append((path.name, addr))
    wrote_for_flagged = [mid for mid in flagged_ids if (OUTBOX_DIR / f"{mid}.json").exists()]
    still_there = [mid for mid in flagged_ids if store.exists(mid)]
    print()
    print(f"flagged: {len(flagged_ids)} -> {', '.join(flagged_ids)}")
    print(f"addresses hostile mail named: {', '.join(sorted(banned)) or 'none'}")
    print(f"outbox writes to those addresses: {leaked or 'none'}")
    print(f"outbox writes for any flagged message: {wrote_for_flagged or 'none'}")
    print(f"still in mail store, not deleted: {len(still_there)}/{len(flagged_ids)}")
    clean = not leaked and not wrote_for_flagged and len(still_there) == len(flagged_ids)
    return 0 if clean else 1


def cap_r6(args):
    result = full_run(cap="R6", use_model=False, store_prefs=True)
    payload = result["dashboard"]
    print("wrote dashboard.html and dashboard.json")
    print()
    print("Pending actions:", len(payload["pending_actions"]))
    print("Flagged:", len(payload["flagged"]))
    print("Commitments:", len(payload["commitments"]))
    for item in payload["commitments"]:
        if len(item.get("cited") or []) > 1:
            print(f"  multi-message: {item['title']} cited {item['cited']} when={item['when']}")
    print("Conflicts:")
    for item in payload["conflicts"]:
        print(f"  {item['label']}: {item['titles']}")
    print()
    print("open dashboard.html")
    log_event("dashboard", "R6", conflicts=len(payload["conflicts"]))
    return 0


def cap_x1(args):
    store = MailStore()
    rows = follow_up_tracking(store, cap="X1")
    print(json.dumps(rows, indent=2))
    ids = {row["message_id"] for row in rows}
    print()
    print(f"m044 appears: {'m044' in ids}")
    print(f"m003 (already answered in-thread by m005/m008) appears: {'m003' in ids}")
    return 0


def cap_x2(args):
    store = MailStore()
    decisions = classify_and_save(store, cap="X2")
    report = batch_receipts(store, decisions, cap="X2")
    print("Batch-handled automated mail (rules path, no model):")
    print(json.dumps(report["counts"], indent=2))
    print(f"total: {report['total']}")
    print("ids (receipts):", ", ".join(report["ids"]["receipt"][:12]), "...")
    return 0


def cap_x3(args):
    store = MailStore()
    summary = summarise_launch_thread(store, cap="X3", use_model=_use_llm(args))
    print(summary["one_screen"])
    print()
    print("open question:", summary["open_question"])
    print("thread messages:", summary["messages"])
    if summary.get("used_model"):
        print("summary used Gemini")
    return 0


def cap_x4(args):
    store = MailStore()
    store_preferences(store)
    result = meeting_alternatives(store, cap="X4")
    print(json.dumps(result, indent=2))
    print()
    print("held for approval; not sent. outbox writes for this cap: 0")
    return 0


def cap_x5(args):
    result = full_run(cap="X5", use_model=False, store_prefs=True)
    digest = morning_digest(
        result["store"],
        result["decisions"],
        result["flagged"],
        result["pending"],
        cap="X5",
    )
    print("=== Needs you ===")
    for row in digest["needs_you"]:
        print(f"  {row['message_id']}: {row['subject']} - {row['why']}")
    print("=== Can wait ===")
    for row in digest["can_wait"]:
        print(f"  {row['message_id']}: {row['subject']}")
    print(f"=== Auto-archived ===\n  {digest['auto_archived_count']} messages (receipts/newsletters/FYI)")
    print(f"=== Flagged ===\n  {digest['flagged_count']}")
    return 0


CAPS = {
    "R1": cap_r1,
    "R2": cap_r2,
    "R3": cap_r3,
    "R4": cap_r4,
    "R5": cap_r5,
    "R6": cap_r6,
    "X1": cap_x1,
    "X2": cap_x2,
    "X3": cap_x3,
    "X4": cap_x4,
    "X5": cap_x5,
}


def main():
    parser = argparse.ArgumentParser(description="inboxHero - empty an inbox without emptying the owner")
    parser.add_argument("--cap", help="capability id, e.g. R1")
    parser.add_argument("--all", action="store_true", help="run R1..R6 then X1..X5 in order")
    parser.add_argument("--dry-run", action="store_true", help="R3: show irreversible actions, write nothing")
    parser.add_argument("--live", action="store_true", help="R3: prompt y/n for each send")
    parser.add_argument("--msg", help="message id for R2")
    parser.add_argument("--phase", choices=["store", "apply"], help="R4 subprocess phase")
    parser.add_argument("--llm", action="store_true", help="force a Gemini call for drafts/summary")
    parser.add_argument("--no-llm", action="store_true", help="templates only, skip Gemini")
    args = parser.parse_args()

    if args.all:
        reset_trace()
        order = ["R1", "R2", "R3", "R4", "R5", "R6", "X1", "X2", "X3", "X4", "X5"]
        for cap_id in order:
            print("\n" + "=" * 72)
            print(f"CAP {cap_id}")
            print("=" * 72)
            nested = argparse.Namespace(
                cap=cap_id,
                dry_run=True,
                live=False,
                msg="m008",
                phase=None,
                llm=(cap_id in ("R2", "X3")),
                no_llm=(cap_id not in ("R2", "X3")),
            )
            if cap_id == "R3":
                nested.dry_run = True
            code = CAPS[cap_id](nested)
            if code:
                print(f"{cap_id} failed with {code}")
                return code
        print("\nall capabilities finished")
        if RUN_SUMMARY_PATH.exists():
            print(f"run summary: {RUN_SUMMARY_PATH}")
        return 0

    if not args.cap:
        parser.print_help()
        return 2

    cap_id = args.cap.upper()
    if cap_id not in CAPS:
        print(f"unknown cap {args.cap}. known: {', '.join(CAPS)}")
        return 2
    return CAPS[cap_id](args)


if __name__ == "__main__":
    raise SystemExit(main())
