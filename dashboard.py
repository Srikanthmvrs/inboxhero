# Roll Number: evernorth-aai-1181939
"""Three-pane dashboard written from a completed run. Not hand-assembled."""

import json
from collections import defaultdict
from datetime import datetime
from html import escape

from config import DASHBOARD_HTML, DASHBOARD_JSON
from commitments import extract_commitments, find_conflicts


def build_dashboard_payload(store, decisions, drafts, pending, flagged):
    commitments = extract_commitments(store)
    conflicts = find_conflicts(commitments)
    payload = {
        "generated_from": "run",
        "pending_actions": pending,
        "flagged": flagged,
        "commitments": commitments,
        "conflicts": conflicts,
    }
    return payload


def _when_label(iso):
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%a %d %b %Y %H:%M")


def _calendar_cells(commitments):
    by_day = defaultdict(list)
    for item in commitments:
        day = item["when"][:10]
        by_day[day].append(item)
    # September 2026 starts Tuesday
    first_weekday = 1  # Tue
    days_in_month = 30
    cells = []
    for _ in range(first_weekday):
        cells.append({"day": "", "items": []})
    for day in range(1, days_in_month + 1):
        key = f"2026-09-{day:02d}"
        cells.append({"day": str(day), "iso": key, "items": by_day.get(key, [])})
    return cells


def render_html(payload):
    pending = payload["pending_actions"]
    flagged = payload["flagged"]
    commitments = payload["commitments"]
    conflicts = payload["conflicts"]
    cells = _calendar_cells(commitments)

    def rows_pending():
        if not pending:
            return "<tr><td colspan='3'>None</td></tr>"
        bits = []
        for item in pending:
            bits.append(
                "<tr>"
                f"<td>{escape(item.get('message_id', ''))}<br><span class='muted'>{escape(item.get('subject', ''))}</span></td>"
                f"<td>{escape(item.get('proposed_action', ''))}</td>"
                f"<td>{escape(item.get('why_human', ''))}</td>"
                "</tr>"
            )
        return "\n".join(bits)

    def rows_flagged():
        if not flagged:
            return "<tr><td colspan='3'>None</td></tr>"
        bits = []
        for item in flagged:
            bits.append(
                "<tr>"
                f"<td>{escape(item.get('message_id', ''))}</td>"
                f"<td>{escape(item.get('attempted', ''))}</td>"
                f"<td>{escape(item.get('instead', ''))}</td>"
                "</tr>"
            )
        return "\n".join(bits)

    conflict_html = ""
    for item in conflicts:
        conflict_html += (
            f"<div class='conflict'>CONFLICT: {escape(', '.join(item['titles']))} "
            f"at {escape(_when_label(item['when']))} "
            f"(cited {escape(', '.join(item['cited']))})</div>"
        )
    if not conflicts:
        conflict_html = "<p class='muted'>No same-time conflicts.</p>"

    commit_rows = []
    for item in commitments:
        cited = ", ".join(item["cited"])
        extra = ""
        if len(item["cited"]) > 1:
            extra = " <span class='badge'>multi-message</span>"
        commit_rows.append(
            "<tr>"
            f"<td>{escape(_when_label(item['when']))}</td>"
            f"<td>{escape(item['title'])}{extra}</td>"
            f"<td>{escape(cited)}</td>"
            "</tr>"
        )

    cal_cells = []
    for cell in cells:
        if not cell["day"]:
            cal_cells.append("<div class='cell empty'></div>")
            continue
        pills = []
        for item in cell["items"]:
            cls = "pill"
            if any(item["id"] in c["items"] for c in conflicts):
                cls += " clash"
            pills.append(f"<div class='{cls}'>{escape(item['title'][:42])}</div>")
        cal_cells.append(
            f"<div class='cell'><div class='num'>{escape(cell['day'])}</div>{''.join(pills)}</div>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>inboxHero dashboard</title>
  <style>
    :root {{ font-family: "Segoe UI", system-ui, sans-serif; color: #102a43; background: #f0f4f8; }}
    body {{ margin: 0; padding: 24px; }}
    h1 {{ margin: 0 0 8px; }}
    .sub {{ color: #627d98; margin-bottom: 24px; }}
    .panes {{ display: grid; grid-template-columns: 1fr; gap: 20px; }}
    @media (min-width: 1100px) {{
      .panes {{ grid-template-columns: 1fr 1fr; }}
      .pane-c {{ grid-column: 1 / -1; }}
    }}
    .pane {{ background: #fff; border-radius: 12px; padding: 16px 18px; box-shadow: 0 1px 3px rgba(16,42,67,.08); }}
    h2 {{ margin: 0 0 12px; font-size: 1.1rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
    th, td {{ text-align: left; padding: 8px 6px; border-bottom: 1px solid #d9e2ec; vertical-align: top; }}
    th {{ color: #627d98; font-weight: 600; }}
    .muted {{ color: #829ab1; font-size: 0.85rem; }}
    .conflict {{ background: #ffe3e3; color: #911111; padding: 10px 12px; border-radius: 8px; margin-bottom: 8px; font-weight: 600; }}
    .badge {{ background: #d9f99d; color: #3f6212; padding: 1px 6px; border-radius: 999px; font-size: 0.75rem; }}
    .cal {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; margin-top: 12px; }}
    .dow {{ font-size: 0.75rem; color: #627d98; text-align: center; }}
    .cell {{ min-height: 72px; background: #f0f4f8; border-radius: 8px; padding: 6px; }}
    .cell.empty {{ background: transparent; }}
    .num {{ font-size: 0.75rem; color: #486581; }}
    .pill {{ font-size: 0.7rem; background: #dbeafe; color: #1e3a8a; border-radius: 4px; padding: 2px 4px; margin-top: 4px; }}
    .pill.clash {{ background: #fecaca; color: #7f1d1d; }}
  </style>
</head>
<body>
  <h1>inboxHero</h1>
  <p class="sub">Three-pane view generated from a completed run. Not edited by hand.</p>
  <div class="panes">
    <section class="pane">
      <h2>1. Pending actions</h2>
      <p class="muted">Things the system wants to do but may not do alone (Part 4).</p>
      <table>
        <tr><th>Message</th><th>Proposed</th><th>Why a human</th></tr>
        {rows_pending()}
      </table>
    </section>
    <section class="pane">
      <h2>2. Flagged</h2>
      <p class="muted">Hostile mail, phishing, and anything that could not be grounded.</p>
      <table>
        <tr><th>Id</th><th>Attempted</th><th>What we did instead</th></tr>
        {rows_flagged()}
      </table>
    </section>
    <section class="pane pane-c">
      <h2>3. Commitments</h2>
      {conflict_html}
      <table>
        <tr><th>When</th><th>What</th><th>Cited</th></tr>
        {''.join(commit_rows)}
      </table>
      <h3>September 2026</h3>
      <div class="cal">
        <div class="dow">Mon</div><div class="dow">Tue</div><div class="dow">Wed</div>
        <div class="dow">Thu</div><div class="dow">Fri</div><div class="dow">Sat</div><div class="dow">Sun</div>
        {''.join(cal_cells)}
      </div>
    </section>
  </div>
</body>
</html>
"""


def write_dashboard(payload):
    DASHBOARD_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    DASHBOARD_HTML.write_text(render_html(payload), encoding="utf-8")
    return DASHBOARD_HTML, DASHBOARD_JSON
