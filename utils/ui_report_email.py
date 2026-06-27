from __future__ import annotations

import json
from pathlib import Path

from config import settings
from utils.email_report import EmailReportConfig, build_ui_inspection_email_body, send_pytest_email_report
from utils.esbao_ui_report import ui_report_attachments


def email_report_requested(config) -> bool:
    try:
        if config.getoption("--email-report"):
            return True
    except ValueError:
        pass
    return settings.EMAIL_REPORT_ENABLED


def send_ui_report_email(config, label: str, report_path: Path) -> bool:
    if not email_report_requested(config):
        return False

    sent: set[str] = getattr(config, "_ui_emails_sent", set())
    key = str(Path(report_path).resolve())
    if key in sent:
        return False

    path = Path(report_path)
    if not path.exists():
        print(f"email report skipped for {label}: report not found at {path}")
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
        "report_label": f"{label}UI巡检",
    }
    summary_path = Path("reports/test-summary-last.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    email_config = EmailReportConfig(
        smtp_host=settings.EMAIL_SMTP_HOST,
        smtp_port=settings.EMAIL_SMTP_PORT,
        smtp_ssl=settings.EMAIL_SMTP_SSL,
        smtp_starttls=settings.EMAIL_SMTP_STARTTLS,
        username=settings.EMAIL_USERNAME,
        password=settings.EMAIL_PASSWORD,
        sender=settings.EMAIL_FROM,
        recipients=settings.EMAIL_TO,
        subject_prefix=settings.EMAIL_SUBJECT_PREFIX,
        attach_logs=settings.EMAIL_ATTACH_LOGS,
        max_attachment_mb=settings.EMAIL_MAX_ATTACHMENT_MB,
    )
    body = build_ui_inspection_email_body([(label, report)], summary)
    attachments = ui_report_attachments(report_dir, summary_path)
    try:
        send_pytest_email_report(email_config, summary, attachments, body=body)
    except Exception as exc:
        print(f"email report was not sent for {label}: {exc}")
        return False

    sent.add(key)
    config._ui_emails_sent = sent
    print(f"email report sent for {label} -> {', '.join(settings.EMAIL_TO)}")
    return True
