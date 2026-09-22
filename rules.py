# Roll Number: evernorth-aai-1181939
"""Cheap routing. Receipts, newsletters and bot mail never touch a model."""

from config import OWNER_EMAIL

NOISE_LOCAL_PARTS = (
    "no-reply",
    "noreply",
    "no_reply",
    "notifications",
    "notification",
    "receipts",
    "receipt",
    "alerts",
    "digest",
    "billing",
    "orders",
    "invoice",
    "invoices",
    "checkin",
    "calendar-notification",
    "feedback",
    "insights",
    "updates",
    "ship-confirm",
)

NOISE_DOMAINS = (
    "spotify.com",
    "lyft.com",
    "uber.com",
    "doordash.com",
    "swiggy.in",
    "amazon.com",
    "netflix.com",
    "linkedin.com",
    "twitter.com",
    "medium.com",
    "substack.com",
    "producthunt.com",
    "coursera.org",
    "grammarly.com",
    "todoist.com",
    "mailchimp.com",
    "zoom.us",
    "digitalocean.com",
    "instacart.com",
    "bluebottlecoffee.com",
    "hackernewsletter.com",
    "namecheap.com",
    "postmarkapp.com",
    "datadoghq.com",
    "sentry.io",
    "stripe.com",
    "chase.com",
    "intercom.io",
    "vercel.com",
    "dropbox.com",
    "slack.com",
    "apple.com",
    "email.apple.com",
    "figma.com",
    "github.com",
    "accounts.google.com",
    "cloudflare.com",
    "notion.so",
    "openai.com",
    "robinhood.com",
    "pragmaticengineer.com",
    "ramp.com",
    "united.com",
    "calendly.com",
    "pagerduty.com",
)

NOISE_SUBJECT_BITS = (
    "receipt",
    "invoice",
    "your weekly",
    "daily digest",
    "screen time",
    "campaign report",
    "cloud recording",
    "unread messages",
    "new notifications",
    "appeared in",
    "password was changed",
    "verification code",
    "monitor ok",
    "incident resolved",
    "statement is available",
    "payout is on the way",
    "bill is ready",
    "usage",
    "actions minutes",
    "check-in is open",
    "timesheet",
)

FYI_NO_ASK = (
    "no action needed",
    "please do not reply",
    "this is an automated",
    "no further action needed",
)


def is_owner(msg):
    return msg.from_addr.lower() == OWNER_EMAIL


def is_internal(msg):
    return msg.from_domain.endswith("paperjet.io")


def looks_like_noise(msg):
    """True for receipts, newsletters, SaaS alerts with no human ask."""
    local = msg.from_local
    domain = msg.from_domain
    subject = msg.subject.lower()
    body = msg.body.lower()

    # Mail the owner sent, or another human at PaperJet wrote, is not noise
    # even if the subject mentions an invoice or a receipt.
    if is_owner(msg):
        return False
    if is_internal(msg) and not any(
        local.startswith(part) or part in local for part in NOISE_LOCAL_PARTS
    ):
        if msg.thread_id.startswith("t-noise-"):
            return True
        return False

    if msg.thread_id.startswith("t-noise-"):
        return True

    if any(local.startswith(part) or part in local for part in NOISE_LOCAL_PARTS):
        return True

    if any(domain == item or domain.endswith("." + item) for item in NOISE_DOMAINS):
        if "action required" in subject:
            return False
        return True

    if any(bit in subject for bit in NOISE_SUBJECT_BITS):
        if is_internal(msg) and "timesheet" in subject:
            return False
        return True

    if any(bit in body for bit in FYI_NO_ASK) and not is_internal(msg):
        return True

    return False


def noise_reason(msg):
    subject = msg.subject.lower()
    if "receipt" in subject or "invoice" in subject or "bill" in subject:
        return "automated receipt/billing mail; no reply required"
    if "digest" in subject or "newsletter" in subject or "weekly" in subject:
        return "newsletter/digest; archive"
    if "notification" in subject or "unread" in subject:
        return "product notification; archive"
    return "automated/no-reply mail; archive without a model call"
