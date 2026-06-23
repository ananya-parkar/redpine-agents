from datetime import datetime


# ── Brand colors ──────────────────────────────────────────────
NAVY    = "#0E2A47"
GREEN   = "#1B5E20"
ORANGE  = "#E65100"
LIGHT   = "#F4F6FA"
WHITE   = "#FFFFFF"
MGRAY   = "#64748B"
DGRAY   = "#1F2937"
BORDER  = "#E2E8F0"

TIER_COLORS = {
    1: ("#FFCDD2", "#C62828", "Early Rumor"),
    2: ("#FFE0B2", "#E65100", "Funding Committed"),
    3: ("#C8E6C9", "#1B5E20", "Design Phase"),
    4: ("#BBDEFB", "#1565C0", "Procurement"),
}
ENG_COLORS = {
    "engage_now":          ("#C8E6C9", "#1B5E20", "Act Now"),
    "monitor":             ("#FFF9C4", "#F57F17", "Monitor"),
    "too_late":            ("#FFCDD2", "#B71C1C", "Too Late"),
    "insufficient_signal": ("#F3F4F6", "#6B7280", "Low Signal"),
}


def _pill(text, bg, color):
    return (f'<span style="background:{bg};color:{color};padding:2px 8px;'
            f'border-radius:4px;font-size:11px;font-weight:600;">{text}</span>')


def _tier_pill(tier):
    if not tier: return ""
    bg, fg, label = TIER_COLORS.get(int(tier), ("#F3F4F6","#6B7280","Unknown"))
    return _pill(f"Tier {tier} — {label}", bg, fg)


def _eng_pill(action):
    bg, fg, label = ENG_COLORS.get(action, ("#F3F4F6","#6B7280", action or "—"))
    return _pill(label, bg, fg)


def _stat_box(label, value, color):
    return f"""
    <td style="width:25%;padding:12px;text-align:center;">
      <div style="background:{color}10;border:1px solid {color}40;
                  border-radius:8px;padding:12px 8px;">
        <div style="font-size:26px;font-weight:700;color:{color};">{value}</div>
        <div style="font-size:11px;color:{MGRAY};margin-top:2px;">{label}</div>
      </div>
    </td>"""


def build_daily_email(ranked_leads, new_leads, tier_alerts):
    today      = datetime.now().strftime("%B %d, %Y")
    top_leads  = [r for r in ranked_leads
                  if r.get("engagement_action") == "engage_now"][:10]
    total      = len(ranked_leads)
    act_now_ct = sum(1 for r in ranked_leads if r.get("engagement_action") == "engage_now")
    monitor_ct = sum(1 for r in ranked_leads if r.get("engagement_action") == "monitor")

    subject = f"Stadium Construction Lead Report — {datetime.now():%b %d, %Y}"

    # ── Top leads table rows ───────────────────────────────────
    lead_rows = ""
    for i, r in enumerate(top_leads, 1):
        bg   = WHITE if i % 2 else LIGHT
        score = r.get("final_score") or "—"
        score_color = (GREEN if float(score or 0) >= 85
                       else "#F57F17" if float(score or 0) >= 70
                       else ORANGE)
        reason = (r.get("engagement_reason") or "")[:120]
        if reason.startswith("[PURSUING]"):
            reason = "⭐ " + reason.replace("[PURSUING]", "").strip()

        lead_rows += f"""
        <tr style="background:{bg};">
          <td style="padding:10px 12px;font-size:13px;font-weight:600;color:{NAVY};
                     border-bottom:1px solid {BORDER};">{i}</td>
          <td style="padding:10px 12px;font-size:13px;color:{DGRAY};
                     border-bottom:1px solid {BORDER};">
            <strong>{r.get('venue_name','')}</strong><br>
            <span style="font-size:11px;color:{MGRAY};">
              {r.get('city','')}, {r.get('state','')} · {r.get('league','')}
            </span>
          </td>
          <td style="padding:10px 12px;text-align:center;border-bottom:1px solid {BORDER};">
            {_tier_pill(r.get('signal_tier'))}
          </td>
          <td style="padding:10px 12px;text-align:center;border-bottom:1px solid {BORDER};">
            <span style="font-size:18px;font-weight:700;color:{score_color};">{score}</span>
          </td>
          <td style="padding:10px 12px;font-size:11px;color:{MGRAY};
                     border-bottom:1px solid {BORDER};">{reason}</td>
        </tr>"""

    if not lead_rows:
        lead_rows = f"""<tr><td colspan="5" style="padding:16px;text-align:center;
                          color:{MGRAY};font-size:13px;">No Act Now leads this run.</td></tr>"""

    # ── New leads rows ─────────────────────────────────────────
    new_rows = ""
    for r in (new_leads or [])[:8]:
        new_rows += f"""
        <tr>
          <td style="padding:8px 12px;font-size:13px;color:{DGRAY};
                     border-bottom:1px solid {BORDER};">
            {r.get('venue_name','')}
          </td>
          <td style="padding:8px 12px;text-align:center;border-bottom:1px solid {BORDER};">
            {_tier_pill(r.get('signal_tier'))}
          </td>
          <td style="padding:8px 12px;text-align:center;border-bottom:1px solid {BORDER};">
            {_eng_pill(r.get('engagement_action'))}
          </td>
          <td style="padding:8px 12px;font-size:12px;color:{MGRAY};
                     border-bottom:1px solid {BORDER};">
            {(r.get('opportunity_summary') or '')[:80]}
          </td>
        </tr>"""
    if not new_rows:
        new_rows = f"""<tr><td colspan="4" style="padding:16px;text-align:center;
                        color:{MGRAY};font-size:13px;">No new leads today.</td></tr>"""

    # ── Tier change rows ───────────────────────────────────────
    tier_rows = ""
    for a in (tier_alerts or [])[:8]:
        arrow = "⬆" if (a.get("to_tier") or 0) > (a.get("from_tier") or 0) else "⬇"
        clr   = GREEN if arrow == "⬆" else "#C62828"
        tier_rows += f"""
        <tr>
          <td style="padding:8px 12px;font-size:13px;font-weight:600;color:{NAVY};
                     border-bottom:1px solid {BORDER};">{a.get('venue_name','')}</td>
          <td style="padding:8px 12px;text-align:center;border-bottom:1px solid {BORDER};">
            <span style="color:{MGRAY};">T{a.get('from_tier')}</span>
            <span style="color:{clr};font-size:16px;margin:0 4px;">{arrow}</span>
            <span style="color:{clr};font-weight:700;">T{a.get('to_tier')}</span>
          </td>
          <td style="padding:8px 12px;font-size:11px;color:{MGRAY};
                     border-bottom:1px solid {BORDER};">
            {str(a.get('changed_at',''))[:10]}
          </td>
        </tr>"""
    if not tier_rows:
        tier_rows = f"""<tr><td colspan="3" style="padding:16px;text-align:center;
                         color:{MGRAY};font-size:13px;">No tier changes this week.</td></tr>"""

    # ── Full HTML ──────────────────────────────────────────────
    body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F1F5F9;font-family:Calibri,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F1F5F9;padding:24px 0;">
<tr><td align="center">
<table width="680" cellpadding="0" cellspacing="0"
       style="background:{WHITE};border-radius:12px;overflow:hidden;
              box-shadow:0 2px 12px rgba(0,0,0,0.08);">

  <!-- HEADER -->
  <tr>
    <td style="background:{NAVY};padding:24px 32px;">
      <div style="font-size:20px;font-weight:700;color:{WHITE};letter-spacing:0.5px;">
        🏟 Stadium Construction Lead Report
      </div>
      <div style="font-size:13px;color:#93C5FD;margin-top:4px;">{today}</div>
    </td>
  </tr>

  <!-- STAT BOXES -->
  <tr>
    <td style="padding:20px 24px 8px;">
      <table width="100%" cellpadding="0" cellspacing="8">
        <tr>
          {_stat_box("Total Leads", total, NAVY)}
          {_stat_box("Act Now", act_now_ct, "#E65100")}
          {_stat_box("Monitor", monitor_ct, "#7C3AED")}
          {_stat_box("New Today", len(new_leads or []), GREEN)}
        </tr>
      </table>
    </td>
  </tr>

  <!-- TOP ACT NOW LEADS -->
  <tr>
    <td style="padding:16px 24px 0;">
      <div style="background:{GREEN};color:{WHITE};font-size:13px;font-weight:700;
                  padding:10px 16px;border-radius:6px 6px 0 0;">
        🎯 TOP ACT NOW LEADS
      </div>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border:1px solid {BORDER};border-top:none;border-radius:0 0 6px 6px;">
        <tr style="background:{LIGHT};">
          <th style="padding:8px 12px;font-size:11px;color:{MGRAY};text-align:left;
                     border-bottom:1px solid {BORDER};">#</th>
          <th style="padding:8px 12px;font-size:11px;color:{MGRAY};text-align:left;
                     border-bottom:1px solid {BORDER};">Venue</th>
          <th style="padding:8px 12px;font-size:11px;color:{MGRAY};text-align:center;
                     border-bottom:1px solid {BORDER};">Tier</th>
          <th style="padding:8px 12px;font-size:11px;color:{MGRAY};text-align:center;
                     border-bottom:1px solid {BORDER};">Score</th>
          <th style="padding:8px 12px;font-size:11px;color:{MGRAY};text-align:left;
                     border-bottom:1px solid {BORDER};">Why Now</th>
        </tr>
        {lead_rows}
      </table>
    </td>
  </tr>

  <!-- NEW LEADS -->
  <tr>
    <td style="padding:16px 24px 0;">
      <div style="background:{NAVY};color:{WHITE};font-size:13px;font-weight:700;
                  padding:10px 16px;border-radius:6px 6px 0 0;">
        ✨ NEW LEADS DISCOVERED TODAY
      </div>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border:1px solid {BORDER};border-top:none;border-radius:0 0 6px 6px;">
        <tr style="background:{LIGHT};">
          <th style="padding:8px 12px;font-size:11px;color:{MGRAY};text-align:left;
                     border-bottom:1px solid {BORDER};">Venue</th>
          <th style="padding:8px 12px;font-size:11px;color:{MGRAY};text-align:center;
                     border-bottom:1px solid {BORDER};">Tier</th>
          <th style="padding:8px 12px;font-size:11px;color:{MGRAY};text-align:center;
                     border-bottom:1px solid {BORDER};">Status</th>
          <th style="padding:8px 12px;font-size:11px;color:{MGRAY};text-align:left;
                     border-bottom:1px solid {BORDER};">Signal Summary</th>
        </tr>
        {new_rows}
      </table>
    </td>
  </tr>

  <!-- TIER CHANGES -->
  <tr>
    <td style="padding:16px 24px 0;">
      <div style="background:#7C3AED;color:{WHITE};font-size:13px;font-weight:700;
                  padding:10px 16px;border-radius:6px 6px 0 0;">
        📈 TIER CHANGES THIS WEEK
      </div>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border:1px solid {BORDER};border-top:none;border-radius:0 0 6px 6px;">
        <tr style="background:{LIGHT};">
          <th style="padding:8px 12px;font-size:11px;color:{MGRAY};text-align:left;
                     border-bottom:1px solid {BORDER};">Venue</th>
          <th style="padding:8px 12px;font-size:11px;color:{MGRAY};text-align:center;
                     border-bottom:1px solid {BORDER};">Tier Movement</th>
          <th style="padding:8px 12px;font-size:11px;color:{MGRAY};text-align:left;
                     border-bottom:1px solid {BORDER};">Date</th>
        </tr>
        {tier_rows}
      </table>
    </td>
  </tr>

  <!-- FOOTER -->
  <tr>
    <td style="padding:24px 32px;text-align:center;border-top:1px solid {BORDER};
               margin-top:16px;">
      <div style="font-size:11px;color:{MGRAY};">
        Full dashboard and all leads in the attached Excel file.<br>
        <span style="color:#93C5FD;">Agent 2 — Stadium Construction Lead Gen</span>
        · Parkar Digital for RedPine Capital
      </div>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""

    return subject, body