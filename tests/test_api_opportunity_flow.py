"""CRM 销售机会主路径接口回归（来源录制：recordings/20260803-155343）。

覆盖：列表分页、详情、关联活动、客户联系人查询。
新建/编辑/删除在录制中已验证，日回归默认不做写/删以免污染数据。
"""
from __future__ import annotations

import json

import allure
import pytest

from config.settings import CRM_OPPORTUNITY_ACTIVITY_RECORD_TYPE_CODE

pytestmark = pytest.mark.api


@allure.feature("CRM 销售机会")
@allure.story("机会列表")
@allure.title("销售机会分页列表查询成功")
def test_opportunity_page_list(crm_auth, crm_opportunity_service):
    payload = crm_opportunity_service.build_page_payload(page_size=10)
    body = crm_opportunity_service.query_opportunities(crm_auth, payload)
    allure.attach(
        json.dumps({"request": payload, "response": body}, ensure_ascii=False, indent=2),
        name="opportunity_page",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"销售机会列表失败: {body}"
    assert crm_opportunity_service.extract_total(body) >= 0
    assert isinstance(crm_opportunity_service.extract_rows(body), list)


@allure.feature("CRM 销售机会")
@allure.story("机会详情")
@allure.title("按列表首条机会查询详情成功")
def test_opportunity_find_by_id(crm_auth, crm_opportunity_service):
    page_body = crm_opportunity_service.query_opportunities(
        crm_auth,
        crm_opportunity_service.build_page_payload(page_size=5),
    )
    assert page_body.get("code") == 1000, f"销售机会列表失败: {page_body}"
    rows = crm_opportunity_service.extract_rows(page_body)
    assert rows, "销售机会列表为空，无法验证详情"
    opportunity_id = int(rows[0]["id"])
    name = rows[0].get("name")

    body = crm_opportunity_service.find_by_id(crm_auth, opportunity_id)
    allure.attach(
        json.dumps(
            {"opportunity_id": opportunity_id, "name": name, "response": body},
            ensure_ascii=False,
            indent=2,
        ),
        name="opportunity_find_by_id",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"销售机会详情失败: {body}"
    data = body.get("data")
    assert isinstance(data, dict), f"详情 data 非对象: {body}"
    assert int(data.get("id") or 0) == opportunity_id or data.get("name")


@allure.feature("CRM 销售机会")
@allure.story("机会活动")
@allure.title("销售机会关联活动分页查询成功")
def test_opportunity_activity_page(crm_auth, crm_opportunity_service):
    page_body = crm_opportunity_service.query_opportunities(
        crm_auth,
        crm_opportunity_service.build_page_payload(page_size=5),
    )
    assert page_body.get("code") == 1000, f"销售机会列表失败: {page_body}"
    rows = crm_opportunity_service.extract_rows(page_body)
    assert rows, "销售机会列表为空，无法验证活动分页"
    relation_id = int(rows[0]["id"])

    body = crm_opportunity_service.query_activity_page(
        crm_auth,
        relation_id=relation_id,
        activity_record_type_code=CRM_OPPORTUNITY_ACTIVITY_RECORD_TYPE_CODE,
    )
    allure.attach(
        json.dumps(
            {
                "relation_id": relation_id,
                "activity_record_type_code": CRM_OPPORTUNITY_ACTIVITY_RECORD_TYPE_CODE,
                "response": body,
            },
            ensure_ascii=False,
            indent=2,
        ),
        name="opportunity_activity_page",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"销售机会活动分页失败: {body}"


@allure.feature("CRM 销售机会")
@allure.story("关联联系人")
@allure.title("按机会关联客户查询联系人列表成功")
def test_opportunity_contact_person_page(crm_auth, crm_opportunity_service):
    page_body = crm_opportunity_service.query_opportunities(
        crm_auth,
        crm_opportunity_service.build_page_payload(page_size=10),
    )
    assert page_body.get("code") == 1000, f"销售机会列表失败: {page_body}"
    rows = crm_opportunity_service.extract_rows(page_body)
    assert rows, "销售机会列表为空"

    customer_id = None
    detail = None
    for row in rows:
        oid = int(row["id"])
        detail = crm_opportunity_service.find_by_id(crm_auth, oid)
        assert detail.get("code") == 1000, f"详情失败: {detail}"
        data = detail.get("data") or {}
        if data.get("customerId"):
            customer_id = int(data["customerId"])
            break

    if customer_id is None:
        pytest.skip("当前列表机会均未关联客户，跳过联系人查询")

    body = crm_opportunity_service.query_contact_persons(crm_auth, customer_id=customer_id)
    allure.attach(
        json.dumps(
            {"customer_id": customer_id, "detail": detail, "response": body},
            ensure_ascii=False,
            indent=2,
        ),
        name="opportunity_contact_person_page",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"联系人列表失败: {body}"
