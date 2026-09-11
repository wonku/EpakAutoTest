from __future__ import annotations

import re

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config import settings
from pages.epak_product_detail_page import EpakProductDetailPage
from pages.mall.base import MallHomePageBase


class EpakMallHomePage(MallHomePageBase):
    SUPPLY_SECTION_TITLE = "All-in-One Packaging Product Supply"
    CATEGORY_CTA_NAMES = ("Find What You Need", "Grow Your Business")
    PRODUCT_CARD = '[class*="product_item_box"]'
    POPUP_NO_THANKS_PATTERN = re.compile(r"No.?Thanks", re.IGNORECASE)
    AUTH_HOST_MARKERS = ("auth.epakgroup.com", "/login")

    REQUIRED_TEXTS = [
        # 保留主体模块标题，避免顶部导航/运营位文案变化造成误判。
        SUPPLY_SECTION_TITLE,
        "Ready-to-Buy Packaging Bundles",
        "Packaging Solutions for Diverse Applications",
        "About EPAK: Your Team Behind the Tech",
        "Quality & Compliance Assurance",
    ]
    # 首页各楼层可点击入口（物料砖块/套装卡/认证标点了不跳转，只巡 CTA 与顶栏）
    HOME_MODULE_JUMPS: tuple[dict, ...] = (
        {
            "module": "顶部导航",
            "name": "Product Info",
            "url_fragment": "/solutions",
            "hints": ("Product Info", "Solutions", "Packaging"),
        },
        {
            "module": "顶部导航",
            "name": "News & Updates",
            "url_fragment": "/insight",
            "hints": ("News", "Insight", "Updates"),
        },
        {
            "module": "顶部导航",
            "name": "Contact Us",
            "url_fragment": "/contact",
            "hints": ("Contact", "Email", "Message"),
        },
        {
            "module": "首屏 Hero",
            "name": "Start Your Sourcing",
            "url_fragment": "/contact",
            "hints": ("Contact", "Email", "Message"),
        },
        {
            "module": "首屏 Hero",
            "name": "Become a Distributor",
            "url_fragment": "/become-a-partner",
            "hints": ("Distributor", "Partner", "Become"),
        },
        {
            "module": "All-in-One Packaging Product Supply",
            "name": "Grow Your Business",
            "url_fragment": "/category",
            "hints": (),
        },
        {
            "module": "Ready-to-Buy Packaging Bundles",
            "name": "Find What You Need",
            "url_fragment": "/category",
            "hints": (),
        },
        {
            "module": "Ready-to-Buy Packaging Bundles",
            "name": "Inquiry Now",
            "url_fragment": "/contact",
            "hints": ("Contact", "Email", "Message"),
        },
        {
            "module": "Packaging Solutions for Diverse Applications",
            "name": "Get Packaging Recommendations",
            "url_fragment": "/solutions",
            "hints": ("Product Info", "Solutions", "Packaging"),
        },
        {
            "module": "Everything You Need One Packaging Partner",
            "name": "Discuss Your Project",
            "url_fragment": "/contact",
            "hints": ("Contact", "Email", "Message"),
        },
        {
            "module": "Beyond Supply Built for Growth",
            "name": "Talk About Your Goals",
            "url_fragment": "/contact",
            "hints": ("Contact", "Email", "Message"),
        },
        {
            "module": "About EPAK: Your Team Behind the Tech",
            "name": "Learn About EPAK",
            "url_fragment": "/about-us",
            "hints": ("About", "EPAK", "Team"),
        },
    )
    _DEST_ERROR_RE = re.compile(
        r"(?<!\d)404(?!\d)|(?<!\d)500(?!\d)|page\s*not\s*found|not\s*found|"
        r"system error|service unavailable|系统错误|服务异常|页面不存在",
        re.I,
    )

    def assert_on_home(self) -> None:
        super().assert_on_home()
        assert "epakgroup.com" in self.page.url, f"当前不在 EPAK 商城首页: {self.page.url}"

    def wait_for_subscribe_popup_loaded(self, timeout_ms: int = 30000) -> bool:
        popup = self.page.locator('[class*="EmailPopModel"]').first
        try:
            popup.wait_for(state="visible", timeout=timeout_ms)
        except PlaywrightTimeoutError:
            return False

        # 弹窗内的营销图片/文案会不定期更新，这里只校验关闭按钮存在，不校验图片内容。
        no_thanks = self.page.locator('[class*="EmailPopLeft_no_text"]').filter(
            has_text=self.POPUP_NO_THANKS_PATTERN
        )
        close_btn = self.page.locator('[class*="EmailPopClose"]').first
        try:
            no_thanks.first.wait_for(state="visible", timeout=timeout_ms)
            return True
        except PlaywrightTimeoutError:
            pass
        try:
            close_btn.wait_for(state="visible", timeout=timeout_ms)
            return True
        except PlaywrightTimeoutError:
            return False

    def close_subscribe_popup(self) -> None:
        popup = self.page.locator('[class*="EmailPopModel"]').first
        if popup.count() == 0 or not popup.is_visible():
            return
        close_btn = self.page.locator('[class*="EmailPopClose"]').first
        no_thanks = self.page.locator('[class*="EmailPopLeft_no_text"]').filter(
            has_text=self.POPUP_NO_THANKS_PATTERN
        ).first
        for candidate in (close_btn, no_thanks):
            if candidate.count() == 0:
                continue
            try:
                candidate.wait_for(state="visible", timeout=10000)
                candidate.click(timeout=10000)
                popup.wait_for(state="hidden", timeout=10000)
                return
            except PlaywrightTimeoutError:
                continue
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
                .find(el => (el.innerText || '').trim() === 'All-in-One Packaging Product Supply');
              target?.scrollIntoView({block: 'center'});
            }"""
            ),
        )

    def assert_home_entry_points(self) -> dict:
        """点开每个首页模块的稳定 CTA，检查跳转页能加载，再回到首页。"""
        jumps: list[dict] = []
        failures: list[str] = []
        for spec in self.HOME_MODULE_JUMPS:
            label = f"{spec['module']}「{spec['name']}」"
            try:
                url = self._open_module_jump(spec)
                jumps.append(
                    {
                        "module": spec["module"],
                        "name": spec["name"],
                        "url": url,
                        "status": "ok",
                    }
                )
                print(f"[ok] {label} -> {url}", flush=True)
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                jumps.append(
                    {
                        "module": spec["module"],
                        "name": spec["name"],
                        "url": self.page.url,
                        "status": "fail",
                        "error": message,
                    }
                )
                failures.append(f"{label}: {message}")
                print(f"[fail] {label} | {self.page.url} | {message}", flush=True)
            finally:
                self._ensure_on_home()
        if failures:
            raise AssertionError(
                "首页模块跳转失败 "
                f"{len(failures)}/{len(self.HOME_MODULE_JUMPS)}: "
                + "; ".join(failures[:8])
            )
        return {"jumps": jumps, "total": len(jumps)}

    def _ensure_on_home(self) -> None:
        self.close_subscribe_popup()
        self.dismiss_cookie_banner_if_present()
        path = (self.page.url.split("epakgroup.com", 1)[-1].split("?")[0].rstrip("/") or "/")
        need_home = "auth.epakgroup.com" in self.page.url or path not in ("", "/")
        if need_home:
            last_error: Exception | None = None
            for attempt in range(1, max(settings.MALL_UI_GOTO_RETRIES, 1) + 1):
                try:
                    self.page.goto(
                        self.home_url,
                        wait_until=settings.MALL_UI_GOTO_WAIT_UNTIL,
                        timeout=settings.MALL_UI_NAV_TIMEOUT_MS,
                    )
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if attempt < settings.MALL_UI_GOTO_RETRIES:
                        self.page.wait_for_timeout(2000)
            if last_error:
                raise AssertionError(f"返回首页失败: {last_error}") from last_error
        self.close_subscribe_popup()
        self.dismiss_cookie_banner_if_present()
        self.page.get_by_text(self.SUPPLY_SECTION_TITLE, exact=True).first.wait_for(
            state="visible",
            timeout=30000,
        )

    def _module_cta_locator(self, name: str):
        link = self.page.locator("a[href]").filter(has_text=name)
        if link.count():
            return link.first
        role = self.page.get_by_role("link", name=name)
        if role.count():
            return role.first
        text = self.page.get_by_text(name, exact=True)
        if text.count():
            return text.first
        return None

    def _open_module_jump(self, spec: dict) -> str:
        self._disable_float_header()
        self.close_subscribe_popup()
        locator = self._module_cta_locator(spec["name"])
        if locator is None:
            raise AssertionError(f"未找到入口「{spec['name']}」")
        locator.scroll_into_view_if_needed(timeout=10000)
        self.page.evaluate(
            """() => {
              const floatHeader = document.querySelector('#floatSearch, [class*="floatSearch"]');
              if (floatHeader) floatHeader.style.pointerEvents = 'none';
            }"""
        )
        return self._click_and_expect_url(
            locator,
            spec["url_fragment"],
            f"{spec['module']}「{spec['name']}」",
            spec["hints"],
        )

    def _wait_for_http_url(self, page: Page) -> None:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=settings.MALL_UI_NAV_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass
        try:
            page.wait_for_function(
                """() => {
                  const href = location.href || '';
                  return href.startsWith('http') && href !== 'about:blank';
                }""",
                timeout=20000,
            )
        except PlaywrightTimeoutError:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=12000)
        except PlaywrightTimeoutError:
            pass

    def _assert_destination_loaded(self, page: Page, label: str, hints: tuple[str, ...]) -> None:
        url = page.url or ""
        if "auth.epakgroup.com" in url and "/user/login" in url:
            raise AssertionError(f"{label}跳到了登录页: {url}")
        body = ""
        try:
            body = page.evaluate("() => (document.body && document.body.innerText) || ''") or ""
        except Exception:
            body = ""
        snippet = " ".join(body.split())
        if self._DEST_ERROR_RE.search(snippet) or self._DEST_ERROR_RE.search(url):
            raise AssertionError(f"{label}打开了错误页: {url}")
        if len(snippet) < 40:
            raise AssertionError(f"{label}页面内容过少，疑似空白: {url}")
        if hints and not any(hint.lower() in snippet.lower() for hint in hints):
            raise AssertionError(f"{label}未出现预期文案 {hints}，url={url}")
        if "/category" in url:
            try:
                page.locator(self.PRODUCT_CARD).first.wait_for(state="visible", timeout=20000)
            except PlaywrightTimeoutError:
                raise AssertionError(f"{label}分类页未出现商品卡片") from None
        self._assert_visible_images_loaded(page, label)

    def _assert_visible_images_loaded(self, page: Page, label: str) -> None:
        elapsed = 0
        poll_ms = 500
        stats = {"visible": 0, "loaded": 0, "broken": 0}
        while elapsed <= 8000:
            stats = page.evaluate(
                """() => {
                  const imgs = Array.from(document.images).filter((img) => {
                    const r = img.getBoundingClientRect();
                    return r.width > 20 && r.height > 20;
                  });
                  return {
                    visible: imgs.length,
                    loaded: imgs.filter((img) => img.complete && img.naturalWidth > 0).length,
                    broken: imgs.filter((img) => img.complete && img.naturalWidth === 0).length,
                  };
                }"""
            )
            if stats["visible"] == 0:
                return
            if stats["loaded"] > 0 and stats["broken"] == 0:
                return
            if stats["loaded"] > 0 and elapsed >= 4000:
                return
            page.wait_for_timeout(poll_ms)
            elapsed += poll_ms
        if stats["visible"] > 0 and stats["loaded"] == 0:
            raise AssertionError(f"{label}页面图片未加载完成: {stats}")

    def _click_and_expect_url(self, locator, url_fragment: str, label: str, hints: tuple[str, ...]) -> str:
        home_page = self.page
        target = None
        try:
            with home_page.context.expect_page(timeout=8000) as popup_info:
                locator.click(timeout=10000, force=True)
            target = popup_info.value
            self._wait_for_http_url(target)
        except PlaywrightTimeoutError:
            for extra in home_page.context.pages:
                if extra is home_page:
                    continue
                if url_fragment.lower() in extra.url.lower():
                    target = extra
                    break
            if target is None:
                target = self.page
                try:
                    target.wait_for_function(
                        """(frag) => (location.href || '').toLowerCase().includes(String(frag).toLowerCase())""",
                        arg=url_fragment,
                        timeout=15000,
                    )
                except PlaywrightTimeoutError:
                    pass
                self._wait_for_http_url(target)

        current = target.url if target else home_page.url
        if url_fragment.lower() not in current.lower():
            href = ""
            try:
                href = locator.get_attribute("href") or ""
            except Exception:
                href = ""
            if href and url_fragment.lower() in href.lower():
                abs_url = href if href.startswith("http") else self.home_url.rstrip("/") + "/" + href.lstrip("/")
                target = self.page
                target.goto(
                    abs_url,
                    wait_until=settings.MALL_UI_GOTO_WAIT_UNTIL,
                    timeout=settings.MALL_UI_NAV_TIMEOUT_MS,
                )
                self._wait_for_http_url(target)
                current = target.url
        if url_fragment.lower() not in current.lower():
            raise AssertionError(f"{label}未打开预期页面，当前 url={current}")
        self._assert_destination_loaded(target, label, hints)
        if target is not None and target is not home_page:
            try:
                target.close()
            except Exception:
                pass
            home_page.bring_to_front()
            self.page = home_page
        return current

    def _disable_float_header(self) -> None:
        self.page.evaluate(
            """() => {
              const floatHeader = document.querySelector('#floatSearch');
              if (floatHeader) floatHeader.style.pointerEvents = 'none';
            }"""
        )

    def _open_category_listing(self) -> None:
        if "/category" in self.page.url:
            return
        cta = None
        for name in self.CATEGORY_CTA_NAMES:
            locator = self.page.get_by_role("link", name=name)
            if locator.count() > 0:
                cta = locator.first
                break
        if cta is None:
            category_url = self.home_url.rstrip("/") + "/category"
            self.page.goto(
                category_url,
                wait_until=settings.MALL_UI_GOTO_WAIT_UNTIL,
                timeout=settings.MALL_UI_NAV_TIMEOUT_MS,
            )
        else:
            cta.click(timeout=10000)
        try:
            self.page.wait_for_url("**/category**", timeout=settings.MALL_UI_NAV_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            if "/category" not in self.page.url:
                raise AssertionError(f"未进入商品分类页: {self.page.url}")
        self.page.locator(self.PRODUCT_CARD).first.wait_for(
            state="visible",
            timeout=30000,
        )

    def _list_catalog_product_candidates(self, preferred_name: str | None = None) -> list[dict]:
        return self.page.evaluate(
            """(preferredName) => {
              const normalize = (text) => (text || '').trim().replace(/\\s+/g, ' ');
              const preferred = (preferredName || '').trim().toLowerCase();
              const cards = Array.from(document.querySelectorAll('[class*="product_item_box"]'));
              const items = [];
              const seen = new Set();
              for (const card of cards) {
                const img = card.querySelector('img[alt]');
                const name = normalize(img?.getAttribute('alt') || card.querySelector('.ellipsis3')?.innerText || '');
                if (!name || seen.has(name)) continue;
                const rect = card.getBoundingClientRect();
                if (rect.width < 20 || rect.height < 20) continue;
                seen.add(name);
                items.push({
                  name,
                  preferred: !!(preferred && name.toLowerCase().includes(preferred)),
                });
              }
              items.sort((a, b) => Number(b.preferred) - Number(a.preferred));
              return items;
            }""",
            preferred_name or "",
        )

    def _click_catalog_product_candidate(self, candidate: dict) -> tuple[bool, Page, str]:
        self._disable_float_header()
        product_name = candidate["name"]
        url_before = self.page.url
        img = self.page.locator(self.PRODUCT_CARD).get_by_alt_text(product_name, exact=True).first
        try:
            img.scroll_into_view_if_needed(timeout=10000)
        except PlaywrightTimeoutError:
            return False, self.page, product_name

        detail_page = self.page
        try:
            with self.page.context.expect_page(timeout=8000) as popup_info:
                img.click(timeout=10000)
            detail_page = popup_info.value
            detail_page.wait_for_load_state("domcontentloaded", timeout=60000)
            if EpakProductDetailPage.is_product_detail_url(detail_page.url):
                return True, detail_page, product_name
        except PlaywrightTimeoutError:
            pass

        resolved = self._resolve_detail_page(url_before, detail_page)
        if resolved:
            return True, resolved, product_name

        try:
            img.click(timeout=10000)
        except PlaywrightTimeoutError:
            pass

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
                arg=url_before,
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

    def open_any_catalog_product(self, preferred_name: str | None = None) -> tuple[str, Page]:
        self.dismiss_cookie_banner_if_present()
        self.close_subscribe_popup()
        self._open_category_listing()
        self.dismiss_cookie_banner_if_present()
        self.close_subscribe_popup()
        self._disable_float_header()

        candidates = self._list_catalog_product_candidates(preferred_name)
        if not candidates:
            raise AssertionError("分类页未找到可点击的商品卡片")

        errors: list[str] = []
        for candidate in candidates:
            navigated, detail_page, product_name = self._click_catalog_product_candidate(candidate)
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
        raise AssertionError(f"分类页尝试多个商品后均未成功跳转，已尝试: {tried}")

    def open_any_one_stop_product(self, preferred_name: str | None = None) -> tuple[str, Page]:
        return self.open_any_catalog_product(preferred_name)

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
        detail = EpakProductDetailPage(page)
        detail.dismiss_image_zoom_overlay()
        for text in EpakProductDetailPage.CTA_TEXT_OPTIONS:
            button = page.get_by_role("button", name=text)
            if button.count() == 0:
                continue
            try:
                button.first.wait_for(state="visible", timeout=5000)
                return
            except PlaywrightTimeoutError:
                continue
        pattern = "|".join(EpakProductDetailPage.CTA_TEXT_OPTIONS)
        page.locator(f"text=/{pattern}/").first.wait_for(
            state="visible",
            timeout=settings.ESB_UI_DETAIL_READY_MS,
        )
