from __future__ import annotations

import re

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config import settings
from pages.epak_product_detail_page import EpakProductDetailPage
from pages.mall.base import MallHomePageBase


class EpakMallHomePage(MallHomePageBase):
    ONE_STOP_SECTION_TITLE = "EPAK One-Stop Platform for Food Packaging"
    POPUP_NO_THANKS_PATTERN = re.compile(r"No.?Thanks", re.IGNORECASE)

    REQUIRED_TEXTS = [
        "Home",
        "Products",
        "Contact Us",
        "Quotations",
        ONE_STOP_SECTION_TITLE,
        "Category Division",
        "You May Require",
        "EPAK Help Center",
        "About EPAK Company",
    ]

    def assert_on_home(self) -> None:
        assert "epakgroup.com" in self.page.url, f"当前不在 EPAK 商城首页: {self.page.url}"

    def wait_for_subscribe_popup_loaded(self, timeout_ms: int = 30000) -> bool:
        popup = self.page.locator('[class*="EmailPopModel"]').first
        try:
            popup.wait_for(state="visible", timeout=timeout_ms)
        except PlaywrightTimeoutError:
            return False

        no_thanks = self.page.locator('[class*="EmailPopLeft_no_text"]').filter(
            has_text=self.POPUP_NO_THANKS_PATTERN
        )
        no_thanks.first.wait_for(state="visible", timeout=timeout_ms)
        self.page.wait_for_function(
            """() => {
              const modal = document.querySelector('[class*="EmailPopModel"]');
              if (!modal) return false;
              const imgs = Array.from(modal.querySelectorAll('img'));
              if (!imgs.length) return true;
              return imgs.every(img => img.complete && img.naturalWidth > 0);
            }""",
            timeout=timeout_ms,
        )
        return True

    def close_subscribe_popup(self) -> None:
        popup = self.page.locator('[class*="EmailPopModel"]').first
        if popup.count() == 0 or not popup.is_visible():
            return
        close_btn = self.page.locator('[class*="EmailPopClose"]').first
        close_btn.wait_for(state="visible", timeout=10000)
        close_btn.click(timeout=10000)
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
                .find(el => (el.innerText || '').trim() === 'EPAK One-Stop Platform for Food Packaging');
              target?.scrollIntoView({block: 'center'});
            }"""
            ),
        )

    def _prepare_one_stop_section(self) -> None:
        self.page.evaluate(
            """() => {
              const target = Array.from(document.querySelectorAll('*'))
                .find(el => (el.innerText || '').trim() === 'EPAK One-Stop Platform for Food Packaging');
              target?.scrollIntoView({block: 'center'});
              const floatHeader = document.querySelector('#floatSearch');
              if (floatHeader) floatHeader.style.pointerEvents = 'none';
            }"""
        )
        self.page.wait_for_timeout(500)

    def _list_one_stop_product_candidates(self, preferred_name: str | None = None) -> list[dict]:
        return self.page.evaluate(
            """(preferredName) => {
              const normalize = (text) => (text || '').trim().replace(/\\s+/g, ' ');
              const isClickable = (el) => {
                const r = el.getBoundingClientRect();
                if (r.width < 20 || r.height < 20) return false;
                if (r.bottom <= 0 || r.top >= window.innerHeight) return false;
                const style = window.getComputedStyle(el);
                return style.visibility !== 'hidden' && style.display !== 'none';
              };
              const section = document.querySelector('[class*="current_situation_wrapper"]');
              if (!section) return [];
              const items = [];
              const seen = new Set();
              for (const link of section.querySelectorAll('a[href*="/products/"]')) {
                if (!isClickable(link)) continue;
                const name = normalize(link.innerText);
                if (!name || seen.has(name)) continue;
                seen.add(name);
                const rect = link.getBoundingClientRect();
                items.push({
                  name,
                  href: link.href,
                  x: rect.x + rect.width / 2,
                  y: rect.y + rect.height / 2,
                  preferred: !!(preferredName && name.includes(preferredName)),
                });
              }
              items.sort((a, b) => Number(b.preferred) - Number(a.preferred));
              return items;
            }""",
            preferred_name or "",
        )

    def _click_one_stop_product_candidate(self, candidate: dict) -> tuple[bool, Page, str]:
        self._prepare_one_stop_section()
        product_name = candidate["name"]
        product_href = candidate["href"]
        url_before = self.page.url
        detail_page = self.page

        self.page.evaluate(
            """(href) => {
              const section = document.querySelector('[class*="current_situation_wrapper"]');
              const target = section
                ? Array.from(section.querySelectorAll('a[href*="/products/"]'))
                    .find(link => link.href === href || link.href.endsWith(href.split('/products/')[1]))
                : null;
              target?.scrollIntoView({block: 'center', inline: 'center'});
            }""",
            product_href,
        )
        self.page.wait_for_timeout(400)

        refreshed = self.page.evaluate(
            """(href) => {
              const section = document.querySelector('[class*="current_situation_wrapper"]');
              const target = section
                ? Array.from(section.querySelectorAll('a[href*="/products/"]'))
                    .find(link => link.href === href || link.href.endsWith(href.split('/products/')[1]))
                : null;
              if (!target) return null;
              const rect = target.getBoundingClientRect();
              return {x: rect.x + rect.width / 2, y: rect.y + rect.height / 2};
            }""",
            product_href,
        )
        if not refreshed:
            return False, self.page, product_name

        try:
            with self.page.context.expect_page(timeout=5000) as popup_info:
                self.page.mouse.click(refreshed["x"], refreshed["y"])
            detail_page = popup_info.value
            detail_page.wait_for_load_state("domcontentloaded", timeout=60000)
            if EpakProductDetailPage.is_product_detail_url(detail_page.url):
                return True, detail_page, product_name
        except PlaywrightTimeoutError:
            pass

        self.page.mouse.click(refreshed["x"], refreshed["y"])
        self.page.evaluate(
            """(href) => {
              const section = document.querySelector('[class*="current_situation_wrapper"]');
              const target = section
                ? Array.from(section.querySelectorAll('a[href*="/products/"]'))
                    .find(link => link.href === href || link.href.endsWith(href.split('/products/')[1]))
                : null;
              target?.click();
            }""",
            product_href,
        )

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
                url_before,
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

    def open_any_one_stop_product(self, preferred_name: str | None = None) -> tuple[str, Page]:
        self.dismiss_cookie_banner_if_present()
        self._prepare_one_stop_section()

        candidates = self._list_one_stop_product_candidates(preferred_name)
        if not candidates:
            raise AssertionError(
                f"未找到「{self.ONE_STOP_SECTION_TITLE}」下可点击的商品链接"
            )

        errors: list[str] = []
        for candidate in candidates:
            navigated, detail_page, product_name = self._click_one_stop_product_candidate(candidate)
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
        raise AssertionError(
            f"「{self.ONE_STOP_SECTION_TITLE}」下尝试多个商品后均未成功跳转，已尝试: {tried}"
        )

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
        pattern = "|".join(EpakProductDetailPage.CTA_TEXT_OPTIONS)
        page.locator(f"text=/{pattern}/").first.wait_for(
            state="visible",
            timeout=settings.ESB_UI_DETAIL_READY_MS,
        )
