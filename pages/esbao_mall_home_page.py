from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config import settings
from pages.esbao_product_detail_page import EsbaoProductDetailPage
from pages.mall.base import MallHomePageBase


class EsbaoMallHomePage(MallHomePageBase):
    HOT_SECTION_TITLE = "热销爆款"
    HOT_PRODUCT_ITEM = ".carousel_item_3dcef7"
    AUTH_HOST_MARKERS = ("auth.esbao.com",)

    REQUIRED_TEXTS = [
        "你好，请登录",
        "商品分类",
        "用户指南",
        "场景分类",
        "甄选工厂",
        "0元入驻",
        "内容资讯",
        "专家人才库",
        "快速询价",
        HOT_SECTION_TITLE,
        "塑料包装",
        "纸质包装",
        "金属包装",
        "包装设备",
        "包材原料",
    ]

    def assert_on_home(self) -> None:
        super().assert_on_home()
        assert "esbao.com" in self.page.url, f"当前不在易食包商城首页: {self.page.url}"

    def assert_full_page_loaded(self, scroll_pause_ms: int = 400) -> dict:
        return super().assert_full_page_loaded(
            scroll_pause_ms,
            scroll_target_js=(
                "() => document.querySelector('[class*=\"commodity_classification\"]')"
                "?.scrollIntoView({block:'center'})"
            ),
        )

    def _prepare_hot_product_section(self) -> None:
        self.page.evaluate(
            """() => {
              const hot = Array.from(document.querySelectorAll('*'))
                .find(el => (el.innerText || '').trim() === '热销爆款');
              hot?.scrollIntoView({block: 'center'});
              const floatHeader = document.querySelector('#floatSearch');
              if (floatHeader) floatHeader.style.pointerEvents = 'none';
            }"""
        )
        self.page.wait_for_timeout(500)

    def _list_hot_product_candidates(self, preferred_name: str | None = None) -> list[dict]:
        return self.page.evaluate(
            """(preferredName) => {
              const normalize = (text) => (text || '').trim().replace(/\\s+/g, ' ');
              const isClickable = (el) => {
                const r = el.getBoundingClientRect();
                if (r.width < 20 || r.height < 20) return false;
                if (r.bottom <= 0 || r.top >= window.innerHeight) return false;
                const slide = el.closest('.slick-slide');
                if (slide && slide.classList.contains('slick-cloned')) return false;
                const style = window.getComputedStyle(el);
                return style.visibility !== 'hidden' && style.display !== 'none';
              };
              const seen = new Set();
              const items = [];
              for (const el of document.querySelectorAll('.carousel_item_3dcef7')) {
                if (!isClickable(el)) continue;
                const name = normalize(el.innerText);
                if (!name || seen.has(name)) continue;
                seen.add(name);
                const rect = el.getBoundingClientRect();
                items.push({
                  name,
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

    def _click_hot_product_candidate(self, candidate: dict) -> tuple[bool, Page, str]:
        self._prepare_hot_product_section()
        product_name = candidate["name"]
        url_before = self.page.url
        detail_page = self.page

        self.page.evaluate(
            """(name) => {
              const normalize = (text) => (text || '').trim().replace(/\\s+/g, ' ');
              const target = Array.from(document.querySelectorAll('.carousel_item_3dcef7')).find(el => {
                const slide = el.closest('.slick-slide');
                if (slide && slide.classList.contains('slick-cloned')) return false;
                return normalize(el.innerText) === name;
              });
              target?.scrollIntoView({block: 'center', inline: 'center'});
            }""",
            product_name,
        )
        self.page.wait_for_timeout(400)

        refreshed = self.page.evaluate(
            """(name) => {
              const normalize = (text) => (text || '').trim().replace(/\\s+/g, ' ');
              const target = Array.from(document.querySelectorAll('.carousel_item_3dcef7')).find(el => {
                const slide = el.closest('.slick-slide');
                if (slide && slide.classList.contains('slick-cloned')) return false;
                return normalize(el.innerText) === name;
              });
              if (!target) return null;
              const rect = target.getBoundingClientRect();
              return {x: rect.x + rect.width / 2, y: rect.y + rect.height / 2};
            }""",
            product_name,
        )
        if not refreshed:
            return False, self.page, product_name

        try:
            with self.page.context.expect_page(timeout=5000) as popup_info:
                self.page.mouse.click(refreshed["x"], refreshed["y"])
            detail_page = popup_info.value
            detail_page.wait_for_load_state("domcontentloaded", timeout=60000)
            if EsbaoProductDetailPage.is_product_detail_url(detail_page.url):
                return True, detail_page, product_name
        except PlaywrightTimeoutError:
            pass

        self.page.mouse.click(refreshed["x"], refreshed["y"])
        self.page.evaluate(
            """(name) => {
              const normalize = (text) => (text || '').trim().replace(/\\s+/g, ' ');
              const target = Array.from(document.querySelectorAll('.carousel_item_3dcef7')).find(el => {
                const slide = el.closest('.slick-slide');
                if (slide && slide.classList.contains('slick-cloned')) return false;
                return normalize(el.innerText) === name;
              });
              target?.click();
            }""",
            product_name,
        )

        resolved = self._resolve_detail_page(url_before)
        if resolved:
            return True, resolved[0], product_name

        try:
            self.page.wait_for_function(
                """(prev) => {
                  const url = location.href;
                  if (url === prev) return false;
                  if (url.includes('auth.esbao.com')) return false;
                  const path = url.split('esbao.com')[1]?.split('?')[0]?.replace(/\\/$/, '') || '/';
                  return path && path !== '/';
                }""",
                url_before,
                timeout=20000,
            )
            if EsbaoProductDetailPage.is_product_detail_url(self.page.url):
                return True, self.page, product_name
        except PlaywrightTimeoutError:
            pass

        resolved = self._resolve_detail_page(url_before)
        if resolved:
            return True, resolved[0], product_name
        return False, self.page, product_name

    def _resolve_detail_page(self, url_before: str) -> tuple[Page, str] | None:
        if (
            EsbaoProductDetailPage.is_product_detail_url(self.page.url)
            and self.page.url != url_before
        ):
            return self.page, self.page.url
        for page in self.page.context.pages:
            if EsbaoProductDetailPage.is_product_detail_url(page.url):
                page.bring_to_front()
                self.page = page
                return page, page.url
        return None

    def open_any_hot_product(self, preferred_name: str | None = None) -> tuple[str, Page]:
        candidates = self._list_hot_product_candidates(preferred_name)
        if not candidates:
            raise AssertionError("未找到「热销爆款」下可点击的商品卡片")

        errors: list[str] = []
        for candidate in candidates:
            navigated, detail_page, product_name = self._click_hot_product_candidate(candidate)
            if not navigated:
                errors.append(product_name)
                continue
            try:
                self._wait_for_detail_page_ready(detail_page)
                return product_name, detail_page
            except PlaywrightTimeoutError:
                if EsbaoProductDetailPage.is_product_detail_url(detail_page.url):
                    errors.append(f"{product_name}(详情页按钮未出现)")
                else:
                    errors.append(product_name)
                continue

        tried = ", ".join(errors[:5])
        raise AssertionError(f"热销爆款下尝试多个商品后均未成功跳转，已尝试: {tried}")

    def open_first_hot_product(self, preferred_name: str = "") -> tuple[str, Page]:
        return self.open_any_hot_product(preferred_name or None)

    def _wait_for_detail_page_ready(self, page: Page) -> None:
        pattern = "|".join(EsbaoProductDetailPage.CTA_TEXT_OPTIONS)
        page.locator(f"text=/{pattern}/").first.wait_for(
            state="visible",
            timeout=settings.ESB_UI_DETAIL_READY_MS,
        )
