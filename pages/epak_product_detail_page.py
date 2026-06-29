from pages.mall.base import MallProductDetailPageBase


class EpakProductDetailPage(MallProductDetailPageBase):
    CTA_TEXT_OPTIONS = ("Order Now", "Add Purchase")
    PARAMETER_TEXTS = ("Main Material", "Thickness", "Width", "Length")
    OPTIONAL_TEXTS = ("Product Introduction", "Basic Information", "Sample")

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

    def _assert_extra_detail_content(self) -> None:
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
