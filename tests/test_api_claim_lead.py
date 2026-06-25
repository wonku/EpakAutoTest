import json

import allure
import pytest

from config.settings import (
    CLAIM_LEAD_CASES,
    CLAIM_LEAD_LEAD_IDS,
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

    return [
        {
            "account": LOGIN_PHONE,
            "password_encrypted": LOGIN_PASSWORD_ENCRYPTED,
            "lead_ids": CLAIM_LEAD_LEAD_IDS,
        }
    ]


def _case_id(case: dict) -> str:
    lead_ids = ",".join(str(x) for x in case["lead_ids"])
    return f"{case['account']}_leads_{lead_ids}"


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

    payload = crm_lead_service.build_claim_lead_payload(lead_ids=case["lead_ids"])
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
