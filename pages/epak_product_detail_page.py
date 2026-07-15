from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from pages.mall.base import MallProductDetailPageBase


class EpakProductDetailPage(MallProductDetailPageBase):
    CTA_TEXT_OPTIONS = ("Order Now", "Add Purchase", "Inquiry Now")
    PARAMETER_TEXT_OPTIONS = (
        "Main Material",
        "Thickness",
        "Width",
        "Length",
        "Weight(g)",
        "Product Type",
        "product",
        "Capacity(oz)",
    )
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
        for text in self.CTA_TEXT_OPTIONS:
            button = self.page.get_by_role("button", name=text)
            if button.count() == 0:
                continue
            try:
                button.first.wait_for(state="visible", timeout=5000)
                return
            except PlaywrightTimeoutError:
                continue
        super()._wait_for_detail_ready()

    def _scroll_detail_page_for_images(self) -> None:
        super()._scroll_detail_page_for_images()
        self.dismiss_image_zoom_overlay()

    def _assert_extra_detail_content(self) -> None:
        self.dismiss_image_zoom_overlay()
        # 勿用 text=/A|Weight(g)|.../：括号会被当成正则捕获组，匹配不到字面量 Weight(g)。
        deadline_ms = self.detail_ready_timeout_ms
        poll_ms = 500
        elapsed = 0
        while elapsed < deadline_ms:
            for text in self.PARAMETER_TEXT_OPTIONS:
                locator = self.page.get_by_text(text, exact=True)
                if locator.count() == 0:
                    continue
                try:
                    if locator.first.is_visible():
                        return
                except PlaywrightTimeoutError:
                    continue
            self.page.wait_for_timeout(poll_ms)
            elapsed += poll_ms
        raise AssertionError(
            "商品详情页参数项未出现（可见），期望至少其一: "
            f"{', '.join(self.PARAMETER_TEXT_OPTIONS)}"
        )

    def _extra_detail_checks(self, body: str) -> dict:
        parameter_checks = {
            text: text in body for text in self.PARAMETER_TEXT_OPTIONS
        }
        found = [name for name, ok in parameter_checks.items() if ok]
        if not found:
            raise AssertionError(
                "商品详情页缺少参数项，期望至少出现其一: "
                f"{', '.join(self.PARAMETER_TEXT_OPTIONS)}"
            )
        return {"parameter_checks": parameter_checks, "found_parameters": found}
