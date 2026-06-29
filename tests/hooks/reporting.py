from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import allure
import pytest

from config import settings
from utils.email_report import latest_api_attachments, latest_mobile_attachments, send_pytest_email_report
from utils.email_config import email_config_from_settings
from utils.ui_report_email import send_ui_report_email


def pytest_addoption(parser):
    parser.addoption(
        "--email-report",
        action="store_true",
        default=False,
        help="Send email report after pytest session finishes.",
    )
    parser.addoption(
        "--report-label",
        action="store",
        default=None,
        help="Email report subject label (e.g. 'CRM API 回归'). Auto-detected if omitted.",
    )


def pytest_configure(config):
    config._login_benchmark_times = []
    config._session_started_at = datetime.now(timezone.utc)
    config._test_stats = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
    config._esbao_ui_report_path = ""
    config._epak_ui_report_path = ""
    config._ui_emails_sent = set()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        stats = getattr(item.config, "_test_stats", None)
        if stats is not None:
            if report.passed:
                stats["passed"] += 1
            elif report.failed:
                stats["failed"] += 1
            elif report.skipped:
                stats["skipped"] += 1

    if report.when != "call" or report.passed:
        return

    page = item.funcargs.get("page")
    if page is None:
        return

    png_bytes = page.screenshot(full_page=True)
    allure.attach(
        png_bytes,
        name=f"{item.name}_failed",
        attachment_type=allure.attachment_type.PNG,
    )


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    summary_path = Path("reports/test-summary-last.json")
    if summary_path.exists():
        terminalreporter.write_sep("=", "test session summary")
        terminalreporter.write_line(f"summary: {summary_path}")
        terminalreporter.write_line(f"exitstatus: {exitstatus}")

    times = getattr(config, "_login_benchmark_times", None)
    if not times:
        return
    avg = sum(times) / len(times)
    mn, mx = min(times), max(times)
    terminalreporter.write_sep("=", "login_benchmark (test_login_benchmark.py)")
    terminalreporter.write_line(
        f"n={len(times)} total={sum(times):.1f}s "
        f"avg={avg:.2f}s min={mn:.2f}s max={mx:.2f}s"
    )


def pytest_sessionfinish(session, exitstatus):
    times = getattr(session.config, "_login_benchmark_times", None)
    if times:
        avg = sum(times) / len(times)
        mn, mx = min(times), max(times)
        out = Path("reports/benchmark-last.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "runs": len(times),
                    "total_seconds": round(sum(times), 3),
                    "avg_seconds": round(avg, 3),
                    "min_seconds": round(mn, 3),
                    "max_seconds": round(mx, 3),
                    "each_seconds": [round(t, 3) for t in times],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    summary_path = _write_test_summary(session, exitstatus)
    if settings.EMAIL_REPORT_ENABLED or session.config.getoption("--email-report"):
        _send_email_report(summary_path, session)


def _normalize_nodeid(nodeid: str) -> str:
    return nodeid.replace("\\", "/")


def _infer_report_context(session) -> dict:
    cli_label = session.config.getoption("--report-label")
    if cli_label:
        return {
            "report_label": cli_label.strip(),
            "report_kind": "custom",
            "report_dir": "reports",
        }
    if settings.EMAIL_REPORT_LABEL:
        return {
            "report_label": settings.EMAIL_REPORT_LABEL,
            "report_kind": "custom",
            "report_dir": "reports",
        }

    nodeids = [_normalize_nodeid(item.nodeid) for item in getattr(session, "items", [])]
    api_tests = [nodeid for nodeid in nodeids if "/test_api_" in nodeid]
    monkey_tests = [nodeid for nodeid in nodeids if "test_monkey" in nodeid]
    appium_tests = [nodeid for nodeid in nodeids if "test_appium" in nodeid]

    if api_tests and not monkey_tests and not appium_tests:
        return {
            "report_label": "CRM API 回归",
            "report_kind": "api",
            "report_dir": "reports/junit",
        }
    if monkey_tests:
        return {
            "report_label": "Monkey Test",
            "report_kind": "monkey",
            "report_dir": str(Path(settings.MONKEY_REPORT_DIR)),
        }
    if appium_tests:
        return {
            "report_label": "Appium Explore",
            "report_kind": "appium",
            "report_dir": str(Path(settings.APPIUM_REPORT_DIR)),
        }
    return {
        "report_label": "Pytest",
        "report_kind": "generic",
        "report_dir": "reports",
    }


def _write_test_summary(session, exitstatus) -> Path:
    started_at = getattr(session.config, "_session_started_at", datetime.now(timezone.utc))
    finished_at = datetime.now(timezone.utc)
    report_context = _infer_report_context(session)
    summary_path = Path("reports/test-summary-last.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "exitstatus": exitstatus,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "stats": getattr(session.config, "_test_stats", {}),
        "report_label": report_context["report_label"],
        "report_kind": report_context["report_kind"],
        "report_dir": report_context["report_dir"],
        "allure_results_dir": str(Path("reports/allure-results")),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_path


def _load_ui_report_from_path(report_path: str) -> dict | None:
    if not report_path:
        return None
    path = Path(report_path)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    data["report_dir"] = str(path.parent.resolve())
    return data


def _load_ui_inspection_reports(config) -> list[tuple[str, dict]]:
    reports: list[tuple[str, dict]] = []
    esbao_report = _load_ui_report_from_path(getattr(config, "_esbao_ui_report_path", ""))
    if esbao_report is not None:
        reports.append(("易食包商城", esbao_report))
    epak_report = _load_ui_report_from_path(getattr(config, "_epak_ui_report_path", ""))
    if epak_report is not None:
        reports.append(("EPAK 英文商城", epak_report))
    return reports


def _send_email_report(summary_path: Path, session) -> None:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    config = email_config_from_settings()
    ui_reports = _load_ui_inspection_reports(session.config)
    if ui_reports:
        for label, report in ui_reports:
            report_dir = Path(report.get("report_dir", ""))
            report_path = report_dir / "report.json"
            send_ui_report_email(session.config, label, report_path)
        return

    report_kind = summary.get("report_kind", "")
    if report_kind == "api":
        attachments = latest_api_attachments(summary_path)
    elif report_kind in {"monkey", "appium", "mobile"}:
        attachments = latest_mobile_attachments(
            Path(settings.MONKEY_REPORT_DIR),
            Path(settings.APPIUM_REPORT_DIR),
            summary_path,
        )
    else:
        attachments = [summary_path]

    try:
        send_pytest_email_report(config, summary, attachments)
    except Exception as exc:
        from utils.email_config import write_email_audit

        write_email_audit(
            status="failed",
            label=summary.get("report_label", "Pytest"),
            subject="",
            recipients=config.recipients,
            error=str(exc),
        )
        print(f"email report was not sent: {exc}")
