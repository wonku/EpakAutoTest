from __future__ import annotations

import re

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config import settings
from pages.epak_product_detail_page import EpakProductDetailPage
from utils.base_page import BasePage


class EpakMallHomePage(BasePage):
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

    def __init__(self, page: Page, home_url: str):
        super().__init__(page)
        self.home_url = home_url

    def assert_on_home(self) -> None:
        assert "epakgroup.com" in self.page.url, f"当前不在 EPAK 商城首页: {self.page.url}"

    def assert_key_modules_visible(self) -> dict[str, bool]:
        body = self.page.content()
        return {text: text in body for text in self.REQUIRED_TEXTS}

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
        text_results = self.assert_key_modules_visible()
        missing_texts = [name for name, ok in text_results.items() if not ok]
        if missing_texts:
            raise AssertionError(f"首页缺少关键文案: {', '.join(missing_texts)}")

        scroll_height = self.page.evaluate("() => document.body.scrollHeight")
        viewport_height = self.page.viewport_size["height"] if self.page.viewport_size else 900
        step = max(viewport_height // 2, 300)
        y = 0
        while y <= scroll_height:
            self.page.evaluate("(y) => window.scrollTo(0, y)", y)
            self.page.wait_for_timeout(scroll_pause_ms)
            y += step

        self.page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        self.page.wait_for_timeout(max(scroll_pause_ms, 800))
        self.page.evaluate("() => window.scrollTo(0, 0)")
        self.page.wait_for_timeout(scroll_pause_ms)
        self.page.evaluate(
            """() => {
              const target = Array.from(document.querySelectorAll('*'))
                .find(el => (el.innerText || '').trim() === 'EPAK One-Stop Platform for Food Packaging');
              target?.scrollIntoView({block: 'center'});
            }"""
        )
        self.page.wait_for_timeout(scroll_pause_ms)
        self.page.wait_for_timeout(settings.ESB_UI_IMAGE_SETTLE_MS)
        self._wait_for_homepage_images(settings.ESB_UI_HOME_IMAGE_WAIT_MS)

        image_stats = self._visible_image_stats()
        broken_images = self._broken_images_in_document()
        if broken_images:
            sample = ", ".join(item.get("src", "")[:80] for item in broken_images[:3])
            raise AssertionError(
                f"首页存在未加载图片 {len(broken_images)} 张，示例: {sample}"
            )

        return {
            "text_checks": text_results,
            "image_stats": image_stats,
            "scroll_height": scroll_height,
            "broken_images": len(broken_images),
        }

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

    def _wait_for_homepage_images(self, max_wait_ms: int) -> None:
        poll_ms = 500
        elapsed = 0
        while elapsed < max_wait_ms:
            pending = self.page.evaluate(
                """() => {
                  const imgs = Array.from(document.images).filter(img => {
                    const r = img.getBoundingClientRect();
                    return r.width > 20 && r.height > 20;
                  });
                  return imgs.filter(img => !img.complete).length;
                }"""
            )
            broken = self._broken_images_in_document()
            if pending == 0 and not broken:
                return
            self.page.wait_for_timeout(poll_ms)
            elapsed += poll_ms

    def _visible_image_stats(self) -> dict:
        return self.page.evaluate(
            """() => {
              const imgs = Array.from(document.images);
              const visible = imgs.filter(img => {
                const r = img.getBoundingClientRect();
                return r.width > 20 && r.height > 20;
              });
              const broken = visible.filter(img => !img.complete || img.naturalWidth === 0);
              return {total: imgs.length, visible: visible.length, broken: broken.length};
            }"""
        )

    def _broken_images_in_document(self) -> list[dict]:
        return self.page.evaluate(
            """() => Array.from(document.images)
              .filter(img => {
                const r = img.getBoundingClientRect();
                const hasSize = r.width > 20 && r.height > 20;
                return hasSize && img.complete && img.naturalWidth === 0;
              })
              .map(img => ({src: img.currentSrc || img.src, alt: img.alt || ''}))"""
        )
