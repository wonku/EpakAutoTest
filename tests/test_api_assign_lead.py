import json

import allure
import pytest

from config.settings import (
    ASSIGN_LEAD_CASES,
    ASSIGN_LEAD_LEAD_IDS,
    ASSIGN_LEAD_NEW_FOLLOW_USER_ID,
    ASSIGN_LEAD_NEW_FOLLOW_USER_NAME,
)
from tests.helpers.crm_case_loader import case_id_leads_and_user, load_json_cases

pytestmark = pytest.mark.api


def _normalize_assign_case(item: dict, index: int) -> dict:
    lead_ids = item.get("lead_ids") or item.get("leadIds")
    if not lead_ids:
        raise ValueError(f"ASSIGN_LEAD_CASES[{index}] 缺少 lead_ids / leadIds")
    follow_user_name = (
        item.get("new_follow_user_name")
        or item.get("newFollowUserName")
        or ASSIGN_LEAD_NEW_FOLLOW_USER_NAME
    )
    follow_user_id = item.get("new_follow_user_id") or item.get("newFollowUserId")
    return {
        "lead_ids": [int(x) for x in lead_ids],
        "new_follow_user_name": follow_user_name,
        "new_follow_user_id": int(follow_user_id) if follow_user_id is not None else None,
    }


_ASSIGN_LEAD_CASES = load_json_cases(
    ASSIGN_LEAD_CASES,
    defaults=[
        {
            "lead_ids": ASSIGN_LEAD_LEAD_IDS,
            "new_follow_user_name": ASSIGN_LEAD_NEW_FOLLOW_USER_NAME,
            "new_follow_user_id": ASSIGN_LEAD_NEW_FOLLOW_USER_ID,
        }
    ],
    normalizer=_normalize_assign_case,
    env_name="ASSIGN_LEAD_CASES",
)


@allure.feature("CRM 接口造数")
@allure.story("销售线索分配")
@pytest.mark.parametrize("case", _ASSIGN_LEAD_CASES, ids=[case_id_leads_and_user(c) for c in _ASSIGN_LEAD_CASES])
def test_assign_leads_by_api(crm_auth, crm_lead_service, case):
    new_follow_user_id = case.get("new_follow_user_id")
    new_follow_user_name = case["new_follow_user_name"]
    user_list_body = None

    if new_follow_user_id is None:
        with allure.step(f"查询有效用户列表并解析跟进人: {new_follow_user_name}"):
            user_list_body = crm_lead_service.list_effective_users(crm_auth)
            new_follow_user_id, new_follow_user_name = crm_lead_service.resolve_follow_user_by_name(
                crm_auth,
                follow_user_name=new_follow_user_name,
                list_body=user_list_body,
            )

    payload = crm_lead_service.build_assign_lead_payload(
        lead_ids=case["lead_ids"],
        new_follow_user_id=new_follow_user_id,
        new_follow_user_name=new_follow_user_name,
    )
    body = crm_lead_service.assign_leads(crm_auth, payload)
    allure.attach(
        json.dumps(
            {
                "user_list_response": user_list_body,
                "request": payload,
                "response": body,
            },
            ensure_ascii=False,
            indent=2,
        ),
        name="assign_lead_api_detail",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"分配线索失败: {body}"
