from __future__ import annotations

import json
from pathlib import Path

from config import settings
from utils.email_config import (
    email_config_from_settings,
    mask_recipient,
    write_email_audit,
)
from utils.email_report import build_ui_inspection_email_body, send_pytest_email_report
from utils.mall_ui_report import ui_report_attachments


def email_report_requested(config) -> bool:
    try:
        if config.getoption("--email-report"):
            return True
    except ValueError:
        pass
    return settings.EMAIL_REPORT_ENABLED


def send_ui_report_email(config, label: str, report_path: Path) -> bool:
    if not email_report_requested(config):
        print("email report skipped: add --email-report or set EMAIL_REPORT_ENABLED=true")
        write_email_audit(
            status="skipped",
            label=label,
            subject="",
            recipients=[],
            error="email report not requested",
        )
        return False

    sent: set[str] = getattr(config, "_ui_emails_sent", set())
    key = str(Path(report_path).resolve())
    if key in sent:
        print(f"email report skipped for {label}: already sent for {key}")
        return False

    path = Path(report_path)
    if not path.exists():
        message = f"report not found at {path}"
        print(f"email report skipped for {label}: {message}")
        write_email_audit(status="skipped", label=label, subject="", recipients=[], error=message)
        return False

    email_config = email_config_from_settings()
    recipients = email_config.recipients
    if not recipients:
        message = "EMAIL_TO is empty — configure recipient addresses in Jenkins Credentials"
        print(f"email report was not sent for {label}: {message}")
        write_email_audit(status="failed", label=label, subject="", recipients=[], error=message)
        return False

    report = json.loads(path.read_text(encoding="utf-8"))
    report_dir = path.parent
    report["report_dir"] = str(report_dir.resolve())
    summary = {
        "exitstatus": report.get("exitstatus", 1 if report.get("status") != "PASS" else 0),
        "started_at": report.get("started_at", ""),
        "finished_at": report.get("finished_at", ""),
        "duration_seconds": report.get("duration_seconds", 0),
        "stats": {
            "passed": 1 if report.get("status") == "PASS" else 0,
            "failed": 0 if report.get("status") == "PASS" else 1,
            "skipped": 0,
        },
        "report_label": f"{label}",
    }
    summary_path = Path("reports/test-summary-last.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    body = build_ui_inspection_email_body([(label, report)], summary)
    attachments = ui_report_attachments(report_dir, summary_path)
    try:
        subject = send_pytest_email_report(email_config, summary, attachments, body=body)
    except Exception as exc:
        message = str(exc)
        print(f"email report was not sent for {label}: {message}")
        write_email_audit(
            status="failed",
            label=label,
            subject="",
            recipients=recipients,
            error=message,
            attachment_count=len(attachments),
        )
        return False

    audit_path = write_email_audit(
        status="sent",
        label=label,
        subject=subject,
        recipients=recipients,
        attachment_count=len(attachments),
    )
    masked = ", ".join(mask_recipient(item) for item in recipients)
    print(
        f"email report sent for {label} -> {masked} "
        f"(recipients={len(recipients)}, attachments={len(attachments)}, audit={audit_path})"
    )
    sent.add(key)
    config._ui_emails_sent = sent
    return True
