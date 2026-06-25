import json

import allure
import pytest

from config.settings import (
    ASSIGN_LEAD_CASES,
    ASSIGN_LEAD_LEAD_IDS,
    ASSIGN_LEAD_NEW_FOLLOW_USER_ID,
    ASSIGN_LEAD_NEW_FOLLOW_USER_NAME,
)


def _load_assign_lead_cases() -> list[dict]:
    """从环境变量加载分配用例；未配置 newFollowUserId 时通过 list 接口按姓名解析。"""
    if ASSIGN_LEAD_CASES:
        raw_cases = json.loads(ASSIGN_LEAD_CASES)
        if not isinstance(raw_cases, list) or not raw_cases:
            raise ValueError("ASSIGN_LEAD_CASES 必须是非空 JSON 数组")
        cases = []
        for index, item in enumerate(raw_cases):
            if not isinstance(item, dict):
                raise ValueError(f"ASSIGN_LEAD_CASES[{index}] 必须是对象")
            lead_ids = item.get("lead_ids") or item.get("leadIds")
            if not lead_ids:
                raise ValueError(f"ASSIGN_LEAD_CASES[{index}] 缺少 lead_ids / leadIds")
            follow_user_name = (
                item.get("new_follow_user_name")
                or item.get("newFollowUserName")
                or ASSIGN_LEAD_NEW_FOLLOW_USER_NAME
            )
            follow_user_id = item.get("new_follow_user_id") or item.get("newFollowUserId")
            cases.append(
                {
                    "lead_ids": [int(x) for x in lead_ids],
                    "new_follow_user_name": follow_user_name,
                    "new_follow_user_id": int(follow_user_id) if follow_user_id is not None else None,
                }
            )
        return cases

    return [
        {
            "lead_ids": ASSIGN_LEAD_LEAD_IDS,
            "new_follow_user_name": ASSIGN_LEAD_NEW_FOLLOW_USER_NAME,
            "new_follow_user_id": ASSIGN_LEAD_NEW_FOLLOW_USER_ID,
        }
    ]


def _case_id(case: dict) -> str:
    lead_ids = ",".join(str(x) for x in case["lead_ids"])
    follow_user_id = case.get("new_follow_user_id")
    follow_user_name = case.get("new_follow_user_name")
    if follow_user_id is None:
        return f"leads_{lead_ids}_user_{follow_user_name}"
    return f"leads_{lead_ids}_user_{follow_user_id}_{follow_user_name}"


_ASSIGN_LEAD_CASES = _load_assign_lead_cases()


@allure.feature("CRM 接口造数")
@allure.story("销售线索分配")
@pytest.mark.parametrize("case", _ASSIGN_LEAD_CASES, ids=[_case_id(c) for c in _ASSIGN_LEAD_CASES])
def test_assign_leads_by_api(auth_login_data, crm_lead_service, case):
    new_follow_user_id = case.get("new_follow_user_id")
    new_follow_user_name = case["new_follow_user_name"]
    user_list_body = None

    if new_follow_user_id is None:
        with allure.step(f"查询有效用户列表并解析跟进人: {new_follow_user_name}"):
            user_list_body = crm_lead_service.list_effective_users(
                member_id=auth_login_data["memberId"],
                user_id=auth_login_data["userId"],
                token=auth_login_data["token"],
            )
            new_follow_user_id, new_follow_user_name = crm_lead_service.resolve_follow_user_by_name(
                member_id=auth_login_data["memberId"],
                user_id=auth_login_data["userId"],
                token=auth_login_data["token"],
                follow_user_name=new_follow_user_name,
                list_body=user_list_body,
            )

    payload = crm_lead_service.build_assign_lead_payload(
        lead_ids=case["lead_ids"],
        new_follow_user_id=new_follow_user_id,
        new_follow_user_name=new_follow_user_name,
    )
    body = crm_lead_service.assign_leads(
        member_id=auth_login_data["memberId"],
        user_id=auth_login_data["userId"],
        token=auth_login_data["token"],
        payload=payload,
    )
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
