from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from utils.base_page import BasePage


class EsbaoAuthPage(BasePage):
    HEADER_LOGO_SELECTOR = '[class*="logoWrap"] img[alt="易食包"]'
    WELCOME_TEXT = "欢迎登录易食包"
    LOGIN_TAB_TEXT = "密码登录"
    LOGIN_BUTTON_TEXT = "点击登录"

    def __init__(self, page: Page, auth_url: str):
        super().__init__(page)
        self.auth_url = auth_url

    def open(self) -> None:
        self.page.goto(self.auth_url, wait_until="domcontentloaded", timeout=60000)
        self._wait_for_login_page_ready()

    def assert_login_page_loaded(self) -> None:
        body = self.page.content()
        assert self.WELCOME_TEXT in body, f"登录页未出现「{self.WELCOME_TEXT}」"
        assert self.LOGIN_TAB_TEXT in body, f"登录页未出现「{self.LOGIN_TAB_TEXT}」"
        assert self.LOGIN_BUTTON_TEXT in body, f"登录页未出现「{self.LOGIN_BUTTON_TEXT}」"
        assert self.page.locator(self.HEADER_LOGO_SELECTOR).count() > 0, "登录页未找到顶部易食包 Logo"

    def _wait_for_login_page_ready(self) -> None:
        self.page.get_by_role("heading", name=self.WELCOME_TEXT).wait_for(
            state="visible",
            timeout=30000,
        )
        self.page.get_by_role("button", name=self.LOGIN_BUTTON_TEXT).wait_for(
            state="visible",
            timeout=30000,
        )
        self.page.locator(self.HEADER_LOGO_SELECTOR).first.wait_for(
            state="visible",
            timeout=30000,
        )

    def open_mall_home_in_new_tab(self) -> Page:
        logo = self.page.locator(self.HEADER_LOGO_SELECTOR).first
        logo.wait_for(state="visible", timeout=15000)
        try:
            with self.page.context.expect_page(timeout=20000) as popup_info:
                logo.click(timeout=10000)
            mall_page = popup_info.value
        except PlaywrightTimeoutError:
            logo.click(timeout=10000)
            mall_page = self.page
        mall_page.wait_for_load_state("domcontentloaded", timeout=60000)
        mall_page.locator("text=商品分类").first.wait_for(state="visible", timeout=60000)
        return mall_page
