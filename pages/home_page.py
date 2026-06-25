from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from utils.base_page import BasePage


class HomePage(BasePage):
    crm_menu_selectors = [
        "text=CRM 2.0",
        "text=CRM2.0",
        "a:has-text('CRM 2.0')",
        "a:has-text('CRM2.0')",
        "[title='CRM 2.0']",
        "[title='CRM2.0']",
    ]
    crm_identity_selectors = [
        "text=CRM 2.0",
        "text=CRM2.0",
        "text=客户",
        "text=线索",
        "text=商机",
    ]

    def open_left_menu(self, menu_name: str) -> Page:
        candidate_selectors = [
            f"text={menu_name}",
            f"a:has-text('{menu_name}')",
            f"[title='{menu_name}']",
        ]
        for selector in candidate_selectors:
            locator = self.page.locator(selector).first
            if locator.count() == 0:
                continue
            locator.scroll_into_view_if_needed()
            try:
                with self.page.expect_popup(timeout=2500) as popup_info:
                    locator.click(timeout=5000)
                popup = popup_info.value
                popup.wait_for_load_state("domcontentloaded", timeout=10000)
                return popup
            except PlaywrightTimeoutError:
                try:
                    locator.click(timeout=5000)
                    self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                    return self.page
                except PlaywrightTimeoutError:
                    continue
        raise AssertionError(f"未找到左侧菜单入口: {menu_name}")

    def open_crm_2(self) -> Page:
        for name in ["CRM 2.0", "CRM2.0"]:
            try:
                return self.open_left_menu(name)
            except AssertionError:
                continue
        raise AssertionError("未找到左侧菜单中的 CRM 2.0 入口")

    def assert_crm_page_loaded(self, target_page: Page) -> None:
        url = target_page.url.lower()
        url_ok = any(k in url for k in ["crm", "customer", "membercenter"])
        text_ok = False
        for selector in self.crm_identity_selectors:
            loc = target_page.locator(selector).first
            if loc.count() > 0:
                text_ok = True
                break
        title = target_page.title().lower()
        title_ok = "crm" in title
        assert url_ok or text_ok or title_ok, (
            f"未命中 CRM 页面标识。url={target_page.url}, title={target_page.title()}"
        )
