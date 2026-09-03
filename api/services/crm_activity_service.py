from __future__ import annotations

from typing import Any

from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.crm_lead_service import CrmLeadService
from config.settings import (
    API_TIMEOUT_SECONDS,
    ACTIVITY_RECORD_TYPE_CODE,
    CRM_ACTIVITY_PAGE_API_URL,
    CRM_ACTIVITY_REFERER,
)


class CrmActivityService:
    """CRM 活动记录接口（来源：录制会话 activity_record_main / 20260810-135954）。"""

    def __init__(self, client: ApiClient):
        self.client = client

    def build_headers(
        self, ctx: AuthContext, *, referer_path: str = CRM_ACTIVITY_REFERER
    ) -> dict:
        return CrmLeadService.build_headers(ctx, referer_path=referer_path)

    @staticmethod
    def build_page_payload(
        *,
        current: int = 1,
        page_size: int = 20,
        activity_content: str = "",
        activity_type_code: str | int = "",
        activity_record_type_code: int | None = None,
        follow_id: list[Any] | None = None,
        create_time_start: str = "",
        create_time_end: str = "",
    ) -> dict:
        return {
            "current": current,
            "pageSize": page_size,
            "activityContent": activity_content,
            "activityTypeCode": activity_type_code,
            "activityRecordTypeCode": (
                ACTIVITY_RECORD_TYPE_CODE
                if activity_record_type_code is None
                else activity_record_type_code
            ),
            "followId": follow_id or [],
            "createTimeStart": create_time_start,
            "createTimeEnd": create_time_end,
        }

    def query_activity_page(self, ctx: AuthContext, payload: dict | None = None) -> dict:
        body = payload or self.build_page_payload()
        resp = self.client.request(
            "POST",
            CRM_ACTIVITY_PAGE_API_URL,
            json_body=body,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def extract_rows(page_body: dict) -> list[dict]:
        data = page_body.get("data")
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        rows = data.get("data") or data.get("records") or data.get("list") or []
        return rows if isinstance(rows, list) else []

    @staticmethod
    def extract_total(page_body: dict) -> int:
        data = page_body.get("data")
        if isinstance(data, list):
            return len(data)
        if not isinstance(data, dict):
            return 0
        for key in ("total", "totalCount", "count"):
            if data.get(key) is not None:
                try:
                    return int(data[key])
                except (TypeError, ValueError):
                    pass
        rows = data.get("data") or data.get("records") or data.get("list") or []
        return len(rows) if isinstance(rows, list) else 0
