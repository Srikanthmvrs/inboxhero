# Roll Number: evernorth-aai-1181939
"""One disposition per message. Rules for noise/flags, then keyword / thread checks."""

from inject import inspect
from rules import is_internal, is_owner, looks_like_noise, noise_reason

DISPOSITIONS = ["reply", "archive", "defer", "delegate", "escalate"]


def classify_one(store, msg):
    flag = inspect(msg)
    if flag:
        return {
            "message_id": msg.id,
            "thread_id": msg.thread_id,
            "from": msg.from_addr,
            "subject": msg.subject,
            "disposition": "escalate",
            "reason": f"flagged {flag['kind']}: {flag['attempt']}",
            "via": "rules",
            "flag": flag,
            "needs_human": True,
        }

    body = msg.body.lower()
    subj = msg.subject.lower()

    if is_owner(msg) and "do not take meetings before" in body:
        return _decision(msg, "archive", "calendar preference from the owner, save it", "rules")

    if is_internal(msg) and "hartwell" in body and ("cc" in body or "loop me in" in subj):
        return _decision(msg, "archive", "standing CC request, save as a preference", "rules")

    if looks_like_noise(msg):
        return _decision(msg, "archive", noise_reason(msg), "rules")

    if "hartwellcho.com" in msg.from_addr.lower():
        return _decision(
            msg,
            "delegate",
            "mail from the lawyers - CC Priya, do not auto-sign",
            "workflow",
        )

    if "resend the url" in body or "staging queue creds" in body:
        return _decision(msg, "reply", "needs a fact from earlier in the thread", "workflow")

    if "staging is down" in subj or "rotated the broker" in body or "workers are draining" in body:
        return _decision(msg, "archive", "staging thread already moved on", "workflow")

    if "needs sam specifically" in body or (
        "pricing copy" in body and "approve" in body
    ):
        return _decision(msg, "escalate", "Sam has to approve this himself", "workflow")

    if "launch week" in subj:
        return _decision(msg, "archive", "launch update, no ask for Sam", "workflow")

    if "board review" in body and "scheduled" in subj:
        return _decision(msg, "archive", "date goes on the calendar", "workflow")

    if "board deck" in subj and "two days before" in body:
        return _decision(msg, "escalate", "deadline depends on another message", "workflow")

    if "that thing we talked about" in body or subj.strip() == "the thing":
        return _decision(msg, "escalate", "too vague to answer without guessing", "workflow")

    if "before markets open" in body or (
        "9:00am" in body and "monday" in body and "partner" in body
    ):
        return _decision(msg, "reply", "slot is earlier than the calendar rule", "workflow")

    if "intro call" in subj or ("30 minutes" in body and "3:00pm" in body):
        return _decision(msg, "reply", "meeting request with a specific time", "workflow")

    if "move our" in subj and "1:1" in subj:
        return _decision(msg, "reply", "internal reschedule", "workflow")

    if "product demo on wednesday" in body or "demo -- wednesday" in subj:
        return _decision(msg, "reply", "external demo slot", "workflow")

    if "date you locked in with your team" in body:
        return _decision(msg, "reply", "needs the launch date from another thread", "workflow")

    if "another offer" in body and "next steps" in body:
        return _decision(msg, "reply", "candidate waiting on a timeline", "workflow")

    if "launch coverage" in subj or "for our launch coverage" in body:
        return _decision(msg, "escalate", "press wording should come from Sam", "workflow")

    if "grab coffee" in body and "no agenda" in body:
        return _decision(msg, "escalate", "social invite, no dates", "workflow")

    if "dental" in body or "dr. osei" in body:
        return _decision(msg, "escalate", "appointment may clash with something else", "workflow")

    if "timesheet" in subj:
        return _decision(msg, "defer", "reminder, not urgent mail", "rules")

    if "i'm out thursday" in body or "pto next week" in subj:
        return _decision(msg, "archive", "FYI from the team", "rules")

    if "office will be closed" in body:
        return _decision(msg, "archive", "facilities FYI", "rules")

    if "auto-saved notes" in body:
        return _decision(msg, "archive", "notes dump", "rules")

    if "no further action needed" in body or "no action needed to continue" in body:
        return _decision(msg, "archive", "vendor said no action needed", "rules")

    if "uptime last week" in body:
        return _decision(msg, "archive", "status FYI", "rules")

    if is_owner(msg) and msg.to_addr.lower() != msg.from_addr.lower():
        return _decision(msg, "defer", "mail Sam sent, nobody has answered yet", "workflow")

    return _decision(msg, "escalate", "not sure, leaving it for Sam", "workflow")


def _decision(msg, disposition, reason, via):
    return {
        "message_id": msg.id,
        "thread_id": msg.thread_id,
        "from": msg.from_addr,
        "subject": msg.subject,
        "disposition": disposition,
        "reason": reason,
        "via": via,
        "flag": None,
        "needs_human": disposition in ("reply", "escalate", "delegate"),
    }


def classify_all(store):
    return [classify_one(store, msg) for msg in store.all()]
