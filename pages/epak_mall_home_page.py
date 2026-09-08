from __future__ import annotations

import re

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config import settings
from pages.epak_product_detail_page import EpakProductDetailPage
from pages.mall.base import MallHomePageBase


class EpakMallHomePage(MallHomePageBase):
    SUPPLY_SECTION_TITLE = "All-in-One Packaging Product Supply"
    CATEGORY_CTA_NAMES = ("Find What You Need", "Grow Your Business")
    PRODUCT_CARD = '[class*="product_item_box"]'
    POPUP_NO_THANKS_PATTERN = re.compile(r"No.?Thanks", re.IGNORECASE)
    AUTH_HOST_MARKERS = ("auth.epakgroup.com",)

    REQUIRED_TEXTS = [
        # 保留主体模块标题，避免顶部导航/运营位文案变化造成误判。
        SUPPLY_SECTION_TITLE,
        "Ready-to-Buy Packaging Bundles",
        "Packaging Solutions for Diverse Applications",
        "About EPAK: Your Team Behind the Tech",
        "Quality & Compliance Assurance",
    ]

    def assert_on_home(self) -> None:
        super().assert_on_home()
        assert "epakgroup.com" in self.page.url, f"当前不在 EPAK 商城首页: {self.page.url}"

    def wait_for_subscribe_popup_loaded(self, timeout_ms: int = 30000) -> bool:
        popup = self.page.locator('[class*="EmailPopModel"]').first
        try:
            popup.wait_for(state="visible", timeout=timeout_ms)
        except PlaywrightTimeoutError:
            return False

        # 弹窗内的营销图片/文案会不定期更新，这里只校验关闭按钮存在，不校验图片内容。
        no_thanks = self.page.locator('[class*="EmailPopLeft_no_text"]').filter(
            has_text=self.POPUP_NO_THANKS_PATTERN
        )
        close_btn = self.page.locator('[class*="EmailPopClose"]').first
        try:
            no_thanks.first.wait_for(state="visible", timeout=timeout_ms)
            return True
        except PlaywrightTimeoutError:
            pass
        try:
            close_btn.wait_for(state="visible", timeout=timeout_ms)
            return True
        except PlaywrightTimeoutError:
            return False

    def close_subscribe_popup(self) -> None:
        popup = self.page.locator('[class*="EmailPopModel"]').first
        if popup.count() == 0 or not popup.is_visible():
            return
        close_btn = self.page.locator('[class*="EmailPopClose"]').first
        no_thanks = self.page.locator('[class*="EmailPopLeft_no_text"]').filter(
            has_text=self.POPUP_NO_THANKS_PATTERN
        ).first
        for candidate in (close_btn, no_thanks):
            if candidate.count() == 0:
                continue
            try:
                candidate.wait_for(state="visible", timeout=10000)
                candidate.click(timeout=10000)
                popup.wait_for(state="hidden", timeout=10000)
                return
            except PlaywrightTimeoutError:
                continue
        popup.wait_for(state="hidden", timeout=10000)

    def dismiss_cookie_banner_if_present(self) -> None:
        accept = self.page.get_by_role("button", name="I Accept")
        if accept.count() == 0:
            return
        try:
            if accept.first.is_visible():
                accept.first.click(timeout=5000)
        except PlaywrightTimeoutError:
            pass

    def assert_full_page_loaded(self, scroll_pause_ms: int = 400) -> dict:
        return super().assert_full_page_loaded(
            scroll_pause_ms,
            scroll_target_js=(
                """() => {
              const target = Array.from(document.querySelectorAll('*'))
                .find(el => (el.innerText || '').trim() === 'All-in-One Packaging Product Supply');
              target?.scrollIntoView({block: 'center'});
            }"""
            ),
        )

    def _disable_float_header(self) -> None:
        self.page.evaluate(
            """() => {
              const floatHeader = document.querySelector('#floatSearch');
              if (floatHeader) floatHeader.style.pointerEvents = 'none';
            }"""
        )

    def _open_category_listing(self) -> None:
        if "/category" in self.page.url:
            return
        cta = None
        for name in self.CATEGORY_CTA_NAMES:
            locator = self.page.get_by_role("link", name=name)
            if locator.count() > 0:
                cta = locator.first
                break
        if cta is None:
            category_url = self.home_url.rstrip("/") + "/category"
            self.page.goto(
                category_url,
                wait_until=settings.MALL_UI_GOTO_WAIT_UNTIL,
                timeout=settings.MALL_UI_NAV_TIMEOUT_MS,
            )
        else:
            cta.click(timeout=10000)
        try:
            self.page.wait_for_url("**/category**", timeout=settings.MALL_UI_NAV_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            if "/category" not in self.page.url:
                raise AssertionError(f"未进入商品分类页: {self.page.url}")
        self.page.locator(self.PRODUCT_CARD).first.wait_for(
            state="visible",
            timeout=30000,
        )

    def _list_catalog_product_candidates(self, preferred_name: str | None = None) -> list[dict]:
        return self.page.evaluate(
            """(preferredName) => {
              const normalize = (text) => (text || '').trim().replace(/\\s+/g, ' ');
              const preferred = (preferredName || '').trim().toLowerCase();
              const cards = Array.from(document.querySelectorAll('[class*="product_item_box"]'));
              const items = [];
              const seen = new Set();
              for (const card of cards) {
                const img = card.querySelector('img[alt]');
                const name = normalize(img?.getAttribute('alt') || card.querySelector('.ellipsis3')?.innerText || '');
                if (!name || seen.has(name)) continue;
                const rect = card.getBoundingClientRect();
                if (rect.width < 20 || rect.height < 20) continue;
                seen.add(name);
                items.push({
                  name,
                  preferred: !!(preferred && name.toLowerCase().includes(preferred)),
                });
              }
              items.sort((a, b) => Number(b.preferred) - Number(a.preferred));
              return items;
            }""",
            preferred_name or "",
        )

    def _click_catalog_product_candidate(self, candidate: dict) -> tuple[bool, Page, str]:
        self._disable_float_header()
        product_name = candidate["name"]
        url_before = self.page.url
        img = self.page.locator(self.PRODUCT_CARD).get_by_alt_text(product_name, exact=True).first
        try:
            img.scroll_into_view_if_needed(timeout=10000)
        except PlaywrightTimeoutError:
            return False, self.page, product_name

        detail_page = self.page
        try:
            with self.page.context.expect_page(timeout=8000) as popup_info:
                img.click(timeout=10000)
            detail_page = popup_info.value
            detail_page.wait_for_load_state("domcontentloaded", timeout=60000)
            if EpakProductDetailPage.is_product_detail_url(detail_page.url):
                return True, detail_page, product_name
        except PlaywrightTimeoutError:
            pass

        resolved = self._resolve_detail_page(url_before, detail_page)
        if resolved:
            return True, resolved, product_name

        try:
            img.click(timeout=10000)
        except PlaywrightTimeoutError:
            pass

        resolved = self._resolve_detail_page(url_before, detail_page)
        if resolved:
            return True, resolved, product_name

        try:
            self.page.wait_for_function(
                """(prev) => {
                  const url = location.href;
                  if (url === prev) return false;
                  if (url.includes('auth.epakgroup.com')) return false;
                  const path = url.split('epakgroup.com')[1]?.split('?')[0]?.replace(/\\/$/, '') || '/';
                  return path && path !== '/' && path.includes('/products/');
                }""",
                arg=url_before,
                timeout=20000,
            )
            if EpakProductDetailPage.is_product_detail_url(self.page.url):
                return True, self.page, product_name
        except PlaywrightTimeoutError:
            pass

        resolved = self._resolve_detail_page(url_before, detail_page)
        if resolved:
            return True, resolved, product_name
        return False, self.page, product_name

    def open_any_catalog_product(self, preferred_name: str | None = None) -> tuple[str, Page]:
        self.dismiss_cookie_banner_if_present()
        self.close_subscribe_popup()
        self._open_category_listing()
        self.dismiss_cookie_banner_if_present()
        self.close_subscribe_popup()
        self._disable_float_header()

        candidates = self._list_catalog_product_candidates(preferred_name)
        if not candidates:
            raise AssertionError("分类页未找到可点击的商品卡片")

        errors: list[str] = []
        for candidate in candidates:
            navigated, detail_page, product_name = self._click_catalog_product_candidate(candidate)
            if not navigated:
                errors.append(product_name)
                continue
            try:
                self._wait_for_detail_page_ready(detail_page)
                return product_name, detail_page
            except PlaywrightTimeoutError:
                if EpakProductDetailPage.is_product_detail_url(detail_page.url):
                    errors.append(f"{product_name}(详情页按钮未出现)")
                else:
                    errors.append(product_name)
                continue

        tried = ", ".join(errors[:5])
        raise AssertionError(f"分类页尝试多个商品后均未成功跳转，已尝试: {tried}")

    def open_any_one_stop_product(self, preferred_name: str | None = None) -> tuple[str, Page]:
        return self.open_any_catalog_product(preferred_name)

    def _resolve_detail_page(self, url_before: str, current_page: Page) -> Page | None:
        if (
            EpakProductDetailPage.is_product_detail_url(current_page.url)
            and current_page.url != url_before
        ):
            current_page.bring_to_front()
            self.page = current_page
            return current_page
        for page in self.page.context.pages:
            if EpakProductDetailPage.is_product_detail_url(page.url):
                page.bring_to_front()
                self.page = page
                return page
        return None

    def _wait_for_detail_page_ready(self, page: Page) -> None:
        detail = EpakProductDetailPage(page)
        detail.dismiss_image_zoom_overlay()
        for text in EpakProductDetailPage.CTA_TEXT_OPTIONS:
            button = page.get_by_role("button", name=text)
            if button.count() == 0:
                continue
            try:
                button.first.wait_for(state="visible", timeout=5000)
                return
            except PlaywrightTimeoutError:
                continue
        pattern = "|".join(EpakProductDetailPage.CTA_TEXT_OPTIONS)
        page.locator(f"text=/{pattern}/").first.wait_for(
            state="visible",
            timeout=settings.ESB_UI_DETAIL_READY_MS,
        )
