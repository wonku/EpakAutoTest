"""CRM 询价单主路径接口回归（来源录制：recordings/20260804-105954）。

覆盖：客户询价列表、子单详情、客户简要信息。
新建草稿/提交接口已封装，造数用例单独提供，日回归默认不写数据。
"""
from __future__ import annotations

import json

import allure
import pytest

from config.settings import (
    CRM_INQUIRY_BUYER_MEMBER_ID,
    CRM_INQUIRY_CUSTOMER_ID,
)

pytestmark = pytest.mark.api


@allure.feature("CRM 询价单")
@allure.story("询价列表")
@allure.title("客户询价单分页列表查询成功")
def test_inquiry_page_list(crm_auth, crm_inquiry_service):
    payload = crm_inquiry_service.build_query_payload(
        page_size=10,
        customer_id=CRM_INQUIRY_CUSTOMER_ID,
        buyer_member_id=CRM_INQUIRY_BUYER_MEMBER_ID,
    )
    body = crm_inquiry_service.query_inquiries(crm_auth, payload)
    allure.attach(
        json.dumps({"request": payload, "response": body}, ensure_ascii=False, indent=2),
        name="inquiry_page",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"询价列表失败: {body}"
    assert crm_inquiry_service.extract_total(body) >= 0
    assert isinstance(crm_inquiry_service.extract_rows(body), list)


@allure.feature("CRM 询价单")
@allure.story("询价详情")
@allure.title("按列表首条子单查询询价详情成功")
def test_inquiry_detail_by_sub(crm_auth, crm_inquiry_service):
    page_body = crm_inquiry_service.query_inquiries(
        crm_auth,
        crm_inquiry_service.build_query_payload(page_size=5),
    )
    assert page_body.get("code") == 1000, f"询价列表失败: {page_body}"
    sub_id = crm_inquiry_service.extract_first_sub_id(page_body)
    assert sub_id is not None, "询价列表无子单，无法验证详情"

    body = crm_inquiry_service.detail_by_sub(crm_auth, sub_id=sub_id)
    allure.attach(
        json.dumps(
            {"sub_id": sub_id, "response": body},
            ensure_ascii=False,
            indent=2,
        ),
        name="inquiry_detail_by_sub",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"询价详情失败: {body}"
    data = body.get("data")
    assert isinstance(data, dict), f"详情 data 非对象: {body}"
    cn = data.get("cnDetail")
    assert isinstance(cn, dict), f"缺少 cnDetail: {body}"


@allure.feature("CRM 询价单")
@allure.story("客户简要")
@allure.title("询价场景客户简要信息查询成功")
def test_inquiry_customer_brief(crm_auth, crm_inquiry_service):
    body = crm_inquiry_service.get_customer_brief(
        crm_auth,
        member_id=CRM_INQUIRY_BUYER_MEMBER_ID,
    )
    allure.attach(
        json.dumps(
            {"member_id": CRM_INQUIRY_BUYER_MEMBER_ID, "response": body},
            ensure_ascii=False,
            indent=2,
        ),
        name="inquiry_customer_brief",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"客户简要失败: {body}"
    data = body.get("data")
    assert isinstance(data, dict), f"简要 data 非对象: {body}"
