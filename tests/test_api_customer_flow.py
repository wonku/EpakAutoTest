"""CRM 客户主路径接口回归。

来源录制：
  - recordings/20260803-142110（列表/详情/查重/活动）
  - recordings/20260807-143309（save/update 海外客户主路径再次验证）

覆盖：列表分页、详情、查重、客户活动分页。
创建/更新接口已在录制中验证，日回归默认不做写操作以免污染数据。
"""
from __future__ import annotations

import json

import allure
import pytest

from config.settings import CRM_CUSTOMER_ACTIVITY_RECORD_TYPE_CODE

pytestmark = pytest.mark.api


@allure.feature("CRM 客户")
@allure.story("客户列表")
@allure.title("客户分页列表查询成功")
def test_customer_page_list(crm_auth, crm_customer_service):
    payload = crm_customer_service.build_page_payload(page_size=10)
    body = crm_customer_service.query_customers(crm_auth, payload)
    allure.attach(
        json.dumps({"request": payload, "response": body}, ensure_ascii=False, indent=2),
        name="customer_page",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"客户列表失败: {body}"
    assert crm_customer_service.extract_total(body) >= 0
    rows = crm_customer_service.extract_rows(body)
    assert isinstance(rows, list)


@allure.feature("CRM 客户")
@allure.story("客户详情")
@allure.title("按列表首条客户查询详情成功")
def test_customer_find_by_id(crm_auth, crm_customer_service):
    page_body = crm_customer_service.query_customers(
        crm_auth,
        crm_customer_service.build_page_payload(page_size=5),
    )
    assert page_body.get("code") == 1000, f"客户列表失败: {page_body}"
    rows = crm_customer_service.extract_rows(page_body)
    assert rows, "客户列表为空，无法验证详情（请确认账号数据权限/viewType）"
    customer_id = int(rows[0]["id"])
    company_name = rows[0].get("companyName")

    body = crm_customer_service.find_by_id(crm_auth, customer_id)
    allure.attach(
        json.dumps(
            {"customer_id": customer_id, "company_name": company_name, "response": body},
            ensure_ascii=False,
            indent=2,
        ),
        name="customer_find_by_id",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"客户详情失败: {body}"
    data = body.get("data")
    assert isinstance(data, dict), f"详情 data 非对象: {body}"
    assert int(data.get("id") or 0) == customer_id or data.get("companyName")


@allure.feature("CRM 客户")
@allure.story("客户查重")
@allure.title("按企业名称查重成功")
def test_customer_check_repeat(crm_auth, crm_customer_service):
    page_body = crm_customer_service.query_customers(
        crm_auth,
        crm_customer_service.build_page_payload(page_size=5),
    )
    assert page_body.get("code") == 1000, f"客户列表失败: {page_body}"
    rows = crm_customer_service.extract_rows(page_body)
    assert rows, "客户列表为空，无法验证查重"
    company_name = str(rows[0].get("companyName") or "").strip()
    assert company_name, f"列表首条无企业名称: {rows[0]}"

    body = crm_customer_service.check_repeat(crm_auth, company_name=company_name)
    allure.attach(
        json.dumps(
            {"company_name": company_name, "response": body},
            ensure_ascii=False,
            indent=2,
        ),
        name="customer_check_repeat",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"客户查重失败: {body}"


@allure.feature("CRM 客户")
@allure.story("客户活动")
@allure.title("客户关联活动分页查询成功")
def test_customer_activity_page(crm_auth, crm_customer_service):
    page_body = crm_customer_service.query_customers(
        crm_auth,
        crm_customer_service.build_page_payload(page_size=5),
    )
    assert page_body.get("code") == 1000, f"客户列表失败: {page_body}"
    rows = crm_customer_service.extract_rows(page_body)
    assert rows, "客户列表为空，无法验证活动分页"
    relation_id = int(rows[0]["id"])

    body = crm_customer_service.query_activity_page(
        crm_auth,
        relation_id=relation_id,
        activity_record_type_code=CRM_CUSTOMER_ACTIVITY_RECORD_TYPE_CODE,
    )
    allure.attach(
        json.dumps(
            {
                "relation_id": relation_id,
                "activity_record_type_code": CRM_CUSTOMER_ACTIVITY_RECORD_TYPE_CODE,
                "response": body,
            },
            ensure_ascii=False,
            indent=2,
        ),
        name="customer_activity_page",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"客户活动分页失败: {body}"
