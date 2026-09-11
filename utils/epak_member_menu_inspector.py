"""会员中心菜单加载巡检：只打开页面，不改数据。"""
from __future__ import annotations

import re
from typing import Any, Callable
from urllib.parse import urlparse

from api.client import ApiClient
from api.services.auth_service import AuthService
from config import settings
from pages.epak_member_center_page import SKIP_HREF_RE, SKIP_L1, EpakMemberCenterPage
from utils.epak_auth_cookie import (
    cookie_domain_from_url,
    inject_epak_ui_auth,
    inject_esbao_ui_auth,
)

_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9\u4e00-\u9fff]+")


def _safe_name(text: str) -> str:
    return _SAFE_NAME_RE.sub("-", text).strip("-")[:40] or "menu"


def run_member_menu_inspection(
    browser,
    collector,
    prefix: str,
    *,
    home_url: str,
    login_data: dict[str, Any],
    inject_auth: Callable,
    locale: str,
) -> dict[str, Any]:
    """展开全部二级后点每个三级，检查跳登录 / 空白。"""
    cookie_domain = cookie_domain_from_url(home_url)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        locale=locale,
        bypass_csp=True,
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
    )
    context.set_default_navigation_timeout(settings.MALL_UI_NAV_TIMEOUT_MS)
    inject_auth(context, login_data, cookie_domain=cookie_domain, page_url=home_url)
    page = context.new_page()
    member = EpakMemberCenterPage(page, home_url)
    results: list[dict[str, Any]] = []
    seen_href: set[str] = set()
    try:
        member.open_home()
        if member.is_login():
            collector.save_screenshot(page, f"06-{prefix}-member-login.png", full_page=False)
            raise AssertionError(f"会员中心未登录: {page.url}")
        collector.save_screenshot(page, f"06-{prefix}-member-home.png", full_page=False)
        collector.add_step("打开会员中心", "pass", url=page.url)

        l1_names = [n for n in member.l1_labels() if n not in SKIP_L1]
        if not l1_names:
            member.expand_collapsed_sider()
            page.wait_for_timeout(800)
            l1_names = [n for n in member.l1_labels() if n not in SKIP_L1]
        if not l1_names:
            debug = page.evaluate(
                """() => ({
                  url: location.href,
                  title: document.title,
                  bodyLen: (document.body && document.body.innerText || '').length,
                  snippet: (document.body && document.body.innerText || '').replace(/\\s+/g,' ').slice(0, 180),
                  hasSider: !!document.querySelector('.ant-layout-sider, aside'),
                })"""
            )
            collector.save_screenshot(page, f"99-{prefix}-failure.png", full_page=False)
            raise AssertionError(f"会员中心未采集到一级菜单: {debug}")

        for l1 in l1_names:
            member.click_l1(l1)
            member.wait_content()
            if member.is_login():
                item = {"path": l1, "l1": l1, "l3": "", "url": page.url, "status": "login"}
                results.append(item)
                collector.save_screenshot(
                    page, f"fail-menu-{_safe_name(l1)}.png", full_page=False
                )
                member.open_home()
                continue
            member.expand_submenus()
            raw_leaves = [
                leaf
                for leaf in member.collect_leaves()
                if leaf.get("href") and not SKIP_HREF_RE.search(leaf["href"])
            ]
            leaves = [leaf for leaf in raw_leaves if leaf["href"] not in seen_href]
            if not leaves:
                if raw_leaves:
                    continue
                path_parts = [p for p in urlparse(page.url).path.split("/") if p]
                if len(path_parts) <= 1:
                    continue
                status = member.classify()
                st = member.content_state()
                results.append(
                    {
                        "path": l1,
                        "l1": l1,
                        "l3": "",
                        "href": page.url,
                        "url": page.url,
                        "status": status,
                        **st,
                    }
                )
                print(f"[{status}] {l1} | {page.url} len={st.get('contentLen')}", flush=True)
                continue
            for leaf in leaves:
                href = leaf["href"]
                text = leaf.get("text") or href.rsplit("/", 1)[-1]
                seen_href.add(href)
                path = f"{l1} / {text}"
                if member.is_login() or "membercenter" not in (page.url or "").lower():
                    member.open_home()
                    member.click_l1(l1)
                    member.expand_submenus()
                clicked = member.click_href(href)
                extra = ""
                if not clicked:
                    page.goto(href, wait_until="commit", timeout=settings.MALL_UI_NAV_TIMEOUT_MS)
                    extra = "goto"
                member.wait_content()
                status = member.classify()
                if status == "loading":
                    page.wait_for_timeout(3000)
                    status = member.classify()
                st = member.content_state()
                results.append(
                    {
                        "path": path,
                        "l1": l1,
                        "l3": text,
                        "href": href,
                        "url": page.url,
                        "status": status,
                        "clicked": clicked,
                        "extra": extra,
                        **st,
                    }
                )
                print(f"[{status}] {path} | {page.url} len={st.get('contentLen')}", flush=True)
                if status in {"login", "empty", "error"}:
                    collector.save_screenshot(
                        page, f"fail-menu-{_safe_name(path)}.png", full_page=False
                    )
                if status == "login":
                    member.open_home()
                    member.click_l1(l1)
                    member.expand_submenus()
    finally:
        try:
            context.close()
        except Exception:
            pass

    counts: dict[str, int] = {}
    for row in results:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    failed = [r for r in results if r["status"] in {"login", "empty", "error", "loading"}]
    collector.add_check(
        "member_menus",
        {
            "home_url": home_url,
            "total": len(results),
            "counts": counts,
            "failed": [{"path": r["path"], "status": r["status"], "url": r.get("url", "")} for r in failed],
        },
    )
    collector.add_step(
        "会员中心菜单加载",
        "fail" if failed else "pass",
        total=len(results),
        **counts,
    )
    if not results:
        raise AssertionError("会员中心未采集到可检查的菜单页")
    if failed:
        preview = "; ".join(f"{r['path']}={r['status']}" for r in failed[:12])
        raise AssertionError(f"会员中心菜单加载失败 {len(failed)}/{len(results)}: {preview}")
    return {"results": results, "counts": counts}


def _record_token_step(collector, login_data: dict[str, Any]) -> None:
    collector.add_step(
        "会员中心获取 token",
        "pass",
        user_id=login_data.get("userId"),
        member_id=login_data.get("memberId"),
        account_name=login_data.get("name") or login_data.get("company"),
    )


def run_epak_member_menu_inspection(browser, collector, prefix: str = "epak") -> dict[str, Any]:
    """登录生产会员中心，展开全部二级后点每个三级，检查跳登录 / 空白。"""
    login_data = AuthService(ApiClient(timeout=settings.API_TIMEOUT_SECONDS)).login_epak_ui()
    _record_token_step(collector, login_data)
    return run_member_menu_inspection(
        browser,
        collector,
        prefix,
        home_url=settings.EPAK_MEMBER_HOME_URL,
        login_data=login_data,
        inject_auth=inject_epak_ui_auth,
        locale="en-US",
    )


def run_esbao_member_menu_inspection(browser, collector, prefix: str = "esbao") -> dict[str, Any]:
    """登录易食包生产会员中心（中文，不切语言），点每个三级检查加载，不改数据。"""
    login_data = AuthService(ApiClient(timeout=settings.API_TIMEOUT_SECONDS)).login_esbao_ui()
    _record_token_step(collector, login_data)
    return run_member_menu_inspection(
        browser,
        collector,
        prefix,
        home_url=settings.ESB_MEMBER_HOME_URL,
        login_data=login_data,
        inject_auth=inject_esbao_ui_auth,
        locale="zh-CN",
    )
