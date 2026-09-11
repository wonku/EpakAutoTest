from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config import settings
from pages.mall.base import MallAuthPageBase
from pages.mall.navigation import wait_for_mall_home_ready


class EpakAuthPage(MallAuthPageBase):
    logo_selector = 'a[aria-label="Back to home"]'
    LOGO_SELECTORS = (
        'a[aria-label="Back to home"]',
        'a[class*="logoLink"]',
        'img[alt="EPAK"]',
        '[class*="brandLogo"]',
        ".lingxi-business-logo",
        "img.lingxi-business-logo",
        '[class*="logo"] img',
    )
    WELCOME_TEXT = "Welcome to EPAK"

    def _wait_for_login_page_ready(self) -> None:
        timeout = settings.MALL_UI_AUTH_READY_TIMEOUT_MS
        last_error: PlaywrightTimeoutError | None = None
        for attempt in range(2):
            attempt_timeout = timeout if attempt == 0 else max(timeout // 2, 30000)
            try:
                self._wait_for_login_content(attempt_timeout)
                self._wait_for_login_logo()
                return
            except PlaywrightTimeoutError as exc:
                last_error = exc
                if attempt == 0:
                    self.page.reload(
                        wait_until="domcontentloaded",
                        timeout=settings.MALL_UI_NAV_TIMEOUT_MS,
                    )
                    try:
                        self.page.wait_for_load_state("networkidle", timeout=15000)
                    except PlaywrightTimeoutError:
                        pass
                    continue
        raise last_error if last_error else AssertionError("EPAK 登录页未就绪")

    def _wait_for_login_content(self, timeout: int) -> None:
        self.page.get_by_text(self.WELCOME_TEXT, exact=False).first.wait_for(
            state="visible",
            timeout=timeout,
        )
        self.page.get_by_role("button", name="Login").wait_for(
            state="visible",
            timeout=min(timeout, 15000),
        )

    def _wait_for_login_logo(self) -> None:
        for selector in self.LOGO_SELECTORS:
            locator = self.page.locator(selector).first
            try:
                locator.wait_for(state="visible", timeout=8000)
                self.logo_selector = selector
                return
            except PlaywrightTimeoutError:
                continue
        raise AssertionError("登录页未找到可点击的 EPAK Logo")

    def assert_login_page_loaded(self) -> None:
        body = self.page.locator("body").inner_text()
        assert self.WELCOME_TEXT in body, "登录页未出现 Welcome to EPAK"
        logo_found = any(
            self.page.locator(selector).count() > 0 for selector in self.LOGO_SELECTORS
        )
        assert logo_found, "登录页未找到 EPAK Logo（左侧 Back to home）"

    def open_mall_home_in_new_tab(self) -> Page:
        home_url = settings.EPAK_MALL_HOME_URL
        home_ready_check = lambda page: wait_for_mall_home_ready(
            page,
            home_url=home_url,
            url_must_contain="www.epakgroup.com",
            url_must_not_contain="/login",
            required_texts=("All-in-One Packaging Product Supply", "Start Your Sourcing"),
        )
        self._wait_for_login_logo()
        return super().open_mall_home_in_new_tab(
            home_url=home_url,
            home_ready_check=home_ready_check,
        )
