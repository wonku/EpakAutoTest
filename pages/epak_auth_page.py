from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config import settings
from pages.mall.base import MallAuthPageBase
from pages.mall.navigation import wait_for_mall_home_ready


class EpakAuthPage(MallAuthPageBase):
    logo_selector = ".lingxi-business-logo"
    LOGO_SELECTORS = (
        ".lingxi-business-logo",
        "img.lingxi-business-logo",
        '[class*="logo"] img',
        "header img",
    )
    WELCOME_TEXT = "Welcome to EPAK GROUP!"

    def _wait_for_login_page_ready(self) -> None:
        timeout = settings.MALL_UI_AUTH_READY_TIMEOUT_MS
        self.page.wait_for_function(
            """(text) => (document.body?.innerText || '').includes(text)""",
            arg=self.WELCOME_TEXT,
            timeout=timeout,
        )
        for selector in self.LOGO_SELECTORS:
            locator = self.page.locator(selector).first
            if locator.count() == 0:
                continue
            try:
                locator.wait_for(state="visible", timeout=15000)
                self.logo_selector = selector
                return
            except PlaywrightTimeoutError:
                continue

    def assert_login_page_loaded(self) -> None:
        assert self.WELCOME_TEXT in self.page.content(), "登录页未出现 Welcome to EPAK GROUP!"
        logo_found = any(
            self.page.locator(selector).count() > 0 for selector in self.LOGO_SELECTORS
        )
        assert logo_found, "登录页未找到 EPAK Logo"

    def open_mall_home_in_new_tab(self) -> Page:
        home_url = settings.EPAK_MALL_HOME_URL
        home_ready_check = lambda page: wait_for_mall_home_ready(
            page,
            home_url=home_url,
            url_must_contain="epakgroup.com",
            url_must_not_contain="auth.epakgroup.com",
            required_texts=("EPAK One-Stop Platform for Food Packaging", "Home"),
        )
        logo = self.page.locator(self.logo_selector).first
        try:
            logo.wait_for(state="visible", timeout=15000)
            return super().open_mall_home_in_new_tab(
                home_url=home_url,
                home_ready_check=home_ready_check,
            )
        except PlaywrightTimeoutError:
            mall_page = self.page.context.new_page()
            mall_page.goto(
                home_url,
                wait_until="domcontentloaded",
                timeout=settings.MALL_UI_NAV_TIMEOUT_MS,
            )
            home_ready_check(mall_page)
            return mall_page
