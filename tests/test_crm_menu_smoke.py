"""CRM 侧栏全菜单可达冒烟（UI 改版回归骨架）。

用法:
  pytest tests/test_crm_menu_smoke.py -m crm_ui
  pytest tests/test_crm_menu_smoke.py -k sales_clue
  # 浏览器兼容（默认仍是 chromium；显式传入才会矩阵展开）:
  pytest tests/test_crm_menu_smoke.py -m crm_ui --ui-browsers=chromium,firefox,webkit

说明:
  - 使用 authenticated_page（接口登录态注入），与 test_login_token 一致
  - 断言刻意偏轻：不绑易变 class，只验「能点开且非登录/非 404/非白屏」
  - 看板等可能无权限：allow_no_permission=True，无权限时记 warning 不算失败
  - 改版后若菜单文案变化，只需改 CRM_SIDEBAR_MENUS
"""
from __future__ import annotations

import allure
import pytest
from playwright.sync_api import Page

from config.settings import APP_HOME_URL
from pages.crm_page import CrmPage
from pages.home_page import HomePage


# 与 testcases/CRM_UI改版_回归矩阵.xlsx「菜单可达检查表」对齐
CRM_SIDEBAR_MENUS: list[dict] = [
    {
        "case_id": "MNU-01",
        "title": "首页",
        "path": ("首页",),
        "priority": "P1",
        "allow_no_permission": False,
    },
    {
        "case_id": "MNU-02",
        "title": "客户",
        "path": ("客户",),
        "priority": "P0",
        "allow_no_permission": False,
    },
    {
        "case_id": "MNU-03",
        "title": "客户查重",
        "path": ("客户", "客户查重"),
        "priority": "P0",
        "allow_no_permission": False,
    },
    {
        "case_id": "MNU-04",
        "title": "销售机会",
        "path": ("销售机会",),
        "priority": "P1",
        "allow_no_permission": False,
    },
    {
        "case_id": "MNU-05",
        "title": "联系人",
        "path": ("联系人",),
        "priority": "P1",
        "allow_no_permission": False,
    },
    {
        "case_id": "MNU-06",
        "title": "销售线索",
        "path": ("销售线索",),
        "priority": "P0",
        "allow_no_permission": False,
    },
    {
        "case_id": "MNU-07",
        "title": "活动记录",
        "path": ("活动记录",),
        "priority": "P0",
        "allow_no_permission": False,
    },
    {
        "case_id": "MNU-08",
        "title": "拜访日程",
        "path": ("拜访日程",),
        "priority": "P1",
        "allow_no_permission": False,
    },
    {
        "case_id": "MNU-09",
        "title": "线索分配规则",
        "path": ("系统设置", "线索分配规则"),
        "priority": "P0",
        "allow_no_permission": False,
    },
    {
        "case_id": "MNU-10",
        "title": "客户分配规则",
        "path": ("系统设置", "客户分配规则"),
        "priority": "P0",
        "allow_no_permission": False,
    },
    {
        "case_id": "MNU-11",
        "title": "权限组管理",
        "path": ("系统设置", "权限组管理"),
        "priority": "P0",
        "allow_no_permission": False,
    },
    {
        "case_id": "MNU-12",
        "title": "线索回收规则",
        "path": ("系统设置", "线索回收规则"),
        "priority": "P1",
        "allow_no_permission": False,
    },
    {
        "case_id": "MNU-13",
        "title": "客户回收规则",
        "path": ("系统设置", "客户回收规则"),
        "priority": "P1",
        "allow_no_permission": False,
    },
    {
        "case_id": "MNU-14",
        "title": "数据共享规则",
        "path": ("系统设置", "数据共享规则"),
        "priority": "P1",
        "allow_no_permission": False,
    },
    {
        "case_id": "MNU-15",
        "title": "用户企微绑定",
        "path": ("系统设置", "用户企微绑定"),
        "priority": "P1",
        "allow_no_permission": False,
    },
    {
        "case_id": "MNU-16",
        "title": "企微好友池",
        "path": ("系统设置", "企微好友池"),
        "priority": "P1",
        "allow_no_permission": False,
    },
    {
        "case_id": "MNU-17",
        "title": "线索看板",
        "path": ("线索看板",),
        "priority": "P1",
        "allow_no_permission": True,
    },
    {
        "case_id": "MNU-18",
        "title": "客户跟进看板",
        "path": ("客户跟进看板",),
        "priority": "P1",
        "allow_no_permission": True,
    },
]


def _menu_ids() -> list[str]:
    return [m["case_id"] for m in CRM_SIDEBAR_MENUS]


def _menu_by_id(case_id: str) -> dict:
    for item in CRM_SIDEBAR_MENUS:
        if item["case_id"] == case_id:
            return item
    raise KeyError(case_id)


@pytest.fixture
def crm_ready_page(authenticated_page) -> Page:
    """注入登录态 → 进平台 → 打开 CRM 2.0，返回 CRM 所在 page（可能是弹窗页）。"""
    page = authenticated_page
    with allure.step("进入平台首页"):
        page.goto(APP_HOME_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        assert "login" not in page.url.lower(), f"登录态注入失败: {page.url}"

    home = HomePage(page)
    with allure.step("打开 CRM 2.0"):
        crm_page = home.open_crm_2()
        crm_page.wait_for_timeout(2500)
        home.assert_crm_page_loaded(crm_page)
        assert "login" not in crm_page.url.lower(), f"进入 CRM 后掉登录: {crm_page.url}"
    return crm_page


@allure.feature("CRM UI 改版回归")
@allure.story("侧栏菜单可达冒烟")
@pytest.mark.crm_ui
@pytest.mark.parametrize("case_id", _menu_ids())
def test_crm_sidebar_menu_reachable(crm_ready_page: Page, case_id: str):
    meta = _menu_by_id(case_id)
    path: tuple[str, ...] = tuple(meta["path"])
    title = meta["title"]
    allure.dynamic.title(f"{case_id} {title}（{' / '.join(path)}）")
    allure.dynamic.severity(meta["priority"])
    allure.dynamic.description(
        "轻量可达：点击侧栏菜单后未掉登录、非 404/白屏；"
        "看板类允许无权限提示。"
    )

    crm = CrmPage(crm_ready_page)
    try:
        with allure.step(f"点击菜单路径: {' → '.join(path)}"):
            crm.open_menu_path(*path)
            crm_ready_page.wait_for_timeout(1200)

        with allure.step("断言页面可达"):
            status = crm.assert_menu_reachable(
                title,
                allow_no_permission=bool(meta["allow_no_permission"]),
            )
            allure.attach(
                f"url={crm_ready_page.url}\nstatus={status}\npath={' / '.join(path)}",
                name=f"{case_id}_reachability",
                attachment_type=allure.attachment_type.TEXT,
            )
            if status == "permission_denied":
                allure.attach(
                    "当前账号无该菜单权限（已按 allow_no_permission 放行）",
                    name=f"{case_id}_permission_note",
                    attachment_type=allure.attachment_type.TEXT,
                )
    except Exception:
        with allure.step("失败截图"):
            png = crm_ready_page.screenshot(full_page=True)
            allure.attach(
                png,
                name=f"{case_id}_failed",
                attachment_type=allure.attachment_type.PNG,
            )
        raise


@allure.feature("CRM UI 改版回归")
@allure.story("侧栏菜单可达冒烟")
@allure.title("侧栏菜单批量可达（单会话串行，便于人工盯屏）")
@pytest.mark.crm_ui
@pytest.mark.crm_ui_serial
def test_crm_sidebar_menus_serial_smoke(crm_ready_page: Page):
    """一条用例串行点完全部菜单，适合改版后人工盯着跑一轮。"""
    crm = CrmPage(crm_ready_page)
    failures: list[str] = []
    results: list[str] = []

    for meta in CRM_SIDEBAR_MENUS:
        case_id = meta["case_id"]
        path = tuple(meta["path"])
        title = meta["title"]
        with allure.step(f"{case_id} {title}"):
            try:
                crm.open_menu_path(*path)
                crm_ready_page.wait_for_timeout(900)
                status = crm.assert_menu_reachable(
                    title,
                    allow_no_permission=bool(meta["allow_no_permission"]),
                )
                results.append(f"{case_id} {title}: {status}")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{case_id} {title}: {exc}")
                try:
                    png = crm_ready_page.screenshot(full_page=True)
                    allure.attach(
                        png,
                        name=f"{case_id}_failed",
                        attachment_type=allure.attachment_type.PNG,
                    )
                except Exception:
                    pass

    allure.attach(
        "\n".join(results + [f"FAIL {x}" for x in failures]),
        name="menu_smoke_summary",
        attachment_type=allure.attachment_type.TEXT,
    )
    assert not failures, "侧栏菜单可达失败:\n" + "\n".join(failures)
