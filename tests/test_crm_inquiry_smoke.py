"""CRM 询价单主路径 UI 冒烟（严格对齐 recordings/20260804-105954）。

录制步骤映射:
  1. 打开客户 → 按企业名称查询 → 进入客户详情
  2. 发起内部询价单
  3. 填写地址与物料信息 → 保存草稿
  4. 查看详情 → 编辑 → 保存并提交

运行:
  $env:HEADLESS="false"
  pytest tests/test_crm_inquiry_smoke.py -m crm_ui -v -s
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import allure
import pytest
from playwright.sync_api import expect

from config.settings import (
    APP_HOME_URL,
    CRM_UI_INQUIRY_CUSTOMER_KEYWORD,
    CRM_UI_PAUSE_ON_FAILURE,
    PLATFORM_BASE_URL,
)
from pages.crm_inquiry_page import CrmInquiryPage
from pages.crm_page import CrmPage
from pages.home_page import HomePage

pytestmark = pytest.mark.crm_ui

CUSTOMER_URL = f"{PLATFORM_BASE_URL}/memberCenter/crm2Ability/customer"


@allure.feature("CRM UI 改版回归")
@allure.story("询价单主路径")
@allure.title("客户详情：发起内部询价 → 草稿 → 提交（对齐录制）")
def test_crm_inquiry_main_path_smoke(authenticated_page):
    page = authenticated_page
    customer_kw = CRM_UI_INQUIRY_CUSTOMER_KEYWORD
    assert customer_kw, "请配置 CRM_UI_INQUIRY_CUSTOMER_KEYWORD"

    stamp = datetime.now().strftime("%m%d%H%M%S")
    material_name = f"自动化物料_{stamp}"
    address = f"自动化详细地址_{stamp}"

    # 可选附件：复用仓库内任意图片；没有则跳过上传
    sample_image = None
    for candidate in (
        Path("testdata/order/contract_sample.jpg"),
        Path("testdata/order/payment_voucher_sample.jpg"),
    ):
        if candidate.exists():
            sample_image = candidate
            break

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
    inquiry = CrmInquiryPage(page)
    page.set_default_timeout(20000)

    try:
        with allure.step("1. 打开客户并按企业名称查询"):
            page.goto(CUSTOMER_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            if "customer" not in page.url.lower():
                crm.open_menu_path("客户")
            crm.assert_menu_reachable("客户")
            inquiry.filter_customer_by_company(customer_kw)

        with allure.step(f"2. 打开客户详情: {customer_kw}"):
            inquiry.open_customer_row(customer_kw)

        with allure.step("3. 发起内部询价单并填写表单"):
            inquiry.open_create_internal_inquiry()
            inquiry.fill_inquiry_form(
                address=address,
                material_name=material_name,
                year_purchase_qty=1000,
                qty=10,
                specification=f"规格_{stamp}",
                remark=f"自动化备注_{stamp}",
            )
            inquiry.upload_attachment_if_present(sample_image)

        with allure.step("4. 保存草稿"):
            inquiry.save_draft()

        with allure.step("5. 查看详情 → 编辑 → 保存并提交"):
            inquiry.open_view_detail()
            inquiry.click_edit()
            # 编辑态再点一次提交；若已在表单页则直接提交
            inquiry.save_and_submit()

        with allure.step("校验未掉回登录页"):
            expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=10000)
            crm.assert_not_kicked_to_login()
    except Exception:
        png = page.screenshot(full_page=True)
        allure.attach(
            png,
            name="inquiry_main_failed",
            attachment_type=allure.attachment_type.PNG,
        )
        if CRM_UI_PAUSE_ON_FAILURE:
            page.pause()
        raise
