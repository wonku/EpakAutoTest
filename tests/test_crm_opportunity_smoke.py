"""CRM 销售机会主路径 UI 冒烟（对齐 recordings/20260803-155343）。

覆盖：筛选查询 → 查看详情 → 新建 → 编辑 → 删除。

运行:
  $env:HEADLESS="false"
  pytest tests/test_crm_opportunity_smoke.py -m crm_ui -v -s

可选环境变量:
  CRM_UI_OPPORTUNITY_CUSTOMER_KEYWORD  关联客户关键字（默认录制同款客户）
"""
from __future__ import annotations

import re
from datetime import datetime

import allure
import pytest
from playwright.sync_api import expect

from config.settings import (
    APP_HOME_URL,
    CRM_UI_OPPORTUNITY_AMOUNT,
    CRM_UI_OPPORTUNITY_CUSTOMER_KEYWORD,
    CRM_UI_OPPORTUNITY_PRODUCT_COUNT,
    CRM_UI_OPPORTUNITY_PRODUCT_PRICE,
    CRM_UI_PAUSE_ON_FAILURE,
    PLATFORM_BASE_URL,
)
from pages.crm_opportunity_page import CrmOpportunityPage
from pages.crm_page import CrmPage
from pages.home_page import HomePage

pytestmark = pytest.mark.crm_ui

OPPORTUNITY_URL = f"{PLATFORM_BASE_URL}/memberCenter/crm2Ability/salesOpportunity"


@allure.feature("CRM UI 改版回归")
@allure.story("销售机会主路径")
@allure.title("销售机会：筛选 → 详情 → 新建 → 编辑 → 删除")
def test_crm_opportunity_main_path_smoke(authenticated_page):
    page = authenticated_page
    customer_kw = CRM_UI_OPPORTUNITY_CUSTOMER_KEYWORD
    assert customer_kw, "请配置 CRM_UI_OPPORTUNITY_CUSTOMER_KEYWORD"
    stamp = datetime.now().strftime("%m%d%H%M%S")
    opportunity_name = f"自动化机会_{stamp}"
    remark_text = f"自动化编辑_{stamp}"

    with allure.step("进入平台并打开 CRM"):
        page.goto(APP_HOME_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        assert "login" not in page.url.lower(), f"登录态注入失败: {page.url}"
        home = HomePage(page)
        crm_tab = home.open_crm_2()
        crm_tab.wait_for_timeout(2000)
        home.assert_crm_page_loaded(crm_tab)
        page = crm_tab

    crm = CrmPage(page)
    opp = CrmOpportunityPage(page)
    page.set_default_timeout(20000)
    try:
        with allure.step("打开销售机会列表"):
            page.goto(OPPORTUNITY_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            if "opportunity" not in page.url.lower() and "Opportunity" not in page.url:
                crm.open_menu_path("销售机会")
            crm.assert_menu_reachable("销售机会")

        with allure.step("筛选条件查询（机会名称 + 客户下拉搜索选中）"):
            page.locator("#opportunity_form_name").fill(customer_kw)
            assert page.locator("#opportunity_form_customerIdList").count() > 0, (
                "列表缺少客户筛选 #opportunity_form_customerIdList"
            )
            # 列表客户筛选为多选可搜索 Select（页面上已能选中）
            opp.select_searchable(
                "#opportunity_form_customerIdList", customer_kw, multi=True
            )
            opp.click_search()
            page.wait_for_timeout(1500)

        with allure.step("打开筛选结果中的详情（若有）"):
            row_link = page.locator(".ant-table-tbody a").first
            if row_link.count() > 0 and row_link.is_visible():
                row_link.click()
                page.wait_for_timeout(1200)
                opp.close_drawer()

        with allure.step(f"新建销售机会: {opportunity_name}"):
            opp.open_create_form()
            opp.fill_create_basic(
                name=opportunity_name,
                customer_keyword=customer_kw,
                amount=CRM_UI_OPPORTUNITY_AMOUNT,
            )
            opp.add_generic_product(
                price=CRM_UI_OPPORTUNITY_PRODUCT_PRICE,
                count=CRM_UI_OPPORTUNITY_PRODUCT_COUNT,
            )
            opp.confirm_save()

        with allure.step("按新建名称查询并打开详情"):
            opp.filter_by_name(opportunity_name)
            opp.assert_row_exists(opportunity_name)
            opp.open_row_by_name(opportunity_name)

        with allure.step("编辑备注并保存"):
            opp.click_edit()
            opp.fill_remark(remark_text)
            opp.confirm_save()
            opp.close_drawer()

        with allure.step("删除刚新建的机会"):
            opp.filter_by_name(opportunity_name)
            opp.delete_row_by_name(opportunity_name)
            opp.filter_by_name(opportunity_name)
            opp.assert_row_absent(opportunity_name)

        with allure.step("校验未掉回登录页"):
            expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=10000)
            crm.assert_not_kicked_to_login()
    except Exception:
        png = page.screenshot(full_page=True)
        allure.attach(
            png,
            name="opportunity_main_failed",
            attachment_type=allure.attachment_type.PNG,
        )
        if CRM_UI_PAUSE_ON_FAILURE:
            page.pause()
        raise
