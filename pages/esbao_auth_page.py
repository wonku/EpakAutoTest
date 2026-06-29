from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config import settings
from pages.mall.base import MallAuthPageBase
from pages.mall.navigation import wait_for_mall_home_ready


class EsbaoAuthPage(MallAuthPageBase):
    logo_selector = '[class*="logoWrap"] img[alt="易食包"]'
    WELCOME_TEXT = "欢迎登录易食包"
    LOGIN_TAB_TEXT = "密码登录"
    LOGIN_BUTTON_TEXT = "点击登录"

    def _wait_for_login_page_ready(self) -> None:
        timeout = settings.MALL_UI_AUTH_READY_TIMEOUT_MS
        self.page.get_by_role("heading", name=self.WELCOME_TEXT).wait_for(
            state="visible",
            timeout=timeout,
        )
        self.page.get_by_role("button", name=self.LOGIN_BUTTON_TEXT).wait_for(
            state="visible",
            timeout=timeout,
        )
        self.page.locator(self.logo_selector).first.wait_for(
            state="visible",
            timeout=timeout,
        )

    def assert_login_page_loaded(self) -> None:
        body = self.page.content()
        assert self.WELCOME_TEXT in body, f"登录页未出现「{self.WELCOME_TEXT}」"
        assert self.LOGIN_TAB_TEXT in body, f"登录页未出现「{self.LOGIN_TAB_TEXT}」"
        assert self.LOGIN_BUTTON_TEXT in body, f"登录页未出现「{self.LOGIN_BUTTON_TEXT}」"
        assert self.page.locator(self.logo_selector).count() > 0, "登录页未找到顶部易食包 Logo"

    def open_mall_home_in_new_tab(self) -> Page:
        return super().open_mall_home_in_new_tab(
            home_url=settings.ESB_MALL_HOME_URL,
            home_ready_check=lambda page: wait_for_mall_home_ready(
                page,
                home_url=settings.ESB_MALL_HOME_URL,
                url_must_contain="esbao.com",
                url_must_not_contain="auth.esbao.com",
                required_texts=("商品分类", "热销爆款"),
            ),
        )
