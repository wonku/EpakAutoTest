"""CRM 客户查重 UI 冒烟（仅侧栏菜单进入，对齐重录路径）。

覆盖（拆两条）:
  1) 有重复数据：菜单 → 客户查重 → 查询 → 结果列表展示企业名 + 建议操作
  2) 无重复数据：空态 → 立即新建下拉 → 国内/国外弹窗仅断言 → 取消

运行:
  pytest tests/test_crm_customer_dup_check_smoke.py -m crm_ui -v -s
"""
from __future__ import annotations

import re

import allure
import pytest
from playwright.sync_api import expect

from config.settings import (
    APP_HOME_URL,
    CRM_UI_CUSTOMER_DUP_HIT_KEYWORD,
    CRM_UI_CUSTOMER_DUP_MISS_KEYWORD,
    CRM_UI_PAUSE_ON_FAILURE,
)
from pages.crm_customer_page import CrmCustomerPage
from pages.crm_page import CrmPage
from pages.home_page import HomePage

pytestmark = pytest.mark.crm_ui


def _open_crm_dup_check(authenticated_page):
    """登录态 → CRM 首页 → 仅菜单进入客户查重。"""
    page = authenticated_page
    page.goto(APP_HOME_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    assert "login" not in page.url.lower(), f"登录态注入失败: {page.url}"
    home = HomePage(page)
    crm_tab = home.open_crm_2()
    crm_tab.wait_for_timeout(2000)
    home.assert_crm_page_loaded(crm_tab)
    page = crm_tab
    crm = CrmPage(page)
    cust = CrmCustomerPage(page)
    page.set_default_timeout(25000)
    cust.open_duplicate_check_via_menu(crm)
    return page, crm, cust


def _resolve_hit_keyword(crm_auth, crm_customer_service) -> str:
    """解析必定能命中的查重关键字（先 API 验证，避免配置公司名已不存在）。"""
    candidates: list[str] = []
    if CRM_UI_CUSTOMER_DUP_HIT_KEYWORD:
        candidates.append(CRM_UI_CUSTOMER_DUP_HIT_KEYWORD)
    page_body = crm_customer_service.query_customers(
        crm_auth, crm_customer_service.build_page_payload(page_size=10)
    )
    for row in crm_customer_service.extract_rows(page_body):
        name = str(row.get("companyName") or "").strip()
        if name and name not in candidates:
            candidates.append(name)
    for name in candidates:
        body = crm_customer_service.check_repeat(crm_auth, company_name=name)
        if crm_customer_service.extract_total(body) > 0:
            return name
    raise AssertionError(
        "无法解析查重命中关键字：配置与列表首屏企业均未通过 checkRepeatPage"
    )


def _screenshot_on_fail(page, name: str) -> None:
    try:
        png = page.screenshot(full_page=True, timeout=10000)
        allure.attach(png, name=name, attachment_type=allure.attachment_type.PNG)
    except Exception:
        pass
    if CRM_UI_PAUSE_ON_FAILURE:
        page.pause()


@allure.feature("CRM UI 改版回归")
@allure.story("客户查重")
@allure.title("客户查重：菜单进入 → 有重复数据命中")
def test_crm_customer_dup_check_hit_smoke(
    authenticated_page, crm_auth, crm_customer_service
):
    keyword = _resolve_hit_keyword(crm_auth, crm_customer_service)
    page = authenticated_page
    try:
        with allure.step("侧栏菜单进入客户查重"):
            page, crm, cust = _open_crm_dup_check(page)

        with allure.step(f"查询已知企业（应命中）: {keyword}"):
            body = cust.search_duplicate_check(keyword)
            allure.attach(
                str(body),
                name="dup_check_hit_api",
                attachment_type=allure.attachment_type.TEXT,
            )
            cust.assert_duplicate_check_hit(keyword, api_body=body)

        with allure.step("校验未掉回登录页"):
            expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=10000)
            crm.assert_not_kicked_to_login()
    except Exception:
        _screenshot_on_fail(page, "customer_dup_hit_failed")
        raise


@allure.feature("CRM UI 改版回归")
@allure.story("客户查重")
@allure.title("客户查重：菜单进入 → 无重复 → 下拉新建国内/国外仅断言后取消")
def test_crm_customer_dup_check_miss_smoke(authenticated_page):
    keyword = CRM_UI_CUSTOMER_DUP_MISS_KEYWORD
    assert keyword, "请配置 CRM_UI_CUSTOMER_DUP_MISS_KEYWORD"
    page = authenticated_page
    try:
        with allure.step("侧栏菜单进入客户查重"):
            page, crm, cust = _open_crm_dup_check(page)

        with allure.step(f"查询不存在企业（应无命中）: {keyword}"):
            body = cust.search_duplicate_check(keyword)
            allure.attach(
                str(body),
                name="dup_check_miss_api",
                attachment_type=allure.attachment_type.TEXT,
            )
            cust.assert_duplicate_check_miss(keyword, api_body=body)

        with allure.step("立即新建 → 新建国内客户弹窗 → 取消（不保存）"):
            cust.open_create_from_dup_miss_dropdown("domestic")
            cust.assert_create_customer_modal("domestic")
            cust.cancel_create_customer_form()
            expect(
                page.get_by_text(re.compile(r"未发现重复客户")).first
            ).to_be_visible(timeout=10000)

        with allure.step("立即新建 → 新建国外客户弹窗 → 取消（不保存）"):
            cust.open_create_from_dup_miss_dropdown("overseas")
            cust.assert_create_customer_modal("overseas")
            cust.cancel_create_customer_form()
            expect(
                page.get_by_text(re.compile(r"未发现重复客户")).first
            ).to_be_visible(timeout=10000)

        with allure.step("校验未掉回登录页"):
            expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=10000)
            crm.assert_not_kicked_to_login()
    except Exception:
        _screenshot_on_fail(page, "customer_dup_miss_failed")
        raise
