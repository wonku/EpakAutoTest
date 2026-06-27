import json
import base64
from datetime import datetime, timezone
from pathlib import Path

import pytest
import allure
from playwright.sync_api import sync_playwright

from config import settings
from api.client import ApiClient
from api.data_factory import DataFactory
from api.services.auth_service import AuthService
from api.services.crm_lead_service import CrmLeadService
from config.settings import (
    API_TIMEOUT_SECONDS,
    APP_HOME_URL,
    BROWSER_EXECUTABLE_PATH,
    HEADLESS,
    LOGIN_PASSWORD_ENCRYPTED,
    LOGIN_PHONE,
    SLOW_MO,
)
from utils.email_report import (
    EmailReportConfig,
    build_ui_inspection_email_body,
    latest_mobile_attachments,
    send_pytest_email_report,
)
from utils.esbao_ui_report import ui_report_attachments
from utils.ui_report_email import send_ui_report_email


def pytest_addoption(parser):
    parser.addoption(
        "--email-report",
        action="store_true",
        default=False,
        help="Send email report after pytest session finishes.",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "esbao: 易食包生产环境商城 UI 巡检")
    config.addinivalue_line("markers", "epak: EPAK 英文站生产环境商城 UI 巡检")
    config.addinivalue_line("markers", "api_negative: CRM 接口异常与边界场景")
    config._login_benchmark_times = []
    config._session_started_at = datetime.now(timezone.utc)
    config._test_stats = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
    config._esbao_ui_report_path = ""
    config._epak_ui_report_path = ""
    config._ui_emails_sent = set()


@pytest.fixture(scope="session")
def playwright_instance():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="function")
def page(playwright_instance):
    launch_kwargs = {"headless": HEADLESS, "slow_mo": SLOW_MO}
    if BROWSER_EXECUTABLE_PATH:
        launch_kwargs["executable_path"] = BROWSER_EXECUTABLE_PATH
    browser = playwright_instance.chromium.launch(**launch_kwargs)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    yield page
    context.close()
    browser.close()


def _build_linkseeks_auth(login_data: dict) -> dict:
    service_type_code = login_data.get("serviceTypeCode")
    member_id = login_data.get("memberId")
    upstream = "1" if service_type_code == 2 or (service_type_code == 3 and member_id == 6) else "0"
    return {
        "userId": login_data.get("userId"),
        "memberId": member_id,
        "token": login_data.get("token"),
        "name": login_data.get("name"),
        "logo": login_data.get("logo"),
        "level": login_data.get("level"),
        "phone": login_data.get("phone") or login_data.get("account"),
        "levelTag": login_data.get("levelTag"),
        "score": login_data.get("score") or 0,
        "creditPoint": login_data.get("creditPoint") or 0,
        "memberRoleType": login_data.get("memberRoleType"),
        "memberRoleId": login_data.get("memberRoleId"),
        "memberType": login_data.get("memberType"),
        "locales": login_data.get("locales"),
        "roles": login_data.get("roles") or [],
        "validateStatus": login_data.get("validateStatus"),
        "validateStatusDesc": login_data.get("validateStatusDesc"),
        "companyList": login_data.get("multiMemberBOS"),
        "supplierId": login_data.get("supplierId"),
        "company": login_data.get("company"),
        "serviceTypeCode": service_type_code,
        "buyerRegisterStatus": login_data.get("buyerRegisterStatus"),
        "dealerRegisterStatus": login_data.get("dealerRegisterStatus"),
        "temporarilyType": login_data.get("temporarilyType"),
        "upstream": upstream,
    }


@pytest.fixture(scope="session")
def auth_service() -> AuthService:
    return AuthService(ApiClient(timeout=API_TIMEOUT_SECONDS))


@pytest.fixture(scope="session")
def auth_login_data(auth_service) -> dict:
    return auth_service.login_with_encrypted_password(LOGIN_PHONE, LOGIN_PASSWORD_ENCRYPTED)


@pytest.fixture(scope="session")
def auth_token(auth_login_data) -> str:
    return auth_login_data["token"]


@pytest.fixture(scope="session")
def api_client(auth_token) -> ApiClient:
    client = ApiClient(
        timeout=API_TIMEOUT_SECONDS,
        default_headers={"Authorization": auth_token, "token": auth_token},
    )
    return client


@pytest.fixture(scope="session")
def data_factory(api_client) -> DataFactory:
    return DataFactory(api_client)


@pytest.fixture(scope="session")
def crm_lead_service(api_client) -> CrmLeadService:
    return CrmLeadService(api_client)


@pytest.fixture(scope="function")
def authenticated_page(page, auth_token, auth_login_data):
    token_literal = json.dumps(auth_token)
    login_data_literal = json.dumps(auth_login_data, ensure_ascii=False)
    linkseeks_auth_obj = _build_linkseeks_auth(auth_login_data)
    linkseeks_auth_str = json.dumps(linkseeks_auth_obj, ensure_ascii=False, separators=(",", ":"))
    linkseeks_auth_b64 = base64.b64encode(linkseeks_auth_str.encode("utf-8")).decode("utf-8")
    linkseeks_auth_literal = json.dumps(linkseeks_auth_b64)
    page.add_init_script(
        f"""
        () => {{
          const token = {token_literal};
          const loginData = {login_data_literal};
          const linkseeksAuth = {linkseeks_auth_literal};
          const keys = ["token", "access_token", "accessToken", "Authorization", "member_token"];
          keys.forEach((k) => window.localStorage.setItem(k, token));
          window.localStorage.setItem("isLogin", "true");
          window.localStorage.setItem("loginStatus", "1");
          window.localStorage.setItem("userInfo", JSON.stringify(loginData));
          window.localStorage.setItem("memberInfo", JSON.stringify(loginData));
          window.localStorage.setItem("loginUser", JSON.stringify(loginData));
          window.localStorage.setItem("account", loginData.account || "");
          window.localStorage.setItem("Linkseeks_AUTH", linkseeksAuth);
        }}
        """,
    )
    page.context.set_extra_http_headers({"Authorization": auth_token, "token": auth_token})
    page.context.add_cookies(
        [
            {"name": "token", "value": auth_token, "domain": ".ysbpack.com", "path": "/"},
            {"name": "Authorization", "value": auth_token, "domain": ".ysbpack.com", "path": "/"},
            {"name": "member_token", "value": auth_token, "domain": ".ysbpack.com", "path": "/"},
            {"name": "Linkseeks_AUTH", "value": linkseeks_auth_b64, "domain": ".ysbpack.com", "path": "/"},
        ]
    )
    yield page


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
        _send_email_report(summary_path, session, exitstatus)


def _write_test_summary(session, exitstatus) -> Path:
    started_at = getattr(session.config, "_session_started_at", datetime.now(timezone.utc))
    finished_at = datetime.now(timezone.utc)
    summary_path = Path("reports/test-summary-last.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "exitstatus": exitstatus,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "stats": getattr(session.config, "_test_stats", {}),
        "report_dir": str(Path(settings.MONKEY_REPORT_DIR)),
        "allure_results_dir": str(Path("reports/allure-results")),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_path


def _send_email_report(summary_path: Path, session, exitstatus) -> None:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    config = EmailReportConfig(
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
    ui_reports = _load_ui_inspection_reports(session.config)
    if ui_reports:
        for label, report in ui_reports:
            report_dir = Path(report.get("report_dir", ""))
            report_path = report_dir / "report.json"
            send_ui_report_email(session.config, label, report_path)
        return

    attachments = latest_mobile_attachments(
        Path(settings.MONKEY_REPORT_DIR),
        Path(settings.APPIUM_REPORT_DIR),
        summary_path,
    )
    try:
        send_pytest_email_report(config, summary, attachments)
    except Exception as exc:
        print(f"email report was not sent: {exc}")


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
