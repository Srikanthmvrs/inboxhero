# Roll Number: evernorth-aai-1181939
"""Thin Gemini wrapper with backoff. Returns None if the model cannot be used."""

import time

from config import CALL_GAP_SECONDS, GEMINI_API_KEY, GEMINI_MODEL

_last_call_at = 0.0


def model_available():
    return bool(GEMINI_API_KEY)


def _wait_gap():
    global _last_call_at
    elapsed = time.time() - _last_call_at
    if elapsed < CALL_GAP_SECONDS:
        time.sleep(CALL_GAP_SECONDS - elapsed)


def generate_text(prompt, system_instruction=None, retries=4):
    """Return model text, or None if no key / persistent failure. Never crashes on 429."""
    if not GEMINI_API_KEY:
        return None

    try:
        import google.generativeai as genai
    except ImportError:
        return None

    genai.configure(api_key=GEMINI_API_KEY)
    kwargs = {"model_name": GEMINI_MODEL}
    if system_instruction:
        kwargs["system_instruction"] = system_instruction
    model = genai.GenerativeModel(**kwargs)

    delay = 5
    for attempt in range(retries):
        try:
            _wait_gap()
            global _last_call_at
            response = model.generate_content(prompt)
            _last_call_at = time.time()
            return (response.text or "").strip()
        except Exception as exc:
            text = str(exc)
            rate_limited = (
                "429" in text
                or "ResourceExhausted" in text
                or "RESOURCE_EXHAUSTED" in text
                or "rate" in text.lower()
            )
            if rate_limited and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            return None
    return None
