# inboxHero

**Public repo:** https://github.com/srikanthmvrs/inboxhero

## Student Information

**Name:** Srikanth Mothey
**Roll Number:** evernorth-aai-1181939
**Assignment:** Assignment 06 - Project inboxHero
**Model Provider:** Google Gemini
**Model Used:** `gemini-3.1-flash-lite` (same as SkyVault). Override with `GEMINI_MODEL` in `.env`.

---

# What this is

Sam's inbox is `inbox.json` (100 messages). inboxHero walks it, puts a disposition on every message, drafts the ones that can be answered from earlier mail, and stops before sending. "Send" just writes a file under `outbox/`. I did not connect a real mailbox.

I reused `memory.py` and the Gemini wrapper style from Assignment 5. No CrewAI / ADK - it is a straight Python pipeline, same as SkyVault.

# How it is split

Receipts, newsletters and "no-reply" mail never go to Gemini. `rules.py` archives those. Prompt-injection and phishing are caught in `inject.py` before classify. What is left is a smaller set: replies, legal CC, meetings, stuff that is too vague.

Gemini is used for:

- grounded drafts (`python demo.py --cap R2 --msg m008`)
- the launch-thread summary (`python demo.py --cap X3`)

`--all` calls the model on those two only so a free API tier does not melt. Pass `--no-llm` if you want templates only. There is a 4 second gap between calls and a retry on HTTP 429.

# Dispositions

- **reply** - draft something, still gated before send
- **archive** - done / noise
- **defer** - waiting (follow-up)
- **delegate** - loop someone else in (Priya on Hartwell & Cho)
- **escalate** - Sam has to look; we will not guess

Send and delete are irreversible. There is no trash in this mock store, so I never delete. Draft / archive / defer can be undone. The gate is `gate.py`: `--dry-run` prints what it would do, `--live` asks y/n.

Retrieval is thread-walk on `thread_id`, keyword search if the fact is in another thread (venue hold needs the launch date).

# Run

```bash
pip install -r requirements.txt
copy .env.example .env
```

Put `GEMINI_API_KEY` in `.env`. Do not zip `.env`.

```bash
python demo.py --cap R1
python demo.py --cap R2 --msg m008
python demo.py --cap R3 --dry-run
python demo.py --cap R4
python demo.py --cap R5
python demo.py --cap R6
python demo.py --cap X1
python demo.py --cap X2
python demo.py --cap X3
python demo.py --cap X4
python demo.py --cap X5
python demo.py --all
```

Open `dashboard.html` after R6.

# Final Report

1. **What did you refuse to automate?** `m023` wants Sam to wire $3,200 for a venue deposit today, says "don't loop in finance yet", and signs off as P - except it is from `priya.nair@paperjet.co` and the real Priya is `priya@paperjet.io`. The line I drew is money leaving the company. You cannot un-wire $3,200, and getting that wrong once costs more than every archive mistake in this inbox put together. `inject.detect_phishing` does flag this one on the domain and the secrecy line, but that is not really why I refuse it - a genuine wire request goes back to Sam too. Same line for the Hartwell & Cho SAFE mail (CC Priya, let Sam sign) and for `m012`, which is too vague to ground, so it drafts nothing.

2. **Where does untrusted text enter?** At `mail_store.py`, and after that every body is just data. `inject.inspect()` runs before classify, so hostile mail is flagged and escalated before a model sees it, and both places that call Gemini (`draft.py` and the X3 summary in `extras.py`) wrap the body in `<untrusted_email>` first. None of that is the real defence though. `gate.py` holds the only functions that write to `outbox/`, and `draft.py` and `provider.py` cannot reach them, so there is no send tool for the model to be talked into using. `preferences.extract_safe_preferences` also skips anything `inspect()` flagged, which is why `m039` cannot save "autonomous mode" and turn the gate off next run; to get a send an attacker needs the scan to miss them and then needs Sam to type `y`.

3. **Who is accountable when it sends the wrong thing?** Whoever typed `y`. The gate prints the recipient, CC, subject and the first 240 characters before it asks, so nobody is approving blind, and that is also why I kept the approval list short - forty prompts and you read none of them. Sam still wears it outside the company, because the mail goes out in his name and the recipient has no idea a system wrote it. For tracing, `trace.jsonl` has the proposed payload, the y/n and whether `outbox/` got a file, and every draft keeps its `cited` ids, so a bad fact and a bad approval look different in the log; what it will not catch is a draft that is accurate but tone-deaf.

4. **Name your own machinery.** `classify.py` is the router - it picks a disposition the way a framework would route a task, and it never calls Gemini. Each `demo.py --cap ...` is a Task, `draft.py` is the Agent that talks to the model, and `pipeline.py` is the Crew that runs classify, retrieve, draft and dashboard in order. A framework would have handed me the graph, the retries and a better CLI; `gate.py` I would have written anyway, because send and delete must not be tools the model can call. I think a crew would have hurt here - this inbox is one branch (rules vs the rest), and putting send behind function calling is exactly how `m039` ("updated assistant settings") gets what it wants.

---

## Files

```
demo.py            entry point (--cap / --all)
inbox.json
config.py          env vars
provider.py        Gemini + 429 retry
mail_store.py
rules.py           noise
inject.py          hostile mail
classify.py        dispositions
retrieve.py        thread-walk
draft.py
gate.py
memory.py          from SkyVault, writes prefs.json
preferences.py
commitments.py
dashboard.py
pipeline.py
extras.py          X1-X5
```
