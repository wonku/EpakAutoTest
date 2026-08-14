"""CRM 拜访日程 UI 冒烟：查询 / 新建 / 编辑 / 关联 / 解绑 / 删除，各一条独立用例。

跟进对象默认「北京中镜眼镜有限责任公司」（现成客户数据）。

运行:
  $env:HEADLESS="false"
  pytest tests/test_crm_visit_schedule_smoke.py -m crm_ui -v -s
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import allure
import pytest
from playwright.sync_api import expect

from config.settings import (
    APP_HOME_URL,
    CRM_UI_PAUSE_ON_FAILURE,
    CRM_UI_VISIT_CUSTOMER_KEYWORD,
    PLATFORM_BASE_URL,
    PROJECT_ROOT,
)
from pages.crm_page import CrmPage
from pages.crm_visit_schedule_page import CrmVisitSchedulePage
from pages.home_page import HomePage

pytestmark = pytest.mark.crm_ui

VISIT_URL = f"{PLATFORM_BASE_URL}/memberCenter/crm2Ability/visitSchedule"
_CTX_FILE = PROJECT_ROOT / "reports" / "crm_visit_last_created.json"


def _log(msg: str) -> None:
    print(f"[visit] {msg}", flush=True)


def _screenshot_on_fail(page, name: str) -> None:
    try:
        png = page.screenshot(full_page=True, timeout=10000)
        allure.attach(png, name=name, attachment_type=allure.attachment_type.PNG)
    except Exception:
        pass
    if CRM_UI_PAUSE_ON_FAILURE:
        page.pause()


def _goto_resilient(page, target: str, *, label: str) -> None:
    _log(f"{label}: goto {target}")
    try:
        page.goto(target, wait_until="domcontentloaded", timeout=60000)
    except Exception as exc:
        _log(f"{label}: 超时 ({exc.__class__.__name__})，改 commit")
        page.goto(target, wait_until="commit", timeout=60000)
    page.wait_for_timeout(1200)


def _open_visit_via_menu(authenticated_page):
    page = authenticated_page
    _goto_resilient(page, APP_HOME_URL, label="平台首页")
    assert "login" not in page.url.lower(), f"登录态注入失败: {page.url}"
    home = HomePage(page)
    _log("点击侧栏 CRM 2.0")
    crm_tab = home.open_crm_2()
    crm_tab.wait_for_timeout(2000)
    home.assert_crm_page_loaded(crm_tab)
    page = crm_tab
    crm = CrmPage(page)
    visit = CrmVisitSchedulePage(page)
    page.set_default_timeout(25000)
    crm.wait_sidebar_ready()
    _log("点击侧栏「拜访日程」")
    crm.open_menu_path("拜访日程")
    visit.assert_list_ready()
    _log(f"拜访日程就绪 url={page.url}")
    return page, crm, visit


def _save_ctx(payload: dict) -> None:
    _CTX_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CTX_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_ctx() -> dict:
    if not _CTX_FILE.is_file():
        return {}
    try:
        return json.loads(_CTX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _customer() -> str:
    name = (CRM_UI_VISIT_CUSTOMER_KEYWORD or "").strip()
    assert name, "请配置 CRM_UI_VISIT_CUSTOMER_KEYWORD"
    return name


@allure.feature("CRM UI 改版回归")
@allure.story("拜访日程查询")
@allure.title("拜访日程：按跟进对象查询")
def test_crm_visit_schedule_query_smoke(authenticated_page, crm_visit_schedule_service, crm_auth):
    customer = _customer()
    page = authenticated_page
    try:
        page, crm, visit = _open_visit_via_menu(page)
        with allure.step(f"按跟进对象查询: {customer}"):
            visit.click_reset()
            body = visit.search_schedules(customer_keyword=customer)
            table = page.locator(".ant-table-tbody tr").filter(has_text=customer)
            assert table.count() > 0, f"查询后列表无 {customer}"
            sample = (table.first.inner_text() or "").replace("\n", " ")
            assert customer in sample, f"行未含跟进对象: {sample!r}"
            _log(f"查询命中 {table.count()} 行 sample={sample[:120]!r}")
            if body and body.get("code") == 1000:
                rows = crm_visit_schedule_service.extract_rows(body)
                assert rows, f"查询接口无数据: {body}"
        expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=8000)
        crm.assert_not_kicked_to_login()
    except Exception:
        _screenshot_on_fail(page, "visit_query_failed")
        raise


@allure.feature("CRM UI 改版回归")
@allure.story("拜访日程新建")
@allure.title("拜访日程：新建后列表可见")
def test_crm_visit_schedule_create_smoke(
    authenticated_page, crm_visit_schedule_service, crm_auth
):
    customer = _customer()
    stamp = datetime.now().strftime("%m%d%H%M%S")
    name = f"自动化拜访{stamp}"
    remark = f"自动化新建{stamp}"
    page = authenticated_page
    try:
        page, crm, visit = _open_visit_via_menu(page)
        with allure.step(f"新建日程 {name} → {customer}"):
            visit.open_create_form()
            visit.fill_create_form(
                name=name, customer_keyword=customer, remark=remark
            )
            saved = visit.save_form()
            if saved:
                assert saved.get("code") == 1000, f"新建日程接口失败: {saved}"
            _log(f"已保存日程 {name} resp={saved}")

        with allure.step("查询并断言新建结果"):
            visit.search_schedules(name=name)
            text = visit.assert_row_contains(name, customer)
            assert any(s in text for s in ("今日拜访", "待拜访")), (
                f"新建后状态应是今日拜访/待拜访: {text!r}"
            )
            _save_ctx({"name": name, "customer": customer, "remark": remark})
            api_rows = crm_visit_schedule_service.find_by_name(crm_auth, name)
            assert api_rows, f"接口未找到新建日程: {name}"
        expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=8000)
        crm.assert_not_kicked_to_login()
    except Exception:
        _screenshot_on_fail(page, "visit_create_failed")
        raise


@allure.feature("CRM UI 改版回归")
@allure.story("拜访日程编辑")
@allure.title("拜访日程：编辑备注后回显")
def test_crm_visit_schedule_edit_smoke(
    authenticated_page, crm_visit_schedule_service, crm_auth
):
    customer = _customer()
    stamp = datetime.now().strftime("%m%d%H%M%S")
    ctx = _load_ctx()
    name = ctx.get("name") or ""
    page = authenticated_page
    try:
        page, crm, visit = _open_visit_via_menu(page)
        if not name:
            name = f"自动化拜访{stamp}"
            visit.open_create_form()
            visit.fill_create_form(
                name=name, customer_keyword=customer, remark="待编辑"
            )
            visit.save_form()
            _save_ctx({"name": name, "customer": customer})
        remark = f"自动化编辑{stamp}"
        with allure.step(f"编辑日程 {name}"):
            visit.search_schedules(name=name, customer_keyword=customer)
            visit.open_edit_form(name)
            visit.fill_remark(remark)
            saved = visit.save_form()
            if saved:
                assert saved.get("code") == 1000, f"编辑日程接口失败: {saved}"

        with allure.step("断言备注已更新"):
            visit.search_schedules(name=name, customer_keyword=customer)
            visit.assert_row_contains(name, remark)
            ctx["remark"] = remark
            _save_ctx(ctx)
        expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=8000)
        crm.assert_not_kicked_to_login()
    except Exception:
        _screenshot_on_fail(page, "visit_edit_failed")
        raise


@allure.feature("CRM UI 改版回归")
@allure.story("拜访日程关联活动")
@allure.title("拜访日程：关联活动记录后状态已完成")
def test_crm_visit_schedule_bind_activity_smoke(authenticated_page):
    customer = _customer()
    page = authenticated_page
    try:
        page, crm, visit = _open_visit_via_menu(page)
        with allure.step(f"筛选 {customer} 中可关联的日程"):
            visit.click_reset()
            visit.search_schedules(customer_keyword=customer)
            name = visit.first_row_name_with_action("关联活动记录", customer=customer)
            _log(f"将关联活动: {name}")

        with allure.step(f"关联活动记录: {name}"):
            visit.bind_activity(name)

        with allure.step("断言状态变为已完成"):
            visit.search_schedules(name=name, customer_keyword=customer)
            text = visit.assert_row_contains(name, "已完成")
            assert "解绑" in text or "查看活动记录" in text, (
                f"关联后应出现查看/解绑: {text!r}"
            )
        expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=8000)
        crm.assert_not_kicked_to_login()
    except Exception:
        _screenshot_on_fail(page, "visit_bind_failed")
        raise


@allure.feature("CRM UI 改版回归")
@allure.story("拜访日程解绑活动")
@allure.title("拜访日程：解绑活动记录")
def test_crm_visit_schedule_unbind_activity_smoke(authenticated_page):
    customer = _customer()
    page = authenticated_page
    try:
        page, crm, visit = _open_visit_via_menu(page)
        with allure.step(f"筛选 {customer} 中可解绑的日程"):
            visit.click_reset()
            visit.search_schedules(customer_keyword=customer)
            name = visit.first_row_name_with_action("解绑", customer=customer)
            _log(f"将解绑: {name}")

        with allure.step(f"解绑活动记录: {name}"):
            visit.unbind_activity(name)

        with allure.step("断言可再次关联或不再是已完成"):
            visit.search_schedules(name=name, customer_keyword=customer)
            text = visit.row_text(name)
            assert "关联活动记录" in text or "已完成" not in text, (
                f"解绑后仍像已绑定: {text!r}"
            )
            _log(f"解绑后行: {text[:160]!r}")
        expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=8000)
        crm.assert_not_kicked_to_login()
    except Exception:
        _screenshot_on_fail(page, "visit_unbind_failed")
        raise


@allure.feature("CRM UI 改版回归")
@allure.story("拜访日程删除")
@allure.title("拜访日程：删除后列表不再出现")
def test_crm_visit_schedule_delete_smoke(
    authenticated_page, crm_visit_schedule_service, crm_auth
):
    customer = _customer()
    ctx = _load_ctx()
    name = ctx.get("name") or ""
    page = authenticated_page
    try:
        page, crm, visit = _open_visit_via_menu(page)
        if not name:
            stamp = datetime.now().strftime("%m%d%H%M%S")
            name = f"自动化拜访{stamp}"
            visit.open_create_form()
            visit.fill_create_form(
                name=name, customer_keyword=customer, remark="待删除"
            )
            visit.save_form()
        with allure.step(f"删除日程 {name}"):
            visit.search_schedules(name=name, customer_keyword=customer)
            visit.delete_row(name)

        with allure.step("再次查询断言已删除"):
            visit.search_schedules(name=name, customer_keyword=customer)
            visit.assert_row_absent(name)
            left = crm_visit_schedule_service.find_by_name(crm_auth, name)
            assert not left, f"接口仍能查到已删日程: {left}"
            if _CTX_FILE.is_file():
                _CTX_FILE.unlink()
        expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=8000)
        crm.assert_not_kicked_to_login()
    except Exception:
        _screenshot_on_fail(page, "visit_delete_failed")
        raise
