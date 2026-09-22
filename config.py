# Roll Number: evernorth-aai-1181939
"""Model provider is configured only through environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

OWNER_EMAIL = os.getenv("OWNER_EMAIL", "sam@paperjet.io")
OWNER_NAME = os.getenv("OWNER_NAME", "Sam")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

# Seconds between LLM calls. Free tiers are often ~15 requests/minute.
CALL_GAP_SECONDS = float(os.getenv("CALL_GAP_SECONDS", "4"))

INBOX_PATH = ROOT / "inbox.json"
OUTBOX_DIR = ROOT / "outbox"
TRACE_PATH = ROOT / "trace.jsonl"
DECISIONS_PATH = ROOT / "decisions.json"
DRAFTS_PATH = ROOT / "drafts.json"
PREFS_PATH = ROOT / "prefs.json"
DASHBOARD_HTML = ROOT / "dashboard.html"
DASHBOARD_JSON = ROOT / "dashboard.json"
RUN_SUMMARY_PATH = ROOT / "run_summary.json"

# Clock used for follow-up ageing and "today" on the dashboard.
REFERENCE_NOW = os.getenv("REFERENCE_NOW", "2026-09-10T09:00:00")
