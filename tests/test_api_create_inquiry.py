"""CRM 询价单接口造数：草稿 → 提交（来源录制 inquiry_main）。

运行:
  pytest tests/test_api_create_inquiry.py -m api -v -s
"""
from __future__ import annotations

import copy
import json
from datetime import datetime

import allure
import pytest

pytestmark = pytest.mark.api


@allure.feature("CRM 询价单")
@allure.story("创建询价")
@allure.title("接口创建内部询价单：草稿并提交成功")
def test_create_inquiry_draft_and_submit(crm_auth, crm_inquiry_service):
    stamp = datetime.now().strftime("%m%d%H%M%S")
    material_name = f"自动化物料_{stamp}"
    draft_payload = crm_inquiry_service.build_create_payload(
        material_name=material_name
    )

    with allure.step("保存草稿 addDraft"):
        draft_body = crm_inquiry_service.add_draft(crm_auth, draft_payload)
        allure.attach(
            json.dumps(
                {"request": draft_payload, "response": draft_body},
                ensure_ascii=False,
                indent=2,
            ),
            name="inquiry_add_draft",
            attachment_type=allure.attachment_type.JSON,
        )
        assert draft_body.get("code") == 1000, f"保存草稿失败: {draft_body}"
        main_id = crm_inquiry_service.extract_main_id(draft_body)
        assert main_id is not None, f"未返回询价主单 id: {draft_body}"

    with allure.step("提交 submitOrUpdate"):
        submit_payload = copy.deepcopy(draft_payload)
        submit_payload["id"] = main_id
        submit_payload["buyerMemberId"] = str(submit_payload["buyerMemberId"])
        for sub in submit_payload.get("subs") or []:
            sub.setdefault("skuName", None)
            sub.setdefault("skuAttribute", None)
        submit_body = crm_inquiry_service.submit_or_update(crm_auth, submit_payload)
        allure.attach(
            json.dumps(
                {"request": submit_payload, "response": submit_body},
                ensure_ascii=False,
                indent=2,
            ),
            name="inquiry_submit",
            attachment_type=allure.attachment_type.JSON,
        )
        assert submit_body.get("code") == 1000, f"提交询价失败: {submit_body}"

    with allure.step("列表回查新建单"):
        page_body = crm_inquiry_service.query_inquiries(
            crm_auth,
            crm_inquiry_service.build_query_payload(page_size=20),
        )
        assert page_body.get("code") == 1000, f"回查列表失败: {page_body}"
        rows = crm_inquiry_service.extract_rows(page_body)
        matched = [
            r
            for r in rows
            if str(r.get("iqrMainId") or r.get("id") or "") == str(main_id)
        ]
        allure.attach(
            json.dumps(
                {"main_id": main_id, "material_name": material_name, "matched": matched[:3]},
                ensure_ascii=False,
                indent=2,
            ),
            name="inquiry_list_recheck",
            attachment_type=allure.attachment_type.JSON,
        )
        assert matched, f"列表未找到新建询价主单 id={main_id}"
