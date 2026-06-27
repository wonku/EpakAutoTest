from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from utils.base_page import BasePage


class EsbaoProductDetailPage(BasePage):
    # 不同商品详情模板按钮文案不同：询价类「获取底价」，商城类「加入购物车」
    CTA_TEXT_OPTIONS = ("获取底价", "加入购物车", "免费样品申领")
    OPTIONAL_TEXTS = ("商家主页", "商品分类", "商品介绍", "基本信息")

    def __init__(self, page: Page):
        super().__init__(page)

    @staticmethod
    def is_product_detail_url(url: str) -> bool:
        if "auth.esbao.com" in url:
            return False
        if "esbao.com" not in url:
            return False
        path = url.split("esbao.com", 1)[-1].split("?")[0].rstrip("/") or "/"
        if path in ("", "/"):
            return False
        return True

    def assert_detail_loaded(self) -> dict:
        assert self.is_product_detail_url(self.page.url), f"未进入商品详情页: {self.page.url}"
        self.page.wait_for_load_state("domcontentloaded", timeout=60000)
        try:
            self.page.wait_for_load_state("networkidle", timeout=30000)
        except PlaywrightTimeoutError:
            pass
        self._wait_for_detail_ready()
        self._wait_for_product_images()

        body = self.page.content()
        cta_checks = {text: text in body for text in self.CTA_TEXT_OPTIONS}
        optional_checks = {text: text in body for text in self.OPTIONAL_TEXTS}
        if not any(cta_checks.values()):
            raise AssertionError(
                f"商品详情页缺少操作按钮，期望其一: {', '.join(self.CTA_TEXT_OPTIONS)}"
            )

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
            "optional_checks": optional_checks,
            "image_stats": image_stats,
        }

    def _wait_for_detail_ready(self) -> None:
        pattern = "|".join(self.CTA_TEXT_OPTIONS)
        self.page.locator(f"text=/{pattern}/").first.wait_for(state="visible", timeout=60000)

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
