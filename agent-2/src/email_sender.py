import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path


SENDER_EMAIL = "stadiumleadsagent@gmail.com"
APP_PASSWORD = "nkmssmpkhnwrbiag"


def send_daily_report(
    receiver_email: str,
    subject: str,
    body: str,
    attachment_path: str | None = None,
):
    msg = MIMEMultipart()

    msg["From"] = SENDER_EMAIL
    msg["To"] = receiver_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "html"))

    if attachment_path:
        path = Path(attachment_path)

        with open(path, "rb") as f:
            part = MIMEApplication(f.read(), Name=path.name)

        part["Content-Disposition"] = (
            f'attachment; filename="{path.name}"'
        )

        msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)