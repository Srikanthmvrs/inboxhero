# Roll Number: evernorth-aai-1181939
"""The mail store. Retrieval reads from here; cited ids are checked against it."""

import json
from datetime import datetime

from config import INBOX_PATH, OWNER_EMAIL


class Message:
    def __init__(self, raw):
        self.id = raw["id"]
        self.thread_id = raw["thread_id"]
        self.from_addr = raw["from"]
        self.to_addr = raw["to"]
        self.subject = raw["subject"]
        self.timestamp = raw["timestamp"]
        self.body = raw["body"]
        self.unread = bool(raw.get("unread"))
        self.raw = raw

    @property
    def dt(self):
        return datetime.fromisoformat(self.timestamp)

    @property
    def from_domain(self):
        if "@" not in self.from_addr:
            return ""
        return self.from_addr.split("@", 1)[1].lower()

    @property
    def from_local(self):
        return self.from_addr.split("@", 1)[0].lower()

    def as_dict(self):
        return dict(self.raw)


class MailStore:
    def __init__(self, path=None):
        self.path = path or INBOX_PATH
        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.messages = [Message(item) for item in payload]
        self.by_id = {msg.id: msg for msg in self.messages}

    def __len__(self):
        return len(self.messages)

    def get(self, message_id):
        return self.by_id.get(message_id)

    def exists(self, message_id):
        return message_id in self.by_id

    def thread(self, thread_id):
        rows = [msg for msg in self.messages if msg.thread_id == thread_id]
        rows.sort(key=lambda msg: msg.dt)
        return rows

    def earlier_in_thread(self, message_id):
        msg = self.get(message_id)
        if not msg:
            return []
        return [item for item in self.thread(msg.thread_id) if item.dt < msg.dt]

    def keyword_search(self, terms, exclude_id=None):
        needles = [term.lower() for term in terms if term]
        hits = []
        for msg in self.messages:
            if exclude_id and msg.id == exclude_id:
                continue
            blob = f"{msg.subject}\n{msg.body}".lower()
            if any(needle in blob for needle in needles):
                hits.append(msg)
        hits.sort(key=lambda msg: msg.dt)
        return hits

    def sent_by_owner(self):
        return [msg for msg in self.messages if msg.from_addr.lower() == OWNER_EMAIL]

    def all(self):
        return list(self.messages)
