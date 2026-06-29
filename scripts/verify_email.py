"""验证 Jenkins / 本机邮件配置是否可用。"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from utils.email_config import email_config_from_settings, mask_recipient, write_email_audit
from utils.email_report import send_pytest_email_report


def main() -> int:
    config = email_config_from_settings()
    try:
        config.validate()
    except ValueError as exc:
        print(f"email config invalid: {exc}")
        return 1

    masked = ", ".join(mask_recipient(item) for item in config.recipients)
    print(f"smtp_host={config.smtp_host}:{config.smtp_port}")
    print(f"sender={config.sender}")
    print(f"recipients({len(config.recipients)})={masked}")

    summary = {
        "exitstatus": 0,
        "started_at": "",
        "finished_at": "",
        "duration_seconds": 0,
        "stats": {"passed": 1, "failed": 0, "skipped": 0},
        "report_label": "邮件配置自检",
    }
    try:
        subject = send_pytest_email_report(
            config,
            summary,
            [],
            body="这是一封 Pyautotest 邮件配置自检，收到说明 SMTP 与收件人配置正确。",
        )
    except Exception as exc:
        write_email_audit(
            status="failed",
            label="邮件配置自检",
            subject="",
            recipients=config.recipients,
            error=str(exc),
        )
        print(f"send failed: {exc}")
        return 1

    audit = write_email_audit(
        status="sent",
        label="邮件配置自检",
        subject=subject,
        recipients=config.recipients,
    )
    print(f"send ok: {subject}")
    print(f"audit: {audit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
