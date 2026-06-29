from __future__ import annotations

from dataclasses import dataclass

import pytest
from playwright.sync_api import sync_playwright

from config import settings
from config.settings import (
    BROWSER_EXECUTABLE_PATH,
    ESB_UI_HEADLESS,
    ESB_UI_VIEWPORT_HEIGHT,
    ESB_UI_VIEWPORT_WIDTH,
    HEADLESS,
    SLOW_MO,
)


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


@pytest.fixture(scope="session")
def playwright_instance():
    with sync_playwright() as playwright:
        yield playwright


def _launch_page(playwright_instance, profile: BrowserProfile, *, mall_ui: bool = False):
    launch_kwargs = {"headless": profile.headless, "slow_mo": SLOW_MO}
    if BROWSER_EXECUTABLE_PATH:
        launch_kwargs["executable_path"] = BROWSER_EXECUTABLE_PATH
    browser = playwright_instance.chromium.launch(**launch_kwargs)
    context = browser.new_context(
        viewport={"width": profile.viewport_width, "height": profile.viewport_height}
    )
    if mall_ui:
        context.set_default_navigation_timeout(settings.MALL_UI_NAV_TIMEOUT_MS)
        context.set_default_timeout(max(settings.MALL_UI_NAV_TIMEOUT_MS // 2, 30000))
    page = context.new_page()
    return browser, context, page


@pytest.fixture(scope="function")
def page(playwright_instance):
    browser, context, page = _launch_page(playwright_instance, BROWSER_PROFILES["crm"])
    yield page
    context.close()
    browser.close()


@pytest.fixture(scope="function")
def mall_ui_page(playwright_instance):
    browser, context, page = _launch_page(
        playwright_instance,
        BROWSER_PROFILES["mall_ui"],
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
