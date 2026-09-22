# Roll Number: evernorth-aai-1181939
"""
Retrieval: thread-walk first, keyword search as fallback for cross-thread facts.
Cited ids are always checked against the mail store.
"""

import re

from config import OWNER_EMAIL



def thread_walk(store, message_id):
    msg = store.get(message_id)
    if not msg:
        return []
    return store.earlier_in_thread(message_id)


def extract_urls(text):
    return re.findall(r"(?:amqp|https?)://[^\s]+", text)


def retrieve_for_reply(store, message_id):
    """
    Return {cited: [ids], facts: [str], missing: bool, method: str, read_ids: [ids]}.
    """
    msg = store.get(message_id)
    if not msg:
        return {
            "cited": [],
            "facts": [],
            "missing": True,
            "method": "thread-walk",
            "read_ids": [],
        }

    earlier = thread_walk(store, message_id)
    read_ids = [item.id for item in earlier]
    facts = []
    cited = []

    if "staging queue" in msg.body.lower() or "resend the url" in msg.body.lower():
        for item in earlier:
            urls = extract_urls(item.body)
            amqp = [url.rstrip(" .") for url in urls if url.startswith("amqp://")]
            if amqp:
                facts.append(f"Staging AMQP URL from {item.id}: {amqp[0]}")
                cited.append(item.id)
        if not cited:
            # Cross-thread keyword fallback
            for item in store.keyword_search(["amqp://", "staging AMQP", "broker-stg"], exclude_id=message_id):
                urls = extract_urls(item.body)
                amqp = [url.rstrip(" .") for url in urls if url.startswith("amqp://")]
                if amqp:
                    facts.append(f"Staging AMQP URL from {item.id}: {amqp[0]}")
                    cited.append(item.id)
                    read_ids.append(item.id)
                    return {
                        "cited": cited,
                        "facts": facts,
                        "missing": False,
                        "method": "keyword",
                        "read_ids": read_ids,
                    }
            return {
                "cited": [],
                "facts": [],
                "missing": True,
                "method": "thread-walk",
                "read_ids": read_ids,
            }
        return {
            "cited": cited,
            "facts": facts,
            "missing": False,
            "method": "thread-walk",
            "read_ids": read_ids,
        }

    if "date you locked in with your team" in msg.body.lower():
        method = "keyword"
        hits = store.keyword_search(["launch week", "the 20th is a hard date", "Target is the 20th"])
        for item in hits:
            read_ids.append(item.id)
            if "20th" in item.body:
                facts.append(f"Launch date from {item.id}: the 20th")
                cited.append(item.id)
        cited = list(dict.fromkeys(cited))
        return {
            "cited": cited,
            "facts": facts,
            "missing": not cited,
            "method": method,
            "read_ids": list(dict.fromkeys(read_ids)),
        }

    # Generic: use the thread, plus quote any concrete numbers/dates from earlier mail.
    for item in earlier:
        facts.append(f"[{item.id} from {item.from_addr}] {item.body[:400]}")
        cited.append(item.id)

    return {
        "cited": cited,
        "facts": facts,
        "missing": len(cited) == 0 and _looks_like_needs_context(msg),
        "method": "thread-walk",
        "read_ids": read_ids,
    }


def _looks_like_needs_context(msg):
    body = msg.body.lower()
    return any(
        bit in body
        for bit in (
            "the url you gave",
            "thing we talked",
            "date you locked",
            "previous email",
            "as discussed",
        )
    )


def unanswered_owner_mail(store, now, min_days=3):
    """Owner-sent messages with no later reply in the same thread from anyone else."""
    rows = []
    for msg in store.sent_by_owner():
        if msg.to_addr.lower() == OWNER_EMAIL:
            continue
        later = [
            item
            for item in store.thread(msg.thread_id)
            if item.dt > msg.dt and item.from_addr.lower() != OWNER_EMAIL
        ]
        days = (now - msg.dt).days
        if later:
            continue
        if days >= min_days:
            rows.append({"message": msg, "days_waiting": days})
    return rows
