"""EPAK 生产会员中心：只点菜单看加载，不改数据。"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from playwright.sync_api import Page

from config import settings

SKIP_L1 = {
    "切换账号",
    "返回商城",
    "Switch account",
    "Return to marketplace",
    "Sign out",
    "Sign Out",
    "Log out",
    "Logout",
    "退出",
    "退出登录",
    "注销",
}
SKIP_HREF_RE = re.compile(r"sign.?out|log.?out|logout|javascript:", re.I)
LOGIN_HINTS = (
    "Sign in to continue",
    "Welcome to EPAK Sign in",
    "Welcome to EPAK GROUP",
    "欢迎登录",
    "欢迎登录易食包",
    "Create an account",
)
LOGIN_HOST_MARKERS = (
    "/login",
    "/user/login",
    "auth.epakgroup",
    "auth.esbao",
    "auth.ysbpack",
)
# 避免把数量「500,000」误判成 HTTP 500
ERROR_HINT_RE = re.compile(
    r"(?<![\d,])(?:404|500)(?![\d,])|page\s*not\s*found|(?<![A-Za-z])not\s*found(?![A-Za-z])|"
    r"system error|service unavailable|系统错误|服务异常|页面不存在|找不到页面",
    re.I,
)
# 空态文案说明页面已加载（只是业务无数据），不算空白页
LOADED_OK_HINTS = (
    "暂无",
    "没有数据",
    "无数据",
    "还没有",
    "空空如也",
    "新建",
    "新增",
    "创建",
    "No data",
    "No Data",
    "nothing here",
)


class EpakMemberCenterPage:
    def __init__(self, page: Page, home_url: str | None = None):
        self.page = page
        self.home_url = (home_url or settings.EPAK_MEMBER_HOME_URL).strip()

    def close_modals(self) -> None:
        for name in ("Cancel", "取消", "Close", "关闭", "I Accept", "No, Thanks", "No Thanks"):
            try:
                self.page.get_by_role("button", name=name).click(timeout=800, force=True)
                self.page.wait_for_timeout(150)
            except Exception:
                pass
        for sel in (".ant-modal-close", ".ant-drawer-close", '[aria-label="Close"]'):
            try:
                self.page.locator(sel).first.click(timeout=500, force=True)
            except Exception:
                pass
        try:
            self.page.keyboard.press("Escape")
        except Exception:
            pass

    def wait_sider(self, timeout_ms: int = 25000) -> bool:
        # 壳页 title=loading... 时可能还没有 sider；微应用起来后才有 wrapperSilder。
        try:
            self.page.wait_for_function(
                """() => {
                  const sider = document.querySelector('.ant-layout-sider.wrapperSilder, .wrapperSilder, .ant-layout-sider');
                  if (!sider) return false;
                  const menuCount = sider.querySelectorAll(
                    '.ant-menu-item, .ant-menu-submenu-title, [title], .anticon'
                  ).length;
                  const t = (sider.innerText || '') + ' ' + (document.title || '');
                  return menuCount >= 1 || /Home|Product|Inquiry|Customer|首页|商品|客户|询价/.test(t);
                }""",
                timeout=timeout_ms,
            )
        except Exception:
            return False
        self.expand_collapsed_sider()
        self.page.wait_for_timeout(600)
        if self.l1_labels():
            return True
        return bool(
            self.page.evaluate(
                "() => !!document.querySelector('.ant-layout-sider.wrapperSilder, .wrapperSilder')"
            )
        )

    def expand_collapsed_sider(self) -> None:
        try:
            loc = self.page.locator(".ant-layout-sider-trigger, .ant-pro-sider-collapsed-button")
            if loc.count():
                loc.first.click(timeout=2000, force=True)
                self.page.wait_for_timeout(400)
                return
        except Exception:
            pass
        self.page.evaluate(
            """() => {
              const trigger = document.querySelector(
                '.ant-layout-sider-trigger, .ant-pro-sider-collapsed-button'
              );
              trigger?.click();
            }"""
        )
        self.page.wait_for_timeout(400)

    def open_home(self) -> None:
        self.page.goto(
            self.home_url,
            wait_until="commit",
            timeout=settings.MALL_UI_NAV_TIMEOUT_MS,
        )
        try:
            self.page.wait_for_load_state("load", timeout=60000)
        except Exception:
            pass
        # 微应用会在 load 之后才挂侧栏，不要刷新页面，否则会打断加载。
        if self.wait_sider(90000):
            self.close_modals()
            return
        self.close_modals()
        print(
            f"[member] open_home wait failed url={self.page.url} title={self.page.title()!r}",
            flush=True,
        )

    def l1_labels(self) -> list[str]:
        return self.page.evaluate(
            """() => {
              const sider = document.querySelector('.ant-layout-sider, aside');
              if (!sider) return [];
              const box = sider.getBoundingClientRect();
              const seen = [];
              const push = (raw) => {
                const t = (raw || '').replace(/\\s+/g, ' ').trim();
                if (!t || t.length > 32) return;
                if (!seen.includes(t)) seen.push(t);
              };
              const nodes = sider.querySelectorAll(
                'label, a span, span, a, .ant-menu-title-content, .ant-menu-item, .ant-menu-submenu-title'
              );
              for (const el of nodes) {
                const r = el.getBoundingClientRect();
                if (r.height < 8) continue;
                if (box.width > 40 && (r.left < box.left - 2 || r.left > box.left + box.width)) continue;
                push(el.innerText);
                push(el.getAttribute('title'));
                push(el.getAttribute('aria-label'));
              }
              return seen;
            }"""
        )

    def click_l1(self, name: str) -> bool:
        loc = self.page.locator(".ant-layout-sider, aside").get_by_text(name, exact=True)
        if loc.count() == 0:
            loc = self.page.get_by_text(name, exact=True)
        if loc.count() == 0:
            return False
        loc.first.click(timeout=8000, force=True)
        self.page.wait_for_timeout(1200)
        self.close_modals()
        return True

    def expand_submenus(self) -> None:
        titles = self.page.locator("div.ant-menu-submenu-title")
        for i in range(titles.count()):
            try:
                titles.nth(i).click(timeout=2500)
                self.page.wait_for_timeout(350)
            except Exception:
                continue
        for _ in range(10):
            opened = self.page.evaluate(
                """() => {
                  let n = 0;
                  const titles = Array.from(document.querySelectorAll('.ant-menu-submenu-title'));
                  for (const el of titles) {
                    const li = el.closest('li');
                    const open = li && (
                      li.className.includes('ant-menu-submenu-open') ||
                      el.getAttribute('aria-expanded') === 'true'
                    );
                    if (!open) {
                      el.scrollIntoView({block: 'nearest'});
                      el.click();
                      n += 1;
                    }
                  }
                  return n;
                }"""
            )
            self.page.wait_for_timeout(400)
            if not opened:
                break

    def collect_leaves(self) -> list[dict]:
        items = self.page.evaluate(
            """() => {
              const sider = document.querySelector('.ant-layout-sider, aside');
              const right = sider ? sider.getBoundingClientRect().right : 80;
              const seen = new Set();
              const out = [];
              for (const a of document.querySelectorAll('a[href*="memberCenter"]')) {
                const href = a.href || '';
                if (!href.includes('/memberCenter/')) continue;
                const r = a.getBoundingClientRect();
                if (r.left < right + 8 || r.left > 430) continue;
                if (r.top < 50 || r.height < 10) continue;
                if (seen.has(href)) continue;
                seen.add(href);
                const text = (a.innerText || a.getAttribute('title') || '').replace(/\\s+/g, ' ').trim();
                out.push({text, href});
              }
              return out;
            }"""
        )
        leaves = []
        for item in items or []:
            href = item.get("href") or ""
            parts = [p for p in urlparse(href).path.split("/") if p]
            if len(parts) <= 2:
                continue
            leaves.append(item)
        return leaves

    def click_href(self, href: str) -> bool:
        loc = self.page.locator(f'a[href="{href}"]')
        if loc.count():
            try:
                loc.first.click(timeout=4000, force=True)
                return True
            except Exception:
                pass
        return bool(
            self.page.evaluate(
                """(href) => {
                  const a = Array.from(document.querySelectorAll('a')).find(x => x.href === href);
                  if (!a) return false;
                  a.click();
                  return true;
                }""",
                href,
            )
        )

    def wait_content(self) -> None:
        self.wait_sider(12000)
        self.page.wait_for_timeout(settings.EPAK_UI_MENU_WAIT_MS)
        self.close_modals()
        self.page.wait_for_timeout(400)

    def content_state(self) -> dict:
        return self.page.evaluate(
            """() => {
              const content = document.querySelector('.ant-layout-content');
              const raw = (content?.innerText || '').replace(/\\s+/g,' ').trim();
              const cleaned = raw.replace(
                /Copyright\\s*©?\\s*(Full chain digital solutions|欧派特|易包装|瑞享包|易食包).*/i,
                ''
              ).trim();
              const spin = !!document.querySelector('.ant-spin-spinning, .ant-spin-dot');
              const hasUi = !!(content && content.querySelector(
                '.ant-table, .ant-form, .ant-empty, .ant-btn, .ant-card, .ant-list, ' +
                '.ant-page-header, .ant-pro-page-header-wrap, form, table, button'
              ));
              return {
                contentLen: cleaned.length,
                snippet: cleaned.slice(0, 140),
                spin,
                hasUi,
              };
            }"""
        )

    def is_login(self) -> bool:
        url = (self.page.url or "").lower()
        if "membercenter" not in url and any(x in url for x in LOGIN_HOST_MARKERS):
            return True
        try:
            text = self.page.evaluate("() => (document.body?.innerText || '').slice(0, 500)") or ""
        except Exception:
            return False
        if "memberCenter" in (self.page.url or ""):
            return False
        return any(x in text for x in LOGIN_HINTS)

    def classify(self) -> str:
        if self.is_login():
            return "login"
        st = self.content_state()
        snippet = st.get("snippet") or ""
        text = snippet + " " + (self.page.url or "")
        if ERROR_HINT_RE.search(text):
            return "error"
        if st.get("spin") and st.get("contentLen", 0) < 40:
            return "loading"
        if any(hint in snippet for hint in LOADED_OK_HINTS) or st.get("hasUi"):
            return "ok"
        if st.get("contentLen", 0) < settings.EPAK_UI_MENU_EMPTY_MIN_CHARS:
            return "empty"
        return "ok"
