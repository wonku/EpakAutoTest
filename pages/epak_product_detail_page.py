from playwright.sync_api import Page

from pages.mall.base import MallProductDetailPageBase


class EpakProductDetailPage(MallProductDetailPageBase):
    CTA_TEXT_OPTIONS = ("Order Now", "Add Purchase")
    PARAMETER_TEXTS = ("Main Material", "Thickness", "Width", "Length")
    OPTIONAL_TEXTS = ("Product Introduction", "Basic Information", "Sample")

    def dismiss_image_zoom_overlay(self) -> None:
        """主图 hover 会弹出放大镜预览，遮挡右侧 CTA；将鼠标移出主图区域。"""
        viewport = self.page.viewport_size or {"width": 1280, "height": 720}
        safe_x = max(viewport["width"] - 80, viewport["width"] // 2)
        self.page.mouse.move(safe_x, 48)
        self.page.wait_for_timeout(300)

    @staticmethod
    def dismiss_image_zoom_on_page(page: Page) -> None:
        EpakProductDetailPage(page).dismiss_image_zoom_overlay()

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

    def _wait_for_detail_ready(self) -> None:
        self.dismiss_image_zoom_overlay()
        super()._wait_for_detail_ready()

    def _scroll_detail_page_for_images(self) -> None:
        super()._scroll_detail_page_for_images()
        self.dismiss_image_zoom_overlay()

    def _assert_extra_detail_content(self) -> None:
        self.dismiss_image_zoom_overlay()
        self.page.locator("text=Main Material").first.wait_for(
            state="visible",
            timeout=self.detail_ready_timeout_ms,
        )

    def _extra_detail_checks(self, body: str) -> dict:
        parameter_checks = {text: text in body for text in self.PARAMETER_TEXTS}
        missing_params = [name for name, ok in parameter_checks.items() if not ok]
        if missing_params:
            raise AssertionError(f"商品详情页缺少参数项: {', '.join(missing_params)}")
        return {"parameter_checks": parameter_checks}
