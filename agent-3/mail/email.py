# agent-3/mail/email.py
"""
Layer 7 (email half) — Daily Email Digest

Sends an HTML email (minimal styling - thin grey borders, white
background, no color fills) showing the TOP LEADS overall, pulled
directly from Postgres (the same source the dashboard uses) - not
just today's brand-new survivors, since most runs find 0 new
candidates once a geography has been fully covered.

The "new today" count is still reported separately for context.

Uses EMAIL_FROM / EMAIL_PASSWORD / EMAIL_TO from .env (Gmail SMTP).
"""

import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(override=True)

EMAIL_FROM = os.getenv("EMAIL_FROM_AGENT3")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD_AGENT3")
EMAIL_TO = os.getenv("EMAIL_TO")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

TOP_N = 10

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "dbname": os.getenv("POSTGRES_DB_AGENT3", "redpine_agent3"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
}


def _get_connection():
    return psycopg2.connect(**DB_CONFIG)


def fetch_top_leads(limit=TOP_N):
    """
    Same source the dashboard uses - the full candidates table in
    Postgres, ranked by Seller Readiness Score, joined with the most
    recent evidence/rationale for the "Why Selected" column.
    """
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    c.company_name,
                    c.state,
                    c.seller_readiness_score,
                    e.one_line_reason,
                    e.why_selected
                FROM candidates c
                LEFT JOIN LATERAL (
                    SELECT * FROM evidence ev WHERE ev.candidate_id = c.id
                    ORDER BY ev.created_at DESC LIMIT 1
                ) e ON true
                ORDER BY c.seller_readiness_score DESC NULLS LAST
                LIMIT %s
                """,
                (limit,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def fetch_total_candidate_count():
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM candidates")
            return cur.fetchone()[0]
    finally:
        conn.close()


def _escape(text):
    if text is None:
        return ""
    text = str(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_plain_text_fallback(top_leads, new_today_count, total_count):
    today_str = datetime.now().strftime("%d-%b-%Y")

    lines = [
        "AGENT 3 - DAILY ACQUISITION TARGET DIGEST",
        f"Date: {today_str}",
        f"New candidates found today: {new_today_count}",
        f"Total candidates in database: {total_count}",
        "",
    ]

    if not top_leads:
        lines.append("No candidates in the database yet.")
        return "\n".join(lines)

    lines.append(f"Top {len(top_leads)} leads overall:")
    for i, row in enumerate(top_leads, start=1):
        company = row.get("company_name", "")
        state = row.get("state", "")
        score = row.get("seller_readiness_score", "")
        reason = row.get("one_line_reason") or row.get("why_selected") or ""
        lines.append(f"{i}. {company} ({state}) - Score: {score} - {reason}")

    lines.append("")
    lines.append("Full details are in the attached dashboard workbook.")
    lines.append("")
    lines.append("- Agent 3 Pipeline")

    return "\n".join(lines)


def build_html_body(top_leads, new_today_count, total_count):
    today_str = datetime.now().strftime("%d-%b-%Y")

    style = """
        body { font-family: Arial, Helvetica, sans-serif; color: #1a1a1a; }
        table { border-collapse: collapse; width: 100%; max-width: 700px; }
        th, td { border: 1px solid #cccccc; padding: 8px 10px; text-align: left; font-size: 13px; }
        th { background-color: #ffffff; font-weight: bold; border-bottom: 2px solid #999999; }
        h2 { font-size: 18px; margin-bottom: 4px; }
        .meta { font-size: 13px; color: #444444; margin-bottom: 16px; }
        .footer { font-size: 12px; color: #777777; margin-top: 20px; }
    """

    html_parts = [
        f"<html><head><style>{style}</style></head><body>",
        "<h2>Agent 3 &mdash; Daily Acquisition Target Digest</h2>",
        f'<div class="meta">Date: {today_str}<br>'
        f"New candidates found today: {new_today_count}<br>"
        f"Total candidates in database: {total_count}</div>",
    ]

    if not top_leads:
        html_parts.append("<p>No candidates in the database yet.</p>")
    else:
        html_parts.append(f"<p><strong>Top {len(top_leads)} Leads Overall</strong></p>")
        html_parts.append("<table>")
        html_parts.append(
            "<tr><th>Rank</th><th>Company</th><th>State</th>"
            "<th>Score</th><th>Why Selected</th></tr>"
        )

        for i, row in enumerate(top_leads, start=1):
            company = _escape(row.get("company_name", ""))
            state = _escape(row.get("state", ""))
            score = _escape(row.get("seller_readiness_score", ""))
            reason = _escape(row.get("one_line_reason") or row.get("why_selected") or "")
            html_parts.append(
                f"<tr><td>{i}</td><td>{company}</td><td>{state}</td>"
                f"<td>{score}</td><td>{reason}</td></tr>"
            )

        html_parts.append("</table>")
        html_parts.append(
            '<p class="footer">Full details are in the attached dashboard workbook.</p>'
        )

    html_parts.append('<p class="footer">- Agent 3 Pipeline</p>')
    html_parts.append("</body></html>")

    return "".join(html_parts)


def send_daily_digest(new_candidates_df, dashboard_file_path):
    """
    new_candidates_df: today's new candidates DataFrame (final_df from
                        main.py) - used ONLY to report the "new today"
                        count, not for the table contents.
    dashboard_file_path: path to the generated .xlsx to attach
    """
    if not all([EMAIL_FROM, EMAIL_PASSWORD, EMAIL_TO]):
        raise ValueError(
            "Missing EMAIL_FROM, EMAIL_PASSWORD, or EMAIL_TO in .env - "
            "cannot send digest email."
        )

    new_today_count = len(new_candidates_df)
    top_leads = fetch_top_leads(TOP_N)
    total_count = fetch_total_candidate_count()

    plain_text = build_plain_text_fallback(top_leads, new_today_count, total_count)
    html_body = build_html_body(top_leads, new_today_count, total_count)
    today_str = datetime.now().strftime("%d-%b-%Y")

    msg = EmailMessage()
    msg["Subject"] = (
        f"Agent 3 Daily Digest - {today_str} "
        f"({new_today_count} new, {total_count} total)"
    )
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.set_content(plain_text)
    msg.add_alternative(html_body, subtype="html")

    if dashboard_file_path and os.path.exists(dashboard_file_path):
        with open(dashboard_file_path, "rb") as f:
            file_data = f.read()
        file_name = os.path.basename(dashboard_file_path)
        msg.add_attachment(
            file_data,
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=file_name,
        )
        print(f"Attached: {file_name}")
    else:
        print("Warning: dashboard file not found, sending email without attachment.")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(msg)

    print(f"Daily digest sent to {EMAIL_TO}")