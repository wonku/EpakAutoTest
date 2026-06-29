from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from config.settings import parse_email_recipients
from utils.email_report import EmailReportConfig


def email_config_from_settings() -> EmailReportConfig:
    return EmailReportConfig(
        smtp_host=os.getenv("EMAIL_SMTP_HOST", "").strip(),
        smtp_port=int(os.getenv("EMAIL_SMTP_PORT", "465")),
        smtp_ssl=os.getenv("EMAIL_SMTP_SSL", "true").lower() == "true",
        smtp_starttls=os.getenv("EMAIL_SMTP_STARTTLS", "false").lower() == "true",
        username=os.getenv("EMAIL_USERNAME", "").strip(),
        password=os.getenv("EMAIL_PASSWORD", "").strip(),
        sender=os.getenv("EMAIL_FROM", os.getenv("EMAIL_USERNAME", "")).strip(),
        recipients=parse_email_recipients(),
        subject_prefix=os.getenv("EMAIL_SUBJECT_PREFIX", "[Pyautotest]").strip(),
        attach_logs=os.getenv("EMAIL_ATTACH_LOGS", "true").lower() == "true",
        max_attachment_mb=int(os.getenv("EMAIL_MAX_ATTACHMENT_MB", "10")),
    )


EMAIL_SUBJECT_LABEL_MAP = {
    "易食包商城": "Esbao-Mall",
    "EPAK 英文商城": "EPAK-Mall",
    "CRM API 回归": "CRM-API",
}


def resolve_email_subject_label(label: str) -> str:
    mapped = EMAIL_SUBJECT_LABEL_MAP.get(label)
    if mapped:
        return mapped
    if label.isascii():
        return label
    return "Pyautotest"


def mask_recipient(address: str) -> str:
    address = address.strip()
    if "@" not in address:
        return "***"
    local, domain = address.split("@", 1)
    if not local:
        return f"***@{domain}"
    if len(local) == 1:
        return f"{local}***@{domain}"
    return f"{local[0]}***@{domain}"


def write_email_audit(
    *,
    status: str,
    label: str,
    subject: str,
    recipients: list[str],
    error: str = "",
    attachment_count: int = 0,
) -> Path:
    out = Path("reports/email-last.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "label": label,
        "subject": subject,
        "recipients": recipients,
        "recipients_masked": [mask_recipient(item) for item in recipients],
        "recipient_count": len(recipients),
        "attachment_count": attachment_count,
        "error": error,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "smtp_host": os.getenv("EMAIL_SMTP_HOST", "").strip(),
        "sender": os.getenv("EMAIL_FROM", os.getenv("EMAIL_USERNAME", "")).strip(),
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
