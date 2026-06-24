"""
Layer 7 (email half) — Daily Email Digest for Agent 2

Restyled to match Agent 3's minimal look: plain grey-bordered tables,
simple header, no color pill badges or stat boxes. Content is the
same as before — Top Act Now leads, New Leads Today, Tier Changes
This Week — just presented in the simpler style.
"""

from datetime import datetime

TIER_LABELS = {
    1: "Tier 1 — Early Rumor",
    2: "Tier 2 — Funding Committed",
    3: "Tier 3 — Design Phase",
    4: "Tier 4 — Procurement",
}
ENG_LABELS = {
    "engage_now":          "Act Now",
    "monitor":             "Monitor",
    "too_late":            "Too Late",
    "insufficient_signal": "Low Signal",
}


def _escape(text):
    if text is None:
        return ""
    text = str(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _tier_text(tier):
    if not tier:
        return ""
    return _escape(TIER_LABELS.get(int(tier), f"Tier {tier}"))


def _eng_text(action):
    return _escape(ENG_LABELS.get(action, action or "—"))


def build_daily_email(ranked_leads, new_leads, tier_alerts):
    today = datetime.now().strftime("%d-%b-%Y")

    top_leads  = [r for r in ranked_leads
                  if r.get("engagement_action") == "engage_now"][:10]
    total      = len(ranked_leads)
    act_now_ct = sum(1 for r in ranked_leads if r.get("engagement_action") == "engage_now")
    monitor_ct = sum(1 for r in ranked_leads if r.get("engagement_action") == "monitor")
    new_today_count = len(new_leads or [])

    subject = (f"Stadium Construction Lead Report - {today} "
               f"({new_today_count} new, {total} total)")

    style = """
        body { font-family: Arial, Helvetica, sans-serif; color: #1a1a1a; }
        table { border-collapse: collapse; width: 100%; max-width: 700px; }
        th, td { border: 1px solid #cccccc; padding: 8px 10px; text-align: left; font-size: 13px; }
        th { background-color: #ffffff; font-weight: bold; border-bottom: 2px solid #999999; }
        h2 { font-size: 18px; margin-bottom: 4px; }
        h3 { font-size: 14px; margin: 18px 0 6px; }
        .meta { font-size: 13px; color: #444444; margin-bottom: 16px; }
        .footer { font-size: 12px; color: #777777; margin-top: 20px; }
    """

    # ── Top Act Now leads rows ──────────────────────────────────
    lead_rows = ""
    for i, r in enumerate(top_leads, 1):
        venue  = _escape(r.get("venue_name", ""))
        place  = _escape(f"{r.get('city','')}, {r.get('state','')} · {r.get('league','')}")
        tier   = _tier_text(r.get("signal_tier"))
        score  = _escape(r.get("final_score") or r.get("score") or "—")
        reason = (r.get("engagement_reason") or r.get("why_priority") or "")[:120]
        if reason.startswith("[PURSUING]"):
            reason = "[Pursuing] " + reason.replace("[PURSUING]", "").strip()
        reason = _escape(reason)
        lead_rows += (
            f"<tr><td>{i}</td><td>{venue}<br>{place}</td>"
            f"<td>{tier}</td><td>{score}</td><td>{reason}</td></tr>"
        )
    if not lead_rows:
        lead_rows = '<tr><td colspan="5">No Act Now leads this run.</td></tr>'

    # ── New leads rows ───────────────────────────────────────────
    new_rows = ""
    for r in (new_leads or [])[:8]:
        venue   = _escape(r.get("venue_name", ""))
        tier    = _tier_text(r.get("signal_tier"))
        status  = _eng_text(r.get("engagement_action") or r.get("engagement"))
        summary = _escape((r.get("opportunity_summary") or r.get("whats_happening") or "")[:80])
        new_rows += f"<tr><td>{venue}</td><td>{tier}</td><td>{status}</td><td>{summary}</td></tr>"
    if not new_rows:
        new_rows = '<tr><td colspan="4">No new leads today.</td></tr>'

    # ── Tier change rows ─────────────────────────────────────────
    tier_rows = ""
    for a in (tier_alerts or [])[:8]:
        venue     = _escape(a.get("venue_name", ""))
        from_tier = a.get("from_tier")
        to_tier   = a.get("to_tier")
        arrow     = "up" if (to_tier or 0) > (from_tier or 0) else "down"
        movement  = _escape(f"T{from_tier} -> T{to_tier} ({arrow})")
        changed   = _escape(str(a.get("changed_at", ""))[:10])
        tier_rows += f"<tr><td>{venue}</td><td>{movement}</td><td>{changed}</td></tr>"
    if not tier_rows:
        tier_rows = '<tr><td colspan="3">No tier changes this week.</td></tr>'

    html_parts = [
        f"<html><head><meta charset='UTF-8'><style>{style}</style></head><body>",
        "<h2>Stadium Construction Lead Report</h2>",
        f'<div class="meta">Date: {today}<br>'
        f"New leads found today: {new_today_count}<br>"
        f"Total leads in database: {total}<br>"
        f"Act Now: {act_now_ct} &nbsp;|&nbsp; Monitor: {monitor_ct}</div>",

        "<h3>Top Act Now Leads</h3>",
        "<table><tr><th>#</th><th>Venue</th><th>Tier</th><th>Score</th><th>Why Now</th></tr>",
        lead_rows, "</table>",

        "<h3>New Leads Discovered Today</h3>",
        "<table><tr><th>Venue</th><th>Tier</th><th>Status</th><th>Signal Summary</th></tr>",
        new_rows, "</table>",

        "<h3>Tier Changes This Week</h3>",
        "<table><tr><th>Venue</th><th>Tier Movement</th><th>Date</th></tr>",
        tier_rows, "</table>",

        '<p class="footer">Full dashboard and all leads are in the attached '
        "Excel file.<br>Agent 2 - Stadium Construction Lead Gen "
        "&middot; Parkar Digital for RedPine Capital</p>",
        "</body></html>",
    ]

    body = "".join(html_parts)
    return subject, body