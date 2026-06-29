import json

import allure
import pytest

from config.settings import (
    MOVE_PUBLIC_SEA_CASES,
    MOVE_PUBLIC_SEA_LEAD_IDS,
    MOVE_PUBLIC_SEA_REASON_CODE,
)
from tests.helpers.crm_case_loader import load_json_cases

pytestmark = pytest.mark.api


def _normalize_move_case(item: dict, index: int) -> dict:
    lead_ids = item.get("lead_ids") or item.get("leadIds")
    if not lead_ids:
        raise ValueError(f"MOVE_PUBLIC_SEA_CASES[{index}] 缺少 lead_ids / leadIds")
    return {
        "lead_ids": [int(x) for x in lead_ids],
        "public_sea_reason_code": item.get("public_sea_reason_code")
        or item.get("publicSeaReasonCode"),
        "remark": item.get("remark"),
    }


def _move_case_id(case: dict) -> str:
    lead_ids = ",".join(str(x) for x in case["lead_ids"])
    reason = case.get("public_sea_reason_code")
    if reason is None:
        reason = MOVE_PUBLIC_SEA_REASON_CODE
    return f"leads_{lead_ids}_reason_{reason}"


_MOVE_PUBLIC_SEA_CASES = load_json_cases(
    MOVE_PUBLIC_SEA_CASES,
    defaults=[
        {
            "lead_ids": MOVE_PUBLIC_SEA_LEAD_IDS,
            "public_sea_reason_code": None,
            "remark": None,
        }
    ],
    normalizer=_normalize_move_case,
    env_name="MOVE_PUBLIC_SEA_CASES",
)


@allure.feature("CRM 接口造数")
@allure.story("销售线索移入公海")
@pytest.mark.parametrize(
    "case",
    _MOVE_PUBLIC_SEA_CASES,
    ids=[_move_case_id(c) for c in _MOVE_PUBLIC_SEA_CASES],
)
def test_move_leads_to_public_sea_by_api(crm_auth, crm_lead_service, case):
    payload = crm_lead_service.build_move_public_sea_payload(
        lead_ids=case["lead_ids"],
        public_sea_reason_code=case.get("public_sea_reason_code"),
        remark=case.get("remark"),
    )
    body = crm_lead_service.move_leads_to_public_sea(crm_auth, payload)
    allure.attach(
        json.dumps({"request": payload, "response": body}, ensure_ascii=False, indent=2),
        name="move_public_sea_api_detail",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"移入公海失败: {body}"
