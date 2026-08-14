from __future__ import annotations

from dataclasses import dataclass

import pytest
from playwright.sync_api import sync_playwright

from config import settings
from config.settings import (
    BROWSER_EXECUTABLE_PATH,
    CRM_NAV_TIMEOUT_MS,
    ESB_UI_HEADLESS,
    ESB_UI_VIEWPORT_HEIGHT,
    ESB_UI_VIEWPORT_WIDTH,
    HEADLESS,
    SLOW_MO,
    UI_BROWSER,
    UI_BROWSERS,
)

SUPPORTED_UI_BROWSERS = frozenset({"chromium", "firefox", "webkit", "chrome", "msedge"})


@dataclass(frozen=True)
class BrowserProfile:
    headless: bool
    viewport_width: int
    viewport_height: int


BROWSER_PROFILES = {
    "crm": BrowserProfile(headless=HEADLESS, viewport_width=1440, viewport_height=900),
    "mall_ui": BrowserProfile(
        headless=ESB_UI_HEADLESS,
        viewport_width=ESB_UI_VIEWPORT_WIDTH,
        viewport_height=ESB_UI_VIEWPORT_HEIGHT,
    ),
}


def _normalize_browser_name(name: str) -> str:
    normalized = (name or "").strip().lower()
    if normalized not in SUPPORTED_UI_BROWSERS:
        supported = ", ".join(sorted(SUPPORTED_UI_BROWSERS))
        raise pytest.UsageError(f"不支持的 UI 浏览器 '{name}'，可选: {supported}")
    return normalized


def resolve_ui_browser_list(config=None) -> list[str]:
    """解析本次会话要跑的浏览器列表。

    优先级: --ui-browsers > --ui-browser > 环境变量 UI_BROWSERS > UI_BROWSER
    默认仅 chromium，用例数量与历史一致。
    """
    if config is not None:
        cli_browsers = config.getoption("--ui-browsers", default=None)
        if cli_browsers:
            names = [item.strip() for item in str(cli_browsers).split(",") if item.strip()]
            return [_normalize_browser_name(name) for name in names]
        cli_browser = config.getoption("--ui-browser", default=None)
        if cli_browser:
            return [_normalize_browser_name(str(cli_browser))]
    if UI_BROWSERS:
        return [_normalize_browser_name(name) for name in UI_BROWSERS]
    return [_normalize_browser_name(UI_BROWSER)]


def pytest_addoption(parser):
    group = parser.getgroup("ui-browser")
    group.addoption(
        "--ui-browser",
        action="store",
        default=None,
        help="单浏览器覆盖（chromium|firefox|webkit|chrome|msedge）。默认沿用 UI_BROWSER/chromium。",
    )
    group.addoption(
        "--ui-browsers",
        action="store",
        default=None,
        help="多浏览器兼容矩阵，逗号分隔。仅显式传入时才会复制用例；日常不设则行为不变。",
    )


def pytest_generate_tests(metafunc):
    """仅当解析出多个浏览器时才参数化，避免默认跑法改变用例 node id。"""
    if "browser_name" not in metafunc.fixturenames:
        return
    browsers = resolve_ui_browser_list(metafunc.config)
    if len(browsers) <= 1:
        return
    metafunc.parametrize("browser_name", browsers, ids=browsers)


@pytest.fixture(scope="session")
def playwright_instance():
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture(scope="function")
def browser_name(request) -> str:
    if hasattr(request, "param"):
        return _normalize_browser_name(request.param)
    return resolve_ui_browser_list(request.config)[0]


def _launch_browser(playwright_instance, browser_name: str, launch_kwargs: dict):
    """按引擎启动浏览器；chromium 默认路径与历史行为一致。"""
    name = _normalize_browser_name(browser_name)
    kwargs = dict(launch_kwargs)

    if name in {"firefox", "webkit"}:
        # 自定义 Chrome 路径不适用于其它引擎
        engine = getattr(playwright_instance, name)
        return engine.launch(**kwargs)

    if name in {"chrome", "msedge"}:
        if BROWSER_EXECUTABLE_PATH and name == "chrome":
            kwargs["executable_path"] = BROWSER_EXECUTABLE_PATH
        else:
            kwargs["channel"] = name
        return playwright_instance.chromium.launch(**kwargs)

    # chromium（默认）：保留 BROWSER_EXECUTABLE_PATH 行为
    if BROWSER_EXECUTABLE_PATH:
        kwargs["executable_path"] = BROWSER_EXECUTABLE_PATH
    return playwright_instance.chromium.launch(**kwargs)


def _launch_page(
    playwright_instance,
    profile: BrowserProfile,
    *,
    browser_name: str = "chromium",
    mall_ui: bool = False,
):
    launch_kwargs = {"headless": profile.headless, "slow_mo": SLOW_MO}
    browser = _launch_browser(playwright_instance, browser_name, launch_kwargs)
    context_kwargs = {
        "viewport": {"width": profile.viewport_width, "height": profile.viewport_height},
    }
    if mall_ui:
        context_kwargs.update(
            {
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "locale": "en-US",
            }
        )
    context = browser.new_context(**context_kwargs)
    if mall_ui:
        context.set_default_navigation_timeout(settings.MALL_UI_NAV_TIMEOUT_MS)
        context.set_default_timeout(max(settings.MALL_UI_NAV_TIMEOUT_MS // 2, 30000))
    else:
        context.set_default_navigation_timeout(CRM_NAV_TIMEOUT_MS)
        context.set_default_timeout(max(CRM_NAV_TIMEOUT_MS // 2, 30000))
    page = context.new_page()
    return browser, context, page


@pytest.fixture(scope="function")
def page(playwright_instance, browser_name):
    try:
        import allure

        allure.dynamic.tag(f"browser:{browser_name}")
        allure.dynamic.parameter("ui_browser", browser_name)
    except Exception:  # noqa: BLE001
        pass
    browser, context, page = _launch_page(
        playwright_instance,
        BROWSER_PROFILES["crm"],
        browser_name=browser_name,
    )
    yield page
    context.close()
    browser.close()


@pytest.fixture(scope="function")
def mall_ui_page(playwright_instance):
    # 商城巡检保持固定 chromium，不受 CRM 兼容矩阵影响
    browser, context, page = _launch_page(
        playwright_instance,
        BROWSER_PROFILES["mall_ui"],
        browser_name="chromium",
        mall_ui=True,
    )
    yield page
    for open_page in list(context.pages):
        try:
            open_page.close()
        except Exception:
            pass
    try:
        context.close()
    except Exception:
        pass
    try:
        browser.close()
    except Exception:
        pass
