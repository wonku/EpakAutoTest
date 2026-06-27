import json

import allure
import pytest

from config.settings import (
    CLAIM_LEAD_CASES,
    LOGIN_PASSWORD_ENCRYPTED,
    LOGIN_PHONE,
)


def _load_claim_lead_cases() -> list[dict]:
    """从环境变量加载认领用例；账号密码可省略，则使用默认登录配置。"""
    if CLAIM_LEAD_CASES:
        raw_cases = json.loads(CLAIM_LEAD_CASES)
        if not isinstance(raw_cases, list) or not raw_cases:
            raise ValueError("CLAIM_LEAD_CASES 必须是非空 JSON 数组")
        cases = []
        for index, item in enumerate(raw_cases):
            if not isinstance(item, dict):
                raise ValueError(f"CLAIM_LEAD_CASES[{index}] 必须是对象")
            lead_ids = item.get("lead_ids") or item.get("leadIds")
            if not lead_ids:
                raise ValueError(f"CLAIM_LEAD_CASES[{index}] 缺少 lead_ids / leadIds")
            account = item.get("account") or item.get("phone") or LOGIN_PHONE
            password_encrypted = (
                item.get("password_encrypted")
                or item.get("passwordEncrypted")
                or item.get("password")
                or LOGIN_PASSWORD_ENCRYPTED
            )
            cases.append(
                {
                    "account": account,
                    "password_encrypted": password_encrypted,
                    "lead_ids": [int(x) for x in lead_ids],
                }
            )
        return cases

    # 默认走自包含流程，避免 Jenkins/CI 依赖固定 leadId 是否已在公海
    return [
        {
            "account": LOGIN_PHONE,
            "password_encrypted": LOGIN_PASSWORD_ENCRYPTED,
            "prepare_public_sea_lead": True,
        }
    ]


def _case_id(case: dict) -> str:
    if case.get("prepare_public_sea_lead"):
        return f"{case['account']}_prepare_and_claim"
    lead_ids = ",".join(str(x) for x in case["lead_ids"])
    return f"{case['account']}_leads_{lead_ids}"


def _prepare_public_sea_lead(crm_lead_service, login_data: dict) -> int:
    """创建线索 → 移入公海，返回可用于认领的 leadId。"""
    member_id = login_data["memberId"]
    user_id = login_data["userId"]
    token = login_data["token"]

    lead_payload = crm_lead_service.build_random_lead_payload(
        member_id=member_id,
        user_id=user_id,
        token=token,
    )
    create_body = crm_lead_service.create_lead(
        member_id=member_id,
        user_id=user_id,
        token=token,
        payload=lead_payload,
    )
    assert create_body.get("code") == 1000, f"认领前置：创建线索失败: {create_body}"

    lead_id = crm_lead_service.resolve_relation_id_from_created_lead(
        create_response=create_body,
        create_payload=lead_payload,
        member_id=member_id,
        user_id=user_id,
        token=token,
    )
    move_payload = crm_lead_service.build_move_public_sea_payload(lead_ids=[lead_id])
    move_body = crm_lead_service.move_leads_to_public_sea(
        member_id=member_id,
        user_id=user_id,
        token=token,
        payload=move_payload,
    )
    assert move_body.get("code") == 1000, f"认领前置：移入公海失败: {move_body}"
    return lead_id


_CLAIM_LEAD_CASES = _load_claim_lead_cases()


@allure.feature("CRM 接口造数")
@allure.story("销售线索认领")
@pytest.mark.parametrize("case", _CLAIM_LEAD_CASES, ids=[_case_id(c) for c in _CLAIM_LEAD_CASES])
def test_claim_leads_by_api(auth_service, crm_lead_service, case):
    with allure.step(f"登录账号 {case['account']} 获取 token"):
        login_data = auth_service.login_with_encrypted_password(
            case["account"],
            case["password_encrypted"],
        )

    setup_detail = {}
    if case.get("prepare_public_sea_lead"):
        with allure.step("创建线索并移入公海，准备可认领数据"):
            lead_id = _prepare_public_sea_lead(crm_lead_service, login_data)
            lead_ids = [lead_id]
            setup_detail = {"prepared_lead_id": lead_id, "mode": "create_and_move_to_public_sea"}
    else:
        lead_ids = case["lead_ids"]

    payload = crm_lead_service.build_claim_lead_payload(lead_ids=lead_ids)
    body = crm_lead_service.claim_leads(
        member_id=login_data["memberId"],
        user_id=login_data["userId"],
        token=login_data["token"],
        payload=payload,
    )
    allure.attach(
        json.dumps(
            {
                "login_account": case["account"],
                "login_user_id": login_data.get("userId"),
                "login_member_id": login_data.get("memberId"),
                "setup": setup_detail,
                "request": payload,
                "response": body,
            },
            ensure_ascii=False,
            indent=2,
        ),
        name="claim_lead_api_detail",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"认领线索失败: {body}"
