# CAPABILITIES.md

**Student:** Srikanth Mothey, evernorth-aai-1181939
**Repository:** https://github.com/srikanthmvrs/inboxhero

```
python demo.py --cap R1
python demo.py --all
```

## The system, in one paragraph

Python only, no framework. `inbox.json` is loaded, receipts/newsletters/phishing/injection are handled by rules, and the remaining mail is classified from the thread and keywords. Gemini writes the grounded reply and the launch-thread summary. Send only happens through `gate.py` into `outbox/`. Prefs live in `prefs.json` (same idea as SkyVault `memory.py`).

## Inbox data

The run processes **100** messages. I assume each object has `id`, `thread_id`, `from`, `to`, `subject`, `timestamp`, `body`, and `unread`, that `timestamp` is ISO-8601, and that the mailbox owner is `sam@paperjet.io`. No other fields are required.

## Design choices

- **Framework: none.** Same as Assignments 4 and 5. One branch (rules vs the rest), not a crew.
- **Retrieval: thread-walk.** `thread_id` is already on every message. Keyword search if the fact is sitting in another thread.
- **Reversible vs irreversible.** Send and delete cannot be undone here (no trash). Draft, label, archive, defer can. I never propose delete.
- **Gate.** `require_approval()` in `gate.py`. `--dry-run` and `--live`. The model cannot call send.
- **Escalation.** I do not ask about 70 receipts. I do ask before sending, and I leave legal / money / vague mail for Sam. Trade-off: an internal FYI might get archived too quickly.

## Capabilities

| id | name | tier | one-line claim |
|----|------|------|----------------|
| R1 | Zero the inbox | B | every message gets one disposition + reason |
| R2 | Grounded reply | B | draft cites the earlier message it used |
| R3 | Gate the irreversible | C | no send without approval or --dry-run |
| R4 | Persistent preference | C | preference still there after a restart |
| R5 | Refuse embedded instructions | C | detect, refuse, flag, tell the user |
| R6 | Dashboard | C | three panes, citations, conflicts |
| X1 | Follow-up tracking | B | unanswered mail Sam sent |
| X2 | Batch receipts | A | count of automated mail archived by rules |
| X3 | Launch-thread summary | B | long thread -> open question |
| X4 | Preference-aware scheduling | C | reject 9am, offer three slots, hold |
| X5 | Morning digest | B | needs you / can wait / archived |

Commands, observables and evidence are in `capabilities.json`.

## Final Report

Answers are in README.md.
