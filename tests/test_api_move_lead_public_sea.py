import json

import allure
import pytest

from config.settings import (
    MOVE_PUBLIC_SEA_CASES,
    MOVE_PUBLIC_SEA_LEAD_IDS,
    MOVE_PUBLIC_SEA_REASON_CODE,
    MOVE_PUBLIC_SEA_REMARK,
)


def _load_move_public_sea_cases() -> list[dict]:
    """从环境变量加载移入公海用例；未配置 reason 时使用默认 publicSeaReasonCode。"""
    if MOVE_PUBLIC_SEA_CASES:
        raw_cases = json.loads(MOVE_PUBLIC_SEA_CASES)
        if not isinstance(raw_cases, list) or not raw_cases:
            raise ValueError("MOVE_PUBLIC_SEA_CASES 必须是非空 JSON 数组")
        cases = []
        for index, item in enumerate(raw_cases):
            if not isinstance(item, dict):
                raise ValueError(f"MOVE_PUBLIC_SEA_CASES[{index}] 必须是对象")
            lead_ids = item.get("lead_ids") or item.get("leadIds")
            if not lead_ids:
                raise ValueError(f"MOVE_PUBLIC_SEA_CASES[{index}] 缺少 lead_ids / leadIds")
            cases.append(
                {
                    "lead_ids": [int(x) for x in lead_ids],
                    "public_sea_reason_code": item.get("public_sea_reason_code")
                    or item.get("publicSeaReasonCode"),
                    "remark": item.get("remark"),
                }
            )
        return cases

    return [
        {
            "lead_ids": MOVE_PUBLIC_SEA_LEAD_IDS,
            "public_sea_reason_code": None,
            "remark": None,
        }
    ]


def _case_id(case: dict) -> str:
    lead_ids = ",".join(str(x) for x in case["lead_ids"])
    reason = case.get("public_sea_reason_code")
    if reason is None:
        reason = MOVE_PUBLIC_SEA_REASON_CODE
    return f"leads_{lead_ids}_reason_{reason}"


_MOVE_PUBLIC_SEA_CASES = _load_move_public_sea_cases()


@allure.feature("CRM 接口造数")
@allure.story("销售线索移入公海")
@pytest.mark.parametrize("case", _MOVE_PUBLIC_SEA_CASES, ids=[_case_id(c) for c in _MOVE_PUBLIC_SEA_CASES])
def test_move_leads_to_public_sea_by_api(auth_login_data, crm_lead_service, case):
    payload = crm_lead_service.build_move_public_sea_payload(
        lead_ids=case["lead_ids"],
        public_sea_reason_code=case.get("public_sea_reason_code"),
        remark=case.get("remark"),
    )
    body = crm_lead_service.move_leads_to_public_sea(
        member_id=auth_login_data["memberId"],
        user_id=auth_login_data["userId"],
        token=auth_login_data["token"],
        payload=payload,
    )
    allure.attach(
        json.dumps({"request": payload, "response": body}, ensure_ascii=False, indent=2),
        name="move_public_sea_api_detail",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"移入公海失败: {body}"
