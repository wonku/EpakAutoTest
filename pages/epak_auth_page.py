from playwright.sync_api import Page

from config import settings
from pages.mall.base import MallAuthPageBase
from pages.mall.navigation import wait_for_mall_home_ready


class EpakAuthPage(MallAuthPageBase):    logo_selector = ".lingxi-business-logo"
    WELCOME_TEXT = "Welcome to EPAK GROUP!"

    def assert_login_page_loaded(self) -> None:
        assert self.WELCOME_TEXT in self.page.content(), "登录页未出现 Welcome to EPAK GROUP!"
        assert self.page.locator(self.logo_selector).count() > 0, "登录页未找到 EPAK Logo"

    def open_mall_home_in_new_tab(self) -> Page:
        return super().open_mall_home_in_new_tab(
            home_url=settings.EPAK_MALL_HOME_URL,
            home_ready_check=lambda page: wait_for_mall_home_ready(
                page,
                home_url=settings.EPAK_MALL_HOME_URL,
                url_must_contain="epakgroup.com",
                url_must_not_contain="auth.epakgroup.com",
                required_texts=("EPAK One-Stop Platform for Food Packaging", "Home"),
            ),
        )