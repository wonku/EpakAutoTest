"""外呼手机号保活：按账号依次登录并对外呼线索发起呼叫。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.auth_service import AuthService
from api.services.outbound_call_service import OutboundCallService
from config.settings import (
    API_TIMEOUT_SECONDS,
    EMAIL_REPORT_ENABLED,
    OUTBOUND_KEEPALIVE_ACCOUNT_INTERVAL_SECONDS,
    OUTBOUND_KEEPALIVE_CASES,
    OUTBOUND_KEEPALIVE_PASSWORD_ENCRYPTED,
    OUTBOUND_KEEPALIVE_REPORT_DIR,
)
from utils.email_config import email_config_from_settings, mask_recipient, write_email_audit
from utils.email_report import send_pytest_email_report


@dataclass
class KeepaliveStepResult:
    account: str
    success: bool
    relation_id: int | None = None
    user_id: int | None = None
    member_id: int | None = None
    call_response: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class KeepaliveReport:
    started_at: str
    finished_at: str | None = None
    success: bool = False
    steps: list[KeepaliveStepResult] = field(default_factory=list)


def _run_case(
    *,
    auth_service: AuthService,
    outbound_service: OutboundCallService,
    account: str,
    password_encrypted: str,
    relation_id: int | None,
) -> KeepaliveStepResult:
    step = KeepaliveStepResult(account=account, success=False)
    try:
        login_data = auth_service.login_with_encrypted_password(account, password_encrypted)
        ctx = AuthContext.from_login_data(login_data)
        step.user_id = ctx.user_id
        step.member_id = ctx.member_id
        resolved_relation_id = outbound_service.resolve_relation_id(ctx, relation_id)
        step.relation_id = resolved_relation_id
        step.call_response = outbound_service.call_phone(ctx, relation_id=resolved_relation_id)
        step.success = True
        print(
            f"[OK] account={account} userId={ctx.user_id} "
            f"relationId={resolved_relation_id} response={step.call_response}"
        )
    except Exception as exc:
        step.error = str(exc)
        print(f"[FAIL] account={account} error={exc}", file=sys.stderr)
    return step


def main(send_email: bool = False) -> int:
    if not OUTBOUND_KEEPALIVE_PASSWORD_ENCRYPTED:
        print("请配置 OUTBOUND_KEEPALIVE_PASSWORD_ENCRYPTED", file=sys.stderr)
        return 2

    cases = OUTBOUND_KEEPALIVE_CASES
    if not cases:
        print("请配置 OUTBOUND_KEEPALIVE_CASES", file=sys.stderr)
        return 2

    report = KeepaliveReport(started_at=datetime.now().isoformat(timespec="seconds"))
    auth_service = AuthService(ApiClient(timeout=API_TIMEOUT_SECONDS))
    outbound_service = OutboundCallService(ApiClient(timeout=API_TIMEOUT_SECONDS))

    for index, case in enumerate(cases):
        account = str(case["account"])
        relation_id = case.get("relation_id")
        if relation_id is not None:
            relation_id = int(relation_id)
        password_encrypted = str(case.get("password_encrypted") or OUTBOUND_KEEPALIVE_PASSWORD_ENCRYPTED)

        report.steps.append(
            _run_case(
                auth_service=auth_service,
                outbound_service=outbound_service,
                account=account,
                password_encrypted=password_encrypted,
                relation_id=relation_id,
            )
        )

        if index < len(cases) - 1:
            wait_seconds = OUTBOUND_KEEPALIVE_ACCOUNT_INTERVAL_SECONDS
            print(f"等待 {wait_seconds} 秒后处理下一个账号...")
            time.sleep(wait_seconds)

    report.finished_at = datetime.now().isoformat(timespec="seconds")
    report.success = all(step.success for step in report.steps)

    report_dir = Path(OUTBOUND_KEEPALIVE_REPORT_DIR) / datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "started_at": report.started_at,
                "finished_at": report.finished_at,
                "success": report.success,
                "steps": [asdict(step) for step in report.steps],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"报告已写入: {report_path}")

    if send_email:
        _maybe_send_email(report, report_path, success=report.success)

    return 0 if report.success else 1


def _maybe_send_email(report: KeepaliveReport, report_path: Path, *, success: bool) -> None:
    try:
        config = email_config_from_settings()
        body_lines = [
            f"外呼保活任务 {'成功' if success else '失败'}",
            f"开始: {report.started_at}",
            f"结束: {report.finished_at}",
            "",
        ]
        for step in report.steps:
            status = "OK" if step.success else "FAIL"
            body_lines.append(
                f"- [{status}] {step.account} relationId={step.relation_id} "
                f"userId={step.user_id} error={step.error or ''}"
            )
        summary = {
            "exitstatus": 0 if success else 1,
            "report_label": "OutboundKeepalive",
            "email_body": "\n".join(body_lines),
        }
        subject = send_pytest_email_report(
            config,
            summary,
            [report_path],
            report_label="OutboundKeepalive",
        )
        write_email_audit(
            status="sent",
            label="OutboundKeepalive",
            subject=subject,
            recipients=[mask_recipient(r) for r in config.recipients],
            attachment_count=1,
        )
        print(f"邮件已发送: {subject}")
    except Exception as exc:
        write_email_audit(
            status="failed",
            label="OutboundKeepalive",
            subject="",
            recipients=[],
            error=str(exc),
        )
        print(f"邮件发送失败: {exc}", file=sys.stderr)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="外呼手机号保活任务")
    parser.add_argument(
        "--email-report",
        action="store_true",
        help="执行结束后发送邮件（或设置 EMAIL_REPORT_ENABLED=true）",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    send_email = args.email_report or EMAIL_REPORT_ENABLED
    raise SystemExit(main(send_email=send_email))
