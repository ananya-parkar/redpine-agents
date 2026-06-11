# agent-1/src/reporting/email/email_digest.py

import smtplib
from email.message import EmailMessage
from pathlib import Path

from src.core.config import (
    EMAIL_FROM,
    EMAIL_PASSWORD,
    EMAIL_TO
)


def send_run_digest(
    priority_rows,
    dashboard_file,
    html_report
):

    top_leads = [
        r
        for r in priority_rows
        if not r.get("suppress_digest")
    ][:10]
    print(
        f"[EMAIL] Priority rows={len(priority_rows)} "
        f"Digest rows={len(top_leads)}",
        flush=True
    )

    digest_count = len(top_leads)


    msg = EmailMessage()

    msg["Subject"] = (
        f"Hotel Acquisition Agent | "
        f"{len(top_leads)} New / Resurfaced Opportunities"
    )

    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    # --------------------------------------------------
    # Plain Text Fallback
    # --------------------------------------------------

    msg.set_content(
        f"""
Hotel Acquisition Agent

Priority Leads Identified: {len(priority_rows)}

Please view this email in HTML format for the full report.
"""
    )

    # --------------------------------------------------
    # Build HTML Table Rows
    # --------------------------------------------------

    rows_html = ""
    if not top_leads:
        rows_html = """
        <tr>
            <td colspan="5">
            No new or resurfaced acquisition opportunities identified in this run.
            </td>
        </tr>
        """
    else:
        for row in top_leads:

            rows_html += f"""
            <tr>
                <td>{row.get('rank')}</td>
                <td>{row.get('hotel_name')}</td>
                <td>{row.get('final_lead_score')}</td>
                <td>{row.get('llm_analysis', {}).get('opportunity_score', '')}</td>
                <td>{row.get('lead_reason')}</td>
            </tr>
            """

    # --------------------------------------------------
    # HTML Email Body
    # --------------------------------------------------

    html_body = f"""
<html>
<body style="
    font-family: Calibri, Arial, sans-serif;
    font-size: 11pt;
    color: #000000;">
<p>Hi,</p>

<p>
Please find attached the results from the latest run of the Hotel Acquisition Agent.
</p>

<p>
The attached dashboard contains the complete lead universe generated during this run,
and the HTML report provides a detailed acquisition review of the highest-priority opportunities.
</p>

<h3>RUN SUMMARY</h3>

<p>
<b>New / Resurfaced Opportunities: {digest_count}</p>

<h3>TOP ACQUISITION OPPORTUNITIES</h3>

<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
    <tr style="background-color:#f2f2f2;">
        <th>Rank</th>
        <th>Property</th>
        <th>Lead Score</th>
        <th>Opportunity Score</th>
        <th>Key Reason</th>
    </tr>

    {rows_html}

</table>

<br>

<h3>ATTACHMENTS</h3>

<ul>
    <li>Hotel Acquisition Dashboard (.xlsx)</li>
    <li>Hotel Acquisition Report (.html)</li>
</ul>

<p>
This email was generated automatically by the Hotel Acquisition Agent.
</p>

<p>
Regards,<br>
Hotel Acquisition Agent
</p>

</body>
</html>
"""

    msg.add_alternative(
        html_body,
        subtype="html"
    )

    # --------------------------------------------------
    # Attach Files
    # --------------------------------------------------

    for file_path in [dashboard_file, html_report]:

        file_path = Path(file_path)

        with open(file_path, "rb") as f:

            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="octet-stream",
                filename=file_path.name
            )

    # --------------------------------------------------
    # Send Email
    # --------------------------------------------------

    with smtplib.SMTP_SSL(
        "smtp.gmail.com",
        465
    ) as smtp:

        smtp.login(
            EMAIL_FROM,
            EMAIL_PASSWORD
        )

        smtp.send_message(msg)

    print(
        "[EMAIL] Digest sent successfully",
        flush=True
    )