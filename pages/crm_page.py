from __future__ import annotations

import re
import time

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect

from utils.base_page import BasePage


# 改版后 DOM 可能变化：优先侧栏容器，再回退到整页文本匹配
_SIDEBAR_ROOT_SELECTORS = [
    ".ant-layout-sider",
    ".ant-menu",
    ".el-aside",
    ".el-menu",
    "aside",
    "[class*='sider']",
    "[class*='SideBar']",
    "[class*='sidebar']",
    "[class*='left-menu']",
]

_MENU_ITEM_PATTERNS = [
    "text={name}",
    "a:has-text('{name}')",
    "[title='{name}']",
    "[aria-label='{name}']",
    ".ant-menu-item:has-text('{name}')",
    ".ant-menu-submenu-title:has-text('{name}')",
    ".el-menu-item:has-text('{name}')",
    ".el-submenu__title:has-text('{name}')",
    "li:has-text('{name}')",
    "span:has-text('{name}')",
]

_PERMISSION_HINT_RE = re.compile(
    r"无权限|没有权限|暂无权限|权限不足|无权访问|not\s*authorized|forbidden|403",
    re.I,
)

_ERROR_HINT_RE = re.compile(
    r"(?<!\d)404(?!\d)|页面不存在|找不到页面|系统错误|服务异常|page\s*not\s*found",
    re.I,
)

# 侧栏 / 子菜单在弱网下可能较晚渲染
_DEFAULT_MENU_WAIT_MS = 30000


class CrmPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)

    def _sidebar_roots(self) -> list:
        roots = []
        for selector in _SIDEBAR_ROOT_SELECTORS:
            loc = self.page.locator(selector)
            if loc.count() > 0:
                roots.append(loc.first)
        return roots

    def wait_sidebar_ready(self, timeout_ms: int = _DEFAULT_MENU_WAIT_MS) -> None:
        """等待侧栏菜单容器出现且至少有一个可见菜单项。"""
        deadline = time.time() + timeout_ms / 1000
        last_error: Exception | None = None
        while time.time() < deadline:
            for selector in _SIDEBAR_ROOT_SELECTORS:
                root = self.page.locator(selector).first
                try:
                    if root.count() == 0:
                        continue
                    if not root.is_visible():
                        continue
                    # 常见一级菜单任一出现即可认为侧栏就绪
                    for probe in ("客户", "销售线索", "首页", "系统设置"):
                        item = root.get_by_text(probe, exact=False).first
                        if item.count() > 0 and item.is_visible():
                            return
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
            self.page.wait_for_timeout(300)
        detail = f"（末次错误: {last_error}）" if last_error else ""
        raise AssertionError(f"侧栏菜单未在 {timeout_ms}ms 内加载完成{detail}")

    def _menu_locator_candidates(self, menu_name: str):
        patterns = [p.format(name=menu_name) for p in _MENU_ITEM_PATTERNS]
        for root in self._sidebar_roots():
            for pattern in patterns:
                yield root.locator(pattern).first
        for pattern in patterns:
            yield self.page.locator(pattern).first

    def _find_visible_menu(self, menu_name: str, timeout_ms: int = _DEFAULT_MENU_WAIT_MS):
        """智能等待：在侧栏里找**可见**菜单项（禁止用 .first 命中隐藏节点）。"""
        deadline = time.time() + timeout_ms / 1000
        last_error: Exception | None = None
        while time.time() < deadline:
            roots = self._sidebar_roots()
            scopes = roots if roots else [self.page]
            for root in scopes:
                for exact in (True, False):
                    loc = root.get_by_text(menu_name, exact=exact)
                    for i in range(min(loc.count(), 12)):
                        node = loc.nth(i)
                        try:
                            if not node.is_visible():
                                continue
                            text = (node.inner_text() or "").strip().replace("\n", "")
                            if not text or menu_name not in text:
                                continue
                            if menu_name == "销售线索" and "看板" in text:
                                continue
                            item = node.locator(
                                "xpath=ancestor-or-self::li[contains(@class,'ant-menu-item') "
                                "or contains(@class,'ant-menu-submenu')][1]"
                            )
                            target = item.first if item.count() > 0 else node
                            expect(target).to_be_visible(timeout=1500)
                            return target
                        except Exception as exc:  # noqa: BLE001
                            last_error = exc
                            continue
            self.page.wait_for_timeout(250)
        detail = f"（末次错误: {last_error}）" if last_error else ""
        raise AssertionError(f"CRM 页面未找到菜单: {menu_name}{detail}")

    def expand_menu_if_needed(
        self, menu_name: str, *, timeout_ms: int = _DEFAULT_MENU_WAIT_MS
    ) -> None:
        """展开可折叠菜单（如系统设置），并等待子菜单区域出现。"""
        loc = self._find_visible_menu(menu_name, timeout_ms=timeout_ms)
        try:
            loc.scroll_into_view_if_needed(timeout=5000)
            expanded = (loc.get_attribute("aria-expanded") or "").lower()
            class_name = loc.get_attribute("class") or ""
            already_open = (
                expanded == "true"
                or "is-opened" in class_name
                or "ant-menu-submenu-open" in class_name
                or "ant-menu-submenu-selected" in class_name
            )
            if not already_open:
                loc.click(timeout=8000)
                # 等展开动画 / 子项懒加载
                self.page.wait_for_timeout(400)
        except PlaywrightTimeoutError:
            # 再试一次强制点击
            loc.click(force=True, timeout=8000)
            self.page.wait_for_timeout(400)

        # 展开后侧栏高度可能变化，给子项一点渲染时间（由后续 wait leaf 兜底）
        self.page.wait_for_load_state("domcontentloaded", timeout=10000)

    def open_menu(self, menu_name: str, *, timeout_ms: int = _DEFAULT_MENU_WAIT_MS) -> None:
        self.wait_sidebar_ready(timeout_ms=min(timeout_ms, _DEFAULT_MENU_WAIT_MS))
        loc = self._find_visible_menu(menu_name, timeout_ms=timeout_ms)
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                loc.scroll_into_view_if_needed(timeout=5000)
                loc.click(timeout=8000)
                self.page.wait_for_load_state("domcontentloaded", timeout=15000)
                # networkidle 在 SPA 上可能永远等不到；用短超时尽力等一轮
                try:
                    self.page.wait_for_load_state("networkidle", timeout=5000)
                except PlaywrightTimeoutError:
                    pass
                return
            except PlaywrightTimeoutError as exc:
                last_error = exc
                # 菜单可能被重渲染，重新定位
                loc = self._find_visible_menu(menu_name, timeout_ms=timeout_ms)
                self.page.wait_for_timeout(400 * (attempt + 1))
        raise AssertionError(f"CRM 页面点击菜单失败: {menu_name}（末次错误: {last_error}）")

    def open_menu_path(self, *menu_names: str, timeout_ms: int = _DEFAULT_MENU_WAIT_MS) -> None:
        """按路径点击菜单。末级为真正入口，中间级展开并智能等待子项出现。"""
        if not menu_names:
            raise AssertionError("菜单路径不能为空")
        self.wait_sidebar_ready(timeout_ms=timeout_ms)
        *parents, leaf = menu_names
        for parent in parents:
            # 子项已可见则不必再点父级；否则展开并等待子项
            try:
                self._find_visible_menu(leaf, timeout_ms=3000)
            except AssertionError:
                self.expand_menu_if_needed(parent, timeout_ms=timeout_ms)
                # 展开后必须等到叶子菜单真正可见（弱网关键）
                self._find_visible_menu(leaf, timeout_ms=timeout_ms)
        self.open_menu(leaf, timeout_ms=timeout_ms)

    def page_text_sample(self, limit: int = 2000) -> str:
        try:
            return (self.page.inner_text("body") or "")[:limit]
        except Exception:
            return ""

    def assert_not_kicked_to_login(self) -> None:
        assert "login" not in self.page.url.lower(), f"操作后掉回登录页: {self.page.url}"

    def assert_menu_reachable(
        self,
        menu_name: str,
        *,
        allow_no_permission: bool = False,
    ) -> str:
        """
        轻量可达断言（适配 UI 改版）：
        - 未掉登录
        - 非明显 404/系统错误
        - 无权限时：allow_no_permission=True 则记为 skip 语义（返回 permission_denied）
        返回: ok | permission_denied
        """
        self.assert_not_kicked_to_login()
        # 等内容区出现一点文本，避免点开后仍在 loading
        deadline = time.time() + 15
        sample = ""
        while time.time() < deadline:
            sample = self.page_text_sample()
            if len(sample.strip()) >= 8:
                break
            self.page.wait_for_timeout(300)
        if _ERROR_HINT_RE.search(sample):
            raise AssertionError(
                f"菜单「{menu_name}」疑似错误页。url={self.page.url} text={sample[:240]}"
            )
        if _PERMISSION_HINT_RE.search(sample):
            if allow_no_permission:
                return "permission_denied"
            raise AssertionError(
                f"菜单「{menu_name}」无权限且未标记可接受。url={self.page.url}"
            )
        if len(sample.strip()) < 8:
            raise AssertionError(
                f"菜单「{menu_name}」打开后页面内容过少（疑似白屏）。url={self.page.url}"
            )
        return "ok"
