"""
Send daily run summary via Slack and/or email.
Reads autoresearch/daily_config.json for settings.
"""

import json
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "daily_config.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH) as f:
        return json.load(f)


def send_slack(webhook_url: str, text: str) -> bool:
    import urllib.request
    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps({"text": text}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as _:
            return True
    except Exception:
        return False


def send_email(cfg: dict, subject: str, body: str) -> bool:
    email_cfg = cfg.get("email", {})
    if not email_cfg.get("enabled"):
        return False
    host = email_cfg.get("smtp_host", "smtp.gmail.com")
    port = email_cfg.get("smtp_port", 587)
    user = email_cfg.get("smtp_user", "")
    pw_env = email_cfg.get("smtp_password_env", "SMTP_PASSWORD")
    password = os.environ.get(pw_env, "")
    from_addr = email_cfg.get("from_addr", user)
    to_addrs = email_cfg.get("to_addrs", [])
    if not user or not password or not to_addrs:
        return False
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(host, port) as s:
            s.starttls()
            s.login(user, password)
            s.sendmail(from_addr, to_addrs, msg.as_string())
        return True
    except Exception:
        return False


def main():
    cfg = load_config()
    # Summary from args or stdin
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = sys.stdin.read().strip() or "Daily run completed."
    date = os.environ.get("DATE", "")
    subject = f"AI Hedge Fund Daily Run {date}"
    body = f"{subject}\n\n{text}"

    sent_slack = False
    if cfg.get("slack_webhook_url"):
        sent_slack = send_slack(cfg["slack_webhook_url"], text)
    if os.environ.get("DAILY_ALERT_URL"):
        sent_slack = send_slack(os.environ["DAILY_ALERT_URL"], text) or sent_slack

    sent_email = send_email(cfg, subject, body)
    if sent_slack:
        print("Slack alert sent.")
    if sent_email:
        print("Email alert sent.")
    if not sent_slack and not sent_email:
        print("No alerts sent (no webhook/email configured).")


if __name__ == "__main__":
    main()
