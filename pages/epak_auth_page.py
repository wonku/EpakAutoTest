from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from utils.base_page import BasePage


class EpakAuthPage(BasePage):
    LOGO_SELECTOR = ".lingxi-business-logo"
    WELCOME_TEXT = "Welcome to EPAK GROUP!"

    def __init__(self, page: Page, auth_url: str):
        super().__init__(page)
        self.auth_url = auth_url

    def open(self) -> None:
        self.page.goto(self.auth_url, wait_until="domcontentloaded", timeout=60000)
        self.page.locator(self.LOGO_SELECTOR).first.wait_for(state="visible", timeout=30000)

    def assert_login_page_loaded(self) -> None:
        assert self.WELCOME_TEXT in self.page.content(), "登录页未出现 Welcome to EPAK GROUP!"
        assert self.page.locator(self.LOGO_SELECTOR).count() > 0, "登录页未找到 EPAK Logo"

    def open_mall_home_in_new_tab(self) -> Page:
        logo = self.page.locator(self.LOGO_SELECTOR).first
        logo.wait_for(state="visible", timeout=15000)
        try:
            with self.page.context.expect_page(timeout=20000) as popup_info:
                logo.click(timeout=10000)
            mall_page = popup_info.value
        except PlaywrightTimeoutError:
            logo.click(timeout=10000)
            mall_page = self.page
        mall_page.wait_for_load_state("domcontentloaded", timeout=60000)
        mall_page.wait_for_function(
            "() => document.body.innerText.includes('EPAK One-Stop Platform for Food Packaging')",
            timeout=60000,
        )
        return mall_page
