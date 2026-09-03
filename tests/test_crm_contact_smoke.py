"""CRM 联系人主路径 UI 冒烟（严格对齐 recordings/20260803-164057 录制步骤）。

录制步骤映射:
  1. 打开联系人
  2. 姓名 + 所属客户 + 来源 + 创建时间 + 注册状态 → 查询
  3. 打开详情 → 关闭
  4. 新建联系人（姓名/客户/性别/手机/邮箱/微信/WhatsApp）→ 确认
  5. 重置 → 按新建姓名查询 → 打开详情
  6. 编辑姓名+备注 → 保存 → 关闭
  7. 按编辑后姓名查询 → 打开详情 → 关闭
  8. 删除 → 确认 → 查询 → 重置

运行:
  $env:HEADLESS="false"
  pytest tests/test_crm_contact_smoke.py -m crm_ui -v -s
"""
from __future__ import annotations

import re
from datetime import datetime

import allure
import pytest
from playwright.sync_api import expect

from config.settings import (
    APP_HOME_URL,
    CRM_UI_CONTACT_CREATE_TIME_END,
    CRM_UI_CONTACT_CREATE_TIME_START,
    CRM_UI_CONTACT_CUSTOMER_KEYWORD,
    CRM_UI_CONTACT_REGISTER_STATUS_TEXT,
    CRM_UI_CONTACT_SOURCE_TEXT,
    CRM_UI_PAUSE_ON_FAILURE,
    PLATFORM_BASE_URL,
)
from pages.crm_contact_page import CrmContactPage
from pages.crm_page import CrmPage
from pages.home_page import HomePage

pytestmark = pytest.mark.crm_ui

CONTACT_URL = f"{PLATFORM_BASE_URL}/memberCenter/crm2Ability/contactPerson"


@allure.feature("CRM UI 改版回归")
@allure.story("联系人主路径")
@allure.title("联系人：筛选 → 详情 → 新建 → 编辑 → 删除（对齐录制）")
def test_crm_contact_main_path_smoke(authenticated_page):
    page = authenticated_page
    customer_kw = CRM_UI_CONTACT_CUSTOMER_KEYWORD
    assert customer_kw, "请配置 CRM_UI_CONTACT_CUSTOMER_KEYWORD"

    stamp = datetime.now().strftime("%m%d%H%M%S")
    contact_name = f"自动化联系人_{stamp}"
    contact_name_edited = f"{contact_name}_编辑"
    phone = f"187{stamp[-8:]}"
    email = f"{phone}@qq.com"
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
    contact = CrmContactPage(page)
    page.set_default_timeout(20000)

    try:
        with allure.step("1. 打开联系人列表"):
            page.goto(CONTACT_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            if "contact" not in page.url.lower() and "Contact" not in page.url:
                crm.open_menu_path("联系人")
            crm.assert_menu_reachable("联系人")

        with allure.step(
            "2. 筛选：姓名 + 所属客户 + 来源 + 创建时间 + 注册状态 → 查询"
        ):
            # 对齐录制首次查询：sourceTypeCode=[1]、createTime=2026-07-03、registerStatus=1
            contact.filter_contacts(
                name=customer_kw,
                company_keyword=customer_kw,
                source_text=CRM_UI_CONTACT_SOURCE_TEXT,
                register_status_text=CRM_UI_CONTACT_REGISTER_STATUS_TEXT,
                create_time_start=CRM_UI_CONTACT_CREATE_TIME_START,
                create_time_end=CRM_UI_CONTACT_CREATE_TIME_END,
            )

        with allure.step("3. 打开详情并关闭（若有结果）"):
            row_link = page.locator(".ant-table-tbody a").first
            if row_link.count() > 0 and row_link.is_visible():
                row_link.click()
                page.wait_for_timeout(1200)
                contact.close_drawer()

        with allure.step(f"4. 新建联系人: {contact_name}"):
            contact.open_create_form()
            contact.fill_create_basic(
                name=contact_name,
                customer_keyword=customer_kw,
                phone=phone,
                email=email,
                wx_code=phone,
                whatsapp=f"{phone}wa",
            )
            contact.confirm_save()

        with allure.step("5. 重置后按新建姓名查询并打开详情"):
            contact.click_reset()
            contact.filter_contacts(name=contact_name)
            contact.assert_row_exists(contact_name)
            contact.open_row_by_name(contact_name)

        with allure.step("6. 编辑姓名与备注并保存"):
            contact.click_edit()
            contact.fill_edit(name=contact_name_edited, remark=remark_text)
            contact.confirm_save()
            contact.close_drawer()

        with allure.step("7. 按编辑后姓名查询并打开详情"):
            contact.filter_contacts(name=contact_name_edited)
            contact.assert_row_exists(contact_name_edited)
            contact.open_row_by_name(contact_name_edited)
            contact.close_drawer()

        with allure.step("8. 删除刚建联系人 → 查询 → 重置"):
            contact.delete_row_by_name(contact_name_edited)
            contact.filter_contacts(name=contact_name_edited)
            contact.assert_row_absent(contact_name_edited)
            contact.click_reset()

        with allure.step("校验未掉回登录页"):
            expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=10000)
            crm.assert_not_kicked_to_login()
    except Exception:
        png = page.screenshot(full_page=True)
        allure.attach(
            png,
            name="contact_main_failed",
            attachment_type=allure.attachment_type.PNG,
        )
        if CRM_UI_PAUSE_ON_FAILURE:
            page.pause()
        raise
