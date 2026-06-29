from __future__ import annotations

from typing import Callable

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config import settings
from utils.base_page import BasePage


class MallAuthPageBase(BasePage):
    logo_selector: str = ""

    def __init__(self, page: Page, auth_url: str):
        super().__init__(page)
        self.auth_url = auth_url

    def _goto_with_retry(self, url: str) -> None:
        wait_until = settings.MALL_UI_GOTO_WAIT_UNTIL
        timeout_ms = settings.MALL_UI_NAV_TIMEOUT_MS
        retries = max(settings.MALL_UI_GOTO_RETRIES, 1)
        errors: list[str] = []
        for attempt in range(1, retries + 1):
            try:
                self.page.goto(url, wait_until=wait_until, timeout=timeout_ms)
                return
            except PlaywrightTimeoutError as exc:
                errors.append(f"attempt {attempt}: {exc}")
                if attempt < retries:
                    self.page.wait_for_timeout(2000)
        raise AssertionError(
            f"页面导航失败（{url}，wait_until={wait_until}，"
            f"timeout={timeout_ms}ms，retries={retries}）: {' | '.join(errors)}"
        )

    def open(self) -> None:
        self._goto_with_retry(self.auth_url)
        self._wait_for_login_page_ready()

    def _wait_for_login_page_ready(self) -> None:
        self.page.locator(self.logo_selector).first.wait_for(state="visible", timeout=30000)

    def open_mall_home_in_new_tab(
        self,
        *,
        home_url: str = "",
        home_ready_check: Callable[[Page], None],
    ) -> Page:
        logo = self.page.locator(self.logo_selector).first
        logo.wait_for(state="visible", timeout=15000)
        try:
            with self.page.context.expect_page(timeout=20000) as popup_info:
                logo.click(timeout=10000)
            mall_page = popup_info.value
        except PlaywrightTimeoutError:
            logo.click(timeout=10000)
            mall_page = self.page
        mall_page.wait_for_load_state("domcontentloaded", timeout=settings.MALL_UI_NAV_TIMEOUT_MS)
        try:
            home_ready_check(mall_page)
        except Exception:
            if home_url and home_url not in mall_page.url:
                mall_page.goto(
                    home_url,
                    wait_until=settings.MALL_UI_GOTO_WAIT_UNTIL,
                    timeout=settings.MALL_UI_NAV_TIMEOUT_MS,
                )
            home_ready_check(mall_page)
        return mall_page


class MallHomePageBase(BasePage):
    REQUIRED_TEXTS: list[str] = []

    def __init__(self, page: Page, home_url: str):
        super().__init__(page)
        self.home_url = home_url

    def assert_key_modules_visible(self) -> dict[str, bool]:
        body = self.page.content()
        return {text: text in body for text in self.REQUIRED_TEXTS}

    def assert_full_page_loaded(
        self,
        scroll_pause_ms: int = 400,
        *,
        scroll_target_js: str | None = None,
    ) -> dict:
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
        if scroll_target_js:
            self.page.evaluate(scroll_target_js)
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


class MallProductDetailPageBase(BasePage):
    CTA_TEXT_OPTIONS: tuple[str, ...] = ()
    OPTIONAL_TEXTS: tuple[str, ...] = ()
    detail_ready_timeout_ms: int = settings.ESB_UI_DETAIL_READY_MS

    def assert_detail_loaded(self) -> dict:
        assert self.is_product_detail_url(self.page.url), f"未进入商品详情页: {self.page.url}"
        self.page.wait_for_load_state("domcontentloaded", timeout=60000)
        try:
            self.page.wait_for_load_state("networkidle", timeout=30000)
        except PlaywrightTimeoutError:
            pass
        self._wait_for_detail_ready()
        self._wait_for_product_images()
        self._assert_extra_detail_content()

        body = self.page.content()
        cta_checks = {text: text in body for text in self.CTA_TEXT_OPTIONS}
        optional_checks = {text: text in body for text in self.OPTIONAL_TEXTS}
        if not any(cta_checks.values()):
            raise AssertionError(
                f"商品详情页缺少操作按钮，期望其一: {', '.join(self.CTA_TEXT_OPTIONS)}"
            )

        title = self.page.title()
        image_stats = self._detail_image_stats()
        if image_stats.get("broken", 0) > 0:
            raise AssertionError(f"商品详情页存在未加载图片: {image_stats['broken']} 张")

        result = {
            "url": self.page.url,
            "title": title,
            "cta_checks": cta_checks,
            "optional_checks": optional_checks,
            "image_stats": image_stats,
        }
        result.update(self._extra_detail_checks(body))
        return result

    @staticmethod
    def is_product_detail_url(url: str) -> bool:
        raise NotImplementedError

    def _assert_extra_detail_content(self) -> None:
        return None

    def _extra_detail_checks(self, body: str) -> dict:
        return {}

    def _wait_for_detail_ready(self) -> None:
        pattern = "|".join(self.CTA_TEXT_OPTIONS)
        self.page.locator(f"text=/{pattern}/").first.wait_for(
            state="visible",
            timeout=self.detail_ready_timeout_ms,
        )

    def _wait_for_product_images(self, timeout_ms: int = 45000) -> None:
        self.page.wait_for_function(
            """() => {
              const imgs = Array.from(document.images).filter(img => {
                const r = img.getBoundingClientRect();
                return r.width > 20 && r.height > 20 && r.bottom > 0 && r.top < window.innerHeight * 2;
              });
              if (!imgs.length) return true;
              const pending = imgs.filter(img => !img.complete);
              if (pending.length) return false;
              return imgs.every(img => img.naturalWidth > 0);
            }""",
            timeout=timeout_ms,
        )

    def _detail_image_stats(self) -> dict:
        return self.page.evaluate(
            """() => {
              const imgs = Array.from(document.images);
              const visible = imgs.filter(img => {
                const r = img.getBoundingClientRect();
                return r.width > 20 && r.height > 20 && r.bottom > 0 && r.top < window.innerHeight * 2;
              });
              const broken = visible.filter(img => img.complete && img.naturalWidth === 0);
              return {total: imgs.length, visible: visible.length, broken: broken.length};
            }"""
        )
