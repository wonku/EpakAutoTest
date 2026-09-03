"""CRM 活动记录接口回归（来源录制：recordings/20260810-135954）。

覆盖：活动分页列表（按记录类型 / 内容关键字）。
"""
from __future__ import annotations

import json

import allure
import pytest

from config.settings import (
    ACTIVITY_RECORD_TYPE_CODE,
    CRM_UI_ACTIVITY_CONTENT_KEYWORD,
)

pytestmark = pytest.mark.api


@allure.feature("CRM 活动记录")
@allure.story("活动列表")
@allure.title("活动记录分页列表查询成功")
def test_activity_page_list(crm_auth, crm_activity_service):
    payload = crm_activity_service.build_page_payload(
        page_size=20,
        activity_record_type_code=ACTIVITY_RECORD_TYPE_CODE,
    )
    body = crm_activity_service.query_activity_page(crm_auth, payload)
    allure.attach(
        json.dumps({"request": payload, "response": body}, ensure_ascii=False, indent=2),
        name="activity_page",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"活动列表失败: {body}"
    assert crm_activity_service.extract_total(body) >= 0
    assert isinstance(crm_activity_service.extract_rows(body), list)


@allure.feature("CRM 活动记录")
@allure.story("活动列表")
@allure.title("按活动内容关键字筛选活动记录")
def test_activity_page_filter_by_content(crm_auth, crm_activity_service):
    keyword = CRM_UI_ACTIVITY_CONTENT_KEYWORD or "添加线下摆放"
    payload = crm_activity_service.build_page_payload(
        page_size=20,
        activity_content=keyword,
        activity_record_type_code=ACTIVITY_RECORD_TYPE_CODE,
    )
    body = crm_activity_service.query_activity_page(crm_auth, payload)
    allure.attach(
        json.dumps({"request": payload, "response": body}, ensure_ascii=False, indent=2),
        name="activity_page_by_content",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"活动内容筛选失败: {body}"
    rows = crm_activity_service.extract_rows(body)
    assert isinstance(rows, list)
