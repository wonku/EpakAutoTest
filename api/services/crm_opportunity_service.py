from __future__ import annotations

from typing import Any

from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.crm_lead_service import CrmLeadService
from config.settings import (
    API_TIMEOUT_SECONDS,
    CRM_ACTIVITY_PAGE_API_URL,
    CRM_CONTACT_PERSON_PAGE_API_URL,
    CRM_OPPORTUNITY_DELETE_API_URL,
    CRM_OPPORTUNITY_FIND_BY_ID_API_URL,
    CRM_OPPORTUNITY_PAGE_API_URL,
    CRM_OPPORTUNITY_REFERER,
    CRM_OPPORTUNITY_SAVE_API_URL,
)


class CrmOpportunityService:
    """CRM 销售机会接口（来源：录制会话 opportunity_main）。"""

    def __init__(self, client: ApiClient):
        self.client = client

    def build_headers(
        self, ctx: AuthContext, *, referer_path: str = CRM_OPPORTUNITY_REFERER
    ) -> dict:
        return CrmLeadService.build_headers(ctx, referer_path=referer_path)

    @staticmethod
    def build_page_payload(
        *,
        current: int = 1,
        page_size: int = 10,
        name: str = "",
        opportunity_type_list: list[Any] | None = None,
        sale_stage_list: list[Any] | None = None,
        follow_user_id_list: list[int] | None = None,
        customer_id_list: list[int] | None = None,
        create_start_date: str = "",
        create_end_date: str = "",
        expected_transaction_start_date: str = "",
        expected_transaction_end_date: str = "",
    ) -> dict:
        return {
            "current": current,
            "pageSize": page_size,
            "name": name,
            "opportunityTypeList": opportunity_type_list or [],
            "saleStageList": sale_stage_list or [],
            "followUserIdList": follow_user_id_list or [],
            "customerIdList": customer_id_list or [],
            "createStartDate": create_start_date,
            "createEndDate": create_end_date,
            "expectedTransactionStartDate": expected_transaction_start_date,
            "expectedTransactionEndDate": expected_transaction_end_date,
        }

    def query_opportunities(self, ctx: AuthContext, payload: dict | None = None) -> dict:
        body = payload or self.build_page_payload()
        resp = self.client.request(
            "POST",
            CRM_OPPORTUNITY_PAGE_API_URL,
            json_body=body,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def extract_rows(page_body: dict) -> list[dict]:
        data = page_body.get("data")
        if not isinstance(data, dict):
            return []
        rows = data.get("data") or data.get("records") or data.get("list") or []
        return rows if isinstance(rows, list) else []

    @staticmethod
    def extract_total(page_body: dict) -> int:
        data = page_body.get("data")
        if not isinstance(data, dict):
            return 0
        try:
            return int(data.get("totalCount", data.get("total")) or 0)
        except (TypeError, ValueError):
            return 0

    def find_by_id(self, ctx: AuthContext, opportunity_id: int) -> dict:
        resp = self.client.request(
            "GET",
            CRM_OPPORTUNITY_FIND_BY_ID_API_URL,
            params={"id": opportunity_id},
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def query_activity_page(
        self,
        ctx: AuthContext,
        *,
        relation_id: int,
        activity_record_type_code: int,
        current: int = 1,
        page_size: int = 10,
    ) -> dict:
        payload = {
            "current": current,
            "pageSize": page_size,
            "activityRecordTypeCode": activity_record_type_code,
            "relationId": relation_id,
        }
        resp = self.client.request(
            "POST",
            CRM_ACTIVITY_PAGE_API_URL,
            json_body=payload,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def query_contact_persons(
        self,
        ctx: AuthContext,
        *,
        customer_id: int,
        current: int = 1,
        page_size: int = 500,
    ) -> dict:
        payload = {
            "current": current,
            "pageSize": page_size,
            "customerId": customer_id,
        }
        resp = self.client.request(
            "POST",
            CRM_CONTACT_PERSON_PAGE_API_URL,
            json_body=payload,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def save_or_update(self, ctx: AuthContext, payload: dict) -> dict:
        resp = self.client.request(
            "POST",
            CRM_OPPORTUNITY_SAVE_API_URL,
            json_body=payload,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def delete(self, ctx: AuthContext, *, sale_opportunity_id: int) -> dict:
        resp = self.client.request(
            "GET",
            CRM_OPPORTUNITY_DELETE_API_URL,
            params={"saleOpportunityId": sale_opportunity_id},
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()
