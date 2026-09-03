import json

import allure
import pytest

from config.settings import (
    CREATE_LEAD_CASES,
    CRM_EXHIBITION_ID,
    LEAD_COUNTRY,
    LEAD_COUNTRY_CODE,
    LEAD_EXHIBITION_NAME,
    LEAD_LEVEL,
    LEAD_LEVEL_CODE,
    LEAD_SOURCE,
    LEAD_SOURCE_CODE,
)
from tests.helpers.crm_case_loader import load_json_cases

pytestmark = pytest.mark.api


def _normalize_create_lead_case(item: dict, index: int) -> dict:
    lead_source_code = item.get("lead_source_code", item.get("leadSourceCode"))
    lead_level_code = item.get("lead_level_code", item.get("leadLevelCode"))
    crm_exhibition_id = item.get("crm_exhibition_id", item.get("crmExhibitionId"))
    return {
        "country": item.get("country") or LEAD_COUNTRY,
        "country_code": item.get("country_code") or item.get("countryCode") or LEAD_COUNTRY_CODE,
        "lead_source": item.get("lead_source") or item.get("leadSource") or "",
        "lead_source_code": int(lead_source_code) if lead_source_code is not None else None,
        "lead_level": item.get("lead_level") or item.get("leadLevel") or "",
        "lead_level_code": int(lead_level_code) if lead_level_code is not None else None,
        "exhibition_name": item.get("exhibition_name") or item.get("exhibitionName") or "",
        "crm_exhibition_id": int(crm_exhibition_id) if crm_exhibition_id is not None else None,
    }


def _case_id_create_lead(case: dict) -> str:
    parts = [
        case.get("lead_source") or (f"src{case['lead_source_code']}" if case.get("lead_source_code") is not None else "src_default"),
        case.get("lead_level") or (f"lv{case['lead_level_code']}" if case.get("lead_level_code") is not None else "lv_none"),
        case.get("exhibition_name")
        or (f"ex{case['crm_exhibition_id']}" if case.get("crm_exhibition_id") is not None else "ex_none"),
        case.get("country") or "country_default",
    ]
    return "_".join(parts)


_CREATE_LEAD_CASES = load_json_cases(
    CREATE_LEAD_CASES,
    defaults=[
        {
            "country": LEAD_COUNTRY,
            "country_code": LEAD_COUNTRY_CODE,
            "lead_source": LEAD_SOURCE,
            "lead_source_code": LEAD_SOURCE_CODE,
            "lead_level": LEAD_LEVEL,
            "lead_level_code": LEAD_LEVEL_CODE,
            "exhibition_name": LEAD_EXHIBITION_NAME,
            "crm_exhibition_id": CRM_EXHIBITION_ID,
        }
    ],
    normalizer=_normalize_create_lead_case,
    env_name="CREATE_LEAD_CASES",
)


@allure.feature("CRM 接口造数")
@allure.story("销售线索")
@allure.title("调用接口创建销售线索（来源/等级/展会可参数化）")
@pytest.mark.parametrize("case", _CREATE_LEAD_CASES, ids=[_case_id_create_lead(c) for c in _CREATE_LEAD_CASES])
def test_create_sales_lead_by_api(crm_auth, crm_lead_service, case):
    payload = crm_lead_service.build_random_lead_payload(
        crm_auth,
        country=case["country"],
        country_code=case["country_code"] or "",
        lead_source=case["lead_source"] or None,
        lead_source_code=case["lead_source_code"],
        lead_level=case["lead_level"] or None,
        lead_level_code=case["lead_level_code"],
        exhibition_name=case["exhibition_name"] or None,
        crm_exhibition_id=case["crm_exhibition_id"],
    )
    body = crm_lead_service.create_lead(crm_auth, payload)
    allure.attach(
        json.dumps({"case": case, "request": payload, "response": body}, ensure_ascii=False, indent=2),
        name="create_lead_api_detail",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"创建线索失败: {body}"


@allure.feature("CRM 接口造数")
@allure.story("销售线索")
@allure.title("调用接口创建德国销售线索")
def test_create_sales_lead_germany_by_api(crm_auth, crm_lead_service):
    payload = crm_lead_service.build_random_lead_payload(crm_auth, country="德国")
    body = crm_lead_service.create_lead(crm_auth, payload)
    relation_id = crm_lead_service.resolve_relation_id_from_created_lead(
        crm_auth,
        create_response=body,
        create_payload=payload,
    )
    allure.attach(
        json.dumps(
            {"request": payload, "response": body, "relation_id": relation_id},
            ensure_ascii=False,
            indent=2,
        ),
        name="create_germany_lead_api_detail",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"创建德国线索失败: {body}"
