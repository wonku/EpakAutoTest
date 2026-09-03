"""CRM 联系人主路径接口回归（来源录制：recordings/20260803-164057）。

覆盖：列表、详情、关联活动。新建/编辑/删除默认不进日回归。
"""
from __future__ import annotations

import json

import allure
import pytest

from config.settings import CRM_CONTACT_ACTIVITY_RECORD_TYPE_CODE

pytestmark = pytest.mark.api


@allure.feature("CRM 联系人")
@allure.story("联系人列表")
@allure.title("联系人分页列表查询成功")
def test_contact_page_list(crm_auth, crm_contact_service):
    payload = crm_contact_service.build_page_payload(page_size=10)
    body = crm_contact_service.query_contacts(crm_auth, payload)
    allure.attach(
        json.dumps({"request": payload, "response": body}, ensure_ascii=False, indent=2),
        name="contact_page",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"联系人列表失败: {body}"
    assert crm_contact_service.extract_total(body) >= 0


@allure.feature("CRM 联系人")
@allure.story("联系人详情")
@allure.title("按列表首条联系人查询详情成功")
def test_contact_find_by_id(crm_auth, crm_contact_service):
    page_body = crm_contact_service.query_contacts(
        crm_auth, crm_contact_service.build_page_payload(page_size=5)
    )
    assert page_body.get("code") == 1000, f"联系人列表失败: {page_body}"
    rows = crm_contact_service.extract_rows(page_body)
    assert rows, "联系人列表为空，无法验证详情"
    contact_id = int(rows[0]["id"])

    body = crm_contact_service.find_by_id(crm_auth, contact_id)
    allure.attach(
        json.dumps(
            {"contact_id": contact_id, "response": body},
            ensure_ascii=False,
            indent=2,
        ),
        name="contact_find_by_id",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"联系人详情失败: {body}"
    data = body.get("data")
    assert isinstance(data, dict), f"详情 data 非对象: {body}"


@allure.feature("CRM 联系人")
@allure.story("联系人活动")
@allure.title("联系人关联活动分页查询成功")
def test_contact_activity_page(crm_auth, crm_contact_service):
    page_body = crm_contact_service.query_contacts(
        crm_auth, crm_contact_service.build_page_payload(page_size=5)
    )
    assert page_body.get("code") == 1000, f"联系人列表失败: {page_body}"
    rows = crm_contact_service.extract_rows(page_body)
    assert rows, "联系人列表为空"
    relation_id = int(rows[0]["id"])

    body = crm_contact_service.query_activity_page(
        crm_auth,
        relation_id=relation_id,
        activity_record_type_code=CRM_CONTACT_ACTIVITY_RECORD_TYPE_CODE,
    )
    allure.attach(
        json.dumps(
            {
                "relation_id": relation_id,
                "activity_record_type_code": CRM_CONTACT_ACTIVITY_RECORD_TYPE_CODE,
                "response": body,
            },
            ensure_ascii=False,
            indent=2,
        ),
        name="contact_activity_page",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"联系人活动分页失败: {body}"
