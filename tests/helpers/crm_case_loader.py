from __future__ import annotations

import json
from typing import Any, Callable


def load_json_cases(
    raw_json: str,
    *,
    defaults: list[dict[str, Any]],
    normalizer: Callable[[dict[str, Any], int], dict[str, Any]],
    env_name: str,
) -> list[dict[str, Any]]:
    if not raw_json:
        return defaults

    raw_cases = json.loads(raw_json)
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError(f"{env_name} 必须是非空 JSON 数组")

    cases: list[dict[str, Any]] = []
    for index, item in enumerate(raw_cases):
        if not isinstance(item, dict):
            raise ValueError(f"{env_name}[{index}] 必须是对象")
        cases.append(normalizer(item, index))
    return cases


def case_id_leads_and_user(case: dict[str, Any]) -> str:
    lead_ids = ",".join(str(x) for x in case["lead_ids"])
    follow_user_id = case.get("new_follow_user_id")
    follow_user_name = case.get("new_follow_user_name")
    if follow_user_id is None:
        return f"leads_{lead_ids}_user_{follow_user_name}"
    return f"leads_{lead_ids}_user_{follow_user_id}_{follow_user_name}"


def case_id_leads_only(case: dict[str, Any]) -> str:
    return "leads_" + ",".join(str(x) for x in case["lead_ids"])
