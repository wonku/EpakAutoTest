"""CRM 销售线索主路径接口回归（来源录制：recordings/20260807-160515）。

覆盖：列表分页、详情、线索活动分页。
saveOrUpdate 已在录制中验证，日回归默认不做写操作以免污染数据。
"""
from __future__ import annotations

import json

import allure
import pytest

pytestmark = pytest.mark.api


@allure.feature("CRM 销售线索")
@allure.story("线索列表")
@allure.title("销售线索分页列表查询成功")
def test_lead_page_list(crm_auth, crm_lead_service):
    payload = crm_lead_service.build_page_payload(page_size=10)
    body = crm_lead_service.query_lead_page(crm_auth, payload)
    allure.attach(
        json.dumps({"request": payload, "response": body}, ensure_ascii=False, indent=2),
        name="lead_page",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"线索列表失败: {body}"
    assert crm_lead_service.extract_total(body) >= 0
    assert isinstance(crm_lead_service.extract_rows(body), list)


@allure.feature("CRM 销售线索")
@allure.story("线索详情")
@allure.title("按列表首条线索查询详情成功")
def test_lead_detail(crm_auth, crm_lead_service):
    page_body = crm_lead_service.query_lead_page(
        crm_auth,
        crm_lead_service.build_page_payload(page_size=5),
    )
    assert page_body.get("code") == 1000, f"线索列表失败: {page_body}"
    rows = crm_lead_service.extract_rows(page_body)
    assert rows, "线索列表为空，无法验证详情（请确认账号数据权限）"
    lead_id = int(rows[0]["id"])
    lead_name = rows[0].get("name")

    body = crm_lead_service.get_lead_detail(crm_auth, lead_id)
    allure.attach(
        json.dumps(
            {"lead_id": lead_id, "lead_name": lead_name, "response": body},
            ensure_ascii=False,
            indent=2,
        ),
        name="lead_detail",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"线索详情失败: {body}"
    data = body.get("data")
    assert isinstance(data, dict), f"详情 data 非对象: {body}"
    assert int(data.get("id") or 0) == lead_id or data.get("name")


@allure.feature("CRM 销售线索")
@allure.story("线索活动")
@allure.title("线索关联活动分页查询成功")
def test_lead_activity_page(crm_auth, crm_lead_service):
    page_body = crm_lead_service.query_lead_page(
        crm_auth,
        crm_lead_service.build_page_payload(page_size=5),
    )
    assert page_body.get("code") == 1000, f"线索列表失败: {page_body}"
    rows = crm_lead_service.extract_rows(page_body)
    assert rows, "线索列表为空，无法验证活动分页"
    relation_id = int(rows[0]["id"])

    body = crm_lead_service.query_lead_activity_page(
        crm_auth,
        relation_id=relation_id,
        activity_record_type_code=1,
    )
    allure.attach(
        json.dumps(
            {"relation_id": relation_id, "response": body},
            ensure_ascii=False,
            indent=2,
        ),
        name="lead_activity_page",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"线索活动分页失败: {body}"
