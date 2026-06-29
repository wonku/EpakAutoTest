from __future__ import annotations

import mimetypes
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path


@dataclass(frozen=True)
class EmailReportConfig:
    smtp_host: str
    smtp_port: int
    smtp_ssl: bool
    smtp_starttls: bool
    username: str
    password: str
    sender: str
    recipients: list[str]
    subject_prefix: str
    attach_logs: bool
    max_attachment_mb: int

    def validate(self) -> None:
        missing = []
        if not self.smtp_host:
            missing.append("EMAIL_SMTP_HOST")
        if not self.sender:
            missing.append("EMAIL_FROM or EMAIL_USERNAME")
        if not self.recipients:
            missing.append("EMAIL_TO")
        if self.username and not self.password:
            missing.append("EMAIL_PASSWORD")
        if missing:
            raise ValueError("missing email config: " + ", ".join(missing))


def send_pytest_email_report(
    config: EmailReportConfig,
    summary: dict,
    attachments: list[Path],
    *,
    report_label: str | None = None,
    body: str | None = None,
) -> str:
    config.validate()

    status = "PASS" if summary.get("exitstatus") == 0 else "FAIL"
    raw_label = report_label or summary.get("report_label") or "Pytest"
    from utils.email_config import resolve_email_subject_label

    label = resolve_email_subject_label(raw_label.replace("UI巡检", "").strip() or raw_label)
    subject = f"{config.subject_prefix} {label} {status}"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.sender
    msg["To"] = ", ".join(config.recipients)
    msg.set_content(body or summary.get("email_body") or _build_body(summary))

    attached = 0
    if config.attach_logs:
        for path in attachments:
            if path.exists() and path.is_file():
                max_bytes = config.max_attachment_mb * 1024 * 1024
                if path.stat().st_size <= max_bytes:
                    attached += 1
            _attach_file(msg, path, config.max_attachment_mb)

    if config.smtp_ssl:
        with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=30) as smtp:
            _login_if_needed(smtp, config)
            rejected = smtp.send_message(msg)
    else:
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as smtp:
            if config.smtp_starttls:
                smtp.starttls()
            _login_if_needed(smtp, config)
            rejected = smtp.send_message(msg)

    if rejected:
        raise RuntimeError(f"SMTP rejected recipients: {rejected}")
    return subject


def latest_monkey_attachments(monkey_report_dir: Path, summary_path: Path) -> list[Path]:
    attachments = [summary_path]
    latest_dir = _latest_child_dir(monkey_report_dir)
    if latest_dir is None:
        return [path for path in attachments if path.exists()]

    for name in ("device-info.txt", "monkey.log", "logcat.txt", "inspection-summary.json"):
        path = latest_dir / name
        if path.exists():
            attachments.append(path)
    screenshots_dir = latest_dir / "screenshots"
    if screenshots_dir.exists():
        issue_screenshots = _issue_screenshots_from_summary(latest_dir / "inspection-summary.json")
        for path in issue_screenshots[:5]:
            if path.exists():
                attachments.append(path)
    return attachments


def latest_appium_attachments(appium_report_dir: Path, summary_path: Path) -> list[Path]:
    attachments = [summary_path]
    latest_dir = _latest_child_dir(appium_report_dir)
    if latest_dir is None:
        return [path for path in attachments if path.exists()]

    for name in ("explore-summary.json", "explore.log"):
        path = latest_dir / name
        if path.exists():
            attachments.append(path)

    issues_dir = latest_dir / "issues"
    if issues_dir.exists():
        for name in ("issue-summary.txt", "issue-context.json"):
            path = issues_dir / name
            if path.exists():
                attachments.append(path)
        for path in sorted(issues_dir.glob("*.png"))[:5]:
            attachments.append(path)

    issue_screenshots = _issue_screenshots_from_summary(latest_dir / "explore-summary.json")
    for path in issue_screenshots[:5]:
        if path.exists():
            attachments.append(path)
    return attachments


def latest_api_attachments(summary_path: Path, junit_dir: Path | None = None) -> list[Path]:
    attachments = [summary_path]
    junit_root = junit_dir or Path("reports/junit")
    if junit_root.exists():
        for path in sorted(junit_root.glob("*.xml"), key=lambda item: item.stat().st_mtime, reverse=True):
            attachments.append(path)
            break
    return [path for path in attachments if path.exists()]


def latest_mobile_attachments(
    monkey_report_dir: Path,
    appium_report_dir: Path,
    summary_path: Path,
) -> list[Path]:
    attachments: list[Path] = []
    seen: set[str] = set()
    for path in latest_monkey_attachments(monkey_report_dir, summary_path):
        key = str(path.resolve())
        if key not in seen and path.exists():
            seen.add(key)
            attachments.append(path)
    for path in latest_appium_attachments(appium_report_dir, summary_path):
        key = str(path.resolve())
        if key not in seen and path.exists():
            seen.add(key)
            attachments.append(path)
    return attachments


def build_ui_inspection_email_body(
    reports: list[tuple[str, dict]],
    pytest_summary: dict,
) -> str:
    stats = pytest_summary.get("stats", {})
    lines = ["商城 UI 巡检已执行完成。", ""]
    for label, report in reports:
        lines.extend(_format_ui_report_section(label, report))
        lines.append("")
    lines.extend(
        [
            "Pytest 统计:",
            f"- passed: {stats.get('passed', 0)}",
            f"- failed: {stats.get('failed', 0)}",
            f"- skipped: {stats.get('skipped', 0)}",
            "",
            "邮件附件包含本次巡检截图与 report.json。",
        ]
    )
    return "\n".join(lines)


def build_esbao_email_body(esbao_report: dict, pytest_summary: dict) -> str:
    return build_ui_inspection_email_body([("易食包商城", esbao_report)], pytest_summary)


def _format_ui_report_section(label: str, report: dict) -> list[str]:
    steps = report.get("steps", [])
    checks = report.get("checks", {})
    homepage = checks.get("homepage", {})
    product = checks.get("product_detail", {})
    lines = [
        f"=== {label} ===",
        f"巡检状态: {report.get('status', 'UNKNOWN')}",
        f"开始时间: {report.get('started_at', '')}",
        f"结束时间: {report.get('finished_at', '')}",
        f"耗时: {report.get('duration_seconds', 0)} 秒",
        "",
        "执行步骤:",
    ]
    for step in steps:
        lines.append(f"- [{step.get('status', '')}] {step.get('name', '')}")
    if report.get("error"):
        lines.extend(["", f"失败原因: {report['error']}"])
    if homepage:
        image_stats = homepage.get("image_stats", {})
        lines.extend(
            [
                "",
                "首页检查:",
                f"- 页面高度: {homepage.get('scroll_height', '')}",
                f"- 可见图片: {image_stats.get('visible', '')}",
                f"- 失败图片: {image_stats.get('broken', 0)}",
            ]
        )
    if product:
        lines.extend(
            [
                "",
                "商品详情检查:",
                f"- 点击商品: {product.get('clicked_product', '')}",
                f"- 详情页 URL: {product.get('url', '')}",
                f"- 页面标题: {product.get('title', '')}",
            ]
        )
    lines.append(f"报告目录: {report.get('report_dir', '')}")
    return lines


def _report_intro(summary: dict) -> str:
    kind = summary.get("report_kind", "")
    if kind == "api":
        return "CRM API 自动化回归已执行完成。"
    if kind in {"monkey", "appium", "mobile"}:
        return "移动端自动化测试已执行完成。"
    return "自动化测试已执行完成。"


def _build_body(summary: dict) -> str:
    stats = summary.get("stats", {})
    lines = [
        _report_intro(summary),
        "",
        f"状态: {'通过' if summary.get('exitstatus') == 0 else '失败'}",
        f"开始时间: {summary.get('started_at', '')}",
        f"结束时间: {summary.get('finished_at', '')}",
        f"耗时: {summary.get('duration_seconds', 0)} 秒",
        "",
        "用例统计:",
        f"- passed: {stats.get('passed', 0)}",
        f"- failed: {stats.get('failed', 0)}",
        f"- skipped: {stats.get('skipped', 0)}",
        f"- error: {stats.get('error', 0)}",
        "",
        f"报告目录: {summary.get('report_dir', '')}",
        f"Allure 结果: {summary.get('allure_results_dir', '')}",
    ]
    return "\n".join(lines)


def _attach_file(msg: EmailMessage, path: Path, max_attachment_mb: int) -> None:
    if not path.exists() or not path.is_file():
        return
    max_bytes = max_attachment_mb * 1024 * 1024
    if path.stat().st_size > max_bytes:
        return
    content_type, _ = mimetypes.guess_type(path.name)
    maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
    msg.add_attachment(
        path.read_bytes(),
        maintype=maintype,
        subtype=subtype,
        filename=path.name,
    )


def _login_if_needed(smtp: smtplib.SMTP, config: EmailReportConfig) -> None:
    if config.username:
        smtp.login(config.username, config.password)


def _latest_child_dir(parent: Path) -> Path | None:
    if not parent.exists():
        return None
    dirs = [path for path in parent.iterdir() if path.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda path: path.stat().st_mtime)


def _issue_screenshots_from_summary(summary_path: Path) -> list[Path]:
    if not summary_path.exists():
        return []
    try:
        import json

        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [Path(item) for item in data.get("issue_screenshots", [])]
