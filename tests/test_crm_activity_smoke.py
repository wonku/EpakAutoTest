"""CRM 活动记录主路径 UI 冒烟（对齐 recordings/20260810-135954）。

覆盖：每个筛选条件设置后立即查询；全部条件齐后最终查询并断言结果符合条件。
创建日期默认 2026-05-27；活动类型默认「线下拜访」。

运行:
  $env:HEADLESS="false"
  pytest tests/test_crm_activity_smoke.py -m crm_ui -v -s
"""
from __future__ import annotations

import json
import re

import allure
import pytest
from playwright.sync_api import expect

from config.settings import (
    APP_HOME_URL,
    CRM_UI_ACTIVITY_CONTENT_KEYWORD,
    CRM_UI_ACTIVITY_CREATE_TIME_END,
    CRM_UI_ACTIVITY_CREATE_TIME_START,
    CRM_UI_ACTIVITY_FOLLOW_KEYWORD,
    CRM_UI_ACTIVITY_TYPE_TEXT,
    CRM_UI_PAUSE_ON_FAILURE,
    PLATFORM_BASE_URL,
)
from pages.crm_activity_page import CrmActivityPage
from pages.crm_page import CrmPage
from pages.home_page import HomePage

pytestmark = pytest.mark.crm_ui

ACTIVITY_URL = f"{PLATFORM_BASE_URL}/memberCenter/crm2Ability/activityLog"


@allure.feature("CRM UI 改版回归")
@allure.story("活动记录主路径")
@allure.title("活动记录：逐条件查询 → 最终断言结果 → 重置翻页")
def test_crm_activity_list_filter_smoke(authenticated_page):
    page = authenticated_page
    create_start = CRM_UI_ACTIVITY_CREATE_TIME_START or "2026-05-27"
    create_end = CRM_UI_ACTIVITY_CREATE_TIME_END or create_start
    content_kw = CRM_UI_ACTIVITY_CONTENT_KEYWORD or "添加线下摆放"
    follow_kw = CRM_UI_ACTIVITY_FOLLOW_KEYWORD or "甜"
    activity_type = CRM_UI_ACTIVITY_TYPE_TEXT or "线下拜访"

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
    act = CrmActivityPage(page)
    page.set_default_timeout(25000)
    try:
        with allure.step("打开活动记录列表"):
            try:
                with page.expect_response(
                    lambda r: "activity/page" in (r.url or ""),
                    timeout=20000,
                ):
                    page.goto(ACTIVITY_URL, wait_until="domcontentloaded")
            except Exception:
                page.goto(ACTIVITY_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            if "activitylog" not in page.url.lower():
                crm.open_menu_path("活动记录")
                page.wait_for_timeout(1500)
            crm.assert_menu_reachable("活动记录")
            act.assert_list_ready()

        with allure.step("条件1：活动记录类型 → 查询"):
            act.pick_record_type_first()
            act.click_query()
            expect(page.locator(".ant-table")).to_be_visible(timeout=10000)

        with allure.step(f"条件2：记录人={follow_kw} → 查询"):
            act.set_follow_user(follow_kw)
            act.click_query()
            expect(page.locator(".ant-table")).to_be_visible(timeout=10000)

        with allure.step(f"条件3：创建日期={create_start}~{create_end} → 查询"):
            act.set_create_time_range(start=create_start, end=create_end)
            act.click_query()
            expect(page.locator(".ant-table")).to_be_visible(timeout=10000)

        with allure.step(f"条件4：活动类型={activity_type} → 查询"):
            act.pick_activity_type(activity_type)
            act.click_query()
            expect(page.locator(".ant-table")).to_be_visible(timeout=10000)

        with allure.step(f"条件5：活动内容={content_kw} → 最终查询并断言结果"):
            act.set_activity_content(content_kw)
            api_body = act.click_query()
            expect(page.locator(".ant-table")).to_be_visible(timeout=10000)
            if api_body is not None:
                allure.attach(
                    json.dumps(api_body, ensure_ascii=False, indent=2)[:8000],
                    name="final_activity_page_response",
                    attachment_type=allure.attachment_type.JSON,
                )
            act.assert_rows_match_filters(
                content_keyword=content_kw,
                follow_keyword=follow_kw,
                create_date=create_start,
                activity_type=activity_type,
                api_body=api_body,
            )
            allure.attach(
                str(act.table_row_count()),
                name="matched_row_count",
                attachment_type=allure.attachment_type.TEXT,
            )

        with allure.step("重置后再按活动内容查询"):
            act.click_reset()
            act.set_activity_content(content_kw)
            act.click_query()
            expect(page.locator(".ant-table")).to_be_visible(timeout=10000)

        with allure.step("翻页（若有第 2 页）"):
            act.goto_page(2)
            act.goto_page(1)
            expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=5000)
    except Exception:
        if CRM_UI_PAUSE_ON_FAILURE:
            page.pause()
        raise
