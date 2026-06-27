from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from utils.base_page import BasePage


class CrmPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)

    def open_menu(self, menu_name: str) -> None:
        selectors = [
            f"text={menu_name}",
            f"a:has-text('{menu_name}')",
            f"[title='{menu_name}']",
            f".ant-menu-item:has-text('{menu_name}')",
            f".el-menu-item:has-text('{menu_name}')",
        ]
        for selector in selectors:
            loc = self.page.locator(selector).first
            if loc.count() == 0:
                continue
            try:
                loc.scroll_into_view_if_needed()
                loc.click(timeout=6000)
                self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                return
            except PlaywrightTimeoutError:
                continue
        raise AssertionError(f"CRM 页面未找到菜单: {menu_name}")

    def open_menu_path(self, *menu_names: str) -> None:
        for name in menu_names:
            self.open_menu(name)
