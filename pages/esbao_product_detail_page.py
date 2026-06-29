from pages.mall.base import MallProductDetailPageBase


class EsbaoProductDetailPage(MallProductDetailPageBase):
    CTA_TEXT_OPTIONS = ("获取底价", "加入购物车", "免费样品申领")
    OPTIONAL_TEXTS = ("商家主页", "商品分类", "商品介绍", "基本信息")

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
