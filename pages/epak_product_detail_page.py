from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config import settings
from utils.base_page import BasePage


class EpakProductDetailPage(BasePage):
    CTA_TEXT_OPTIONS = ("Order Now", "Add Purchase")
    PARAMETER_TEXTS = ("Main Material", "Thickness", "Width", "Length")
    OPTIONAL_TEXTS = ("Product Introduction", "Basic Information", "Sample")

    def __init__(self, page: Page):
        super().__init__(page)

    @staticmethod
    def is_product_detail_url(url: str) -> bool:
        if "auth.epakgroup.com" in url:
            return False
        if "epakgroup.com" not in url:
            return False
        path = url.split("epakgroup.com", 1)[-1].split("?")[0].rstrip("/") or "/"
        if path in ("", "/"):
            return False
        return "/products/" in path

    def assert_detail_loaded(self) -> dict:
        assert self.is_product_detail_url(self.page.url), f"未进入商品详情页: {self.page.url}"
        self.page.wait_for_load_state("domcontentloaded", timeout=60000)
        try:
            self.page.wait_for_load_state("networkidle", timeout=30000)
        except PlaywrightTimeoutError:
            pass
        self._wait_for_detail_ready()
        self._wait_for_product_images()
        self._wait_for_parameters()

        body = self.page.content()
        cta_checks = {text: text in body for text in self.CTA_TEXT_OPTIONS}
        parameter_checks = {text: text in body for text in self.PARAMETER_TEXTS}
        optional_checks = {text: text in body for text in self.OPTIONAL_TEXTS}
        if not any(cta_checks.values()):
            raise AssertionError(
                f"商品详情页缺少操作按钮，期望其一: {', '.join(self.CTA_TEXT_OPTIONS)}"
            )
        missing_params = [name for name, ok in parameter_checks.items() if not ok]
        if missing_params:
            raise AssertionError(f"商品详情页缺少参数项: {', '.join(missing_params)}")

        title = self.page.title()
        image_stats = self.page.evaluate(
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
        if image_stats.get("broken", 0) > 0:
            raise AssertionError(f"商品详情页存在未加载图片: {image_stats['broken']} 张")

        return {
            "url": self.page.url,
            "title": title,
            "cta_checks": cta_checks,
            "parameter_checks": parameter_checks,
            "optional_checks": optional_checks,
            "image_stats": image_stats,
        }

    def _wait_for_detail_ready(self) -> None:
        pattern = "|".join(self.CTA_TEXT_OPTIONS)
        self.page.locator(f"text=/{pattern}/").first.wait_for(
            state="visible",
            timeout=settings.ESB_UI_DETAIL_READY_MS,
        )

    def _wait_for_parameters(self) -> None:
        self.page.locator("text=Main Material").first.wait_for(
            state="visible",
            timeout=settings.ESB_UI_DETAIL_READY_MS,
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
