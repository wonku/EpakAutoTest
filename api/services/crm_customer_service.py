from __future__ import annotations

from typing import Any

from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.crm_lead_service import CrmLeadService
from config.settings import (
    API_TIMEOUT_SECONDS,
    CRM_ACTIVITY_PAGE_API_URL,
    CRM_CUSTOMER_CHECK_REPEAT_API_URL,
    CRM_CUSTOMER_DUP_REFERER,
    CRM_CUSTOMER_FIND_BY_ID_API_URL,
    CRM_CUSTOMER_PAGE_API_URL,
    CRM_CUSTOMER_REFERER,
    CRM_CUSTOMER_SAVE_API_URL,
    CRM_CUSTOMER_UPDATE_API_URL,
    CRM_CUSTOMER_VIEW_TYPE,
)


class CrmCustomerService:
    """CRM 客户模块接口（来源：录制会话 customer_main）。"""

    def __init__(self, client: ApiClient):
        self.client = client

    def build_headers(self, ctx: AuthContext, *, referer_path: str = CRM_CUSTOMER_REFERER) -> dict:
        return CrmLeadService.build_headers(ctx, referer_path=referer_path)

    @staticmethod
    def build_page_payload(
        *,
        current: int = 1,
        page_size: int = 10,
        view_type: int = CRM_CUSTOMER_VIEW_TYPE,
        company_name: str = "",
        province: str = "",
        customer_type: int | None = None,
        follow_user_id_list: list[int] | None = None,
        status_list: list[Any] | None = None,
        register_status_list: list[Any] | None = None,
        team_user_id_list: list[int] | None = None,
        sale_org_list: list[Any] | None = None,
        source_type_list: list[Any] | None = None,
        create_start_time: str = "",
        create_end_time: str = "",
        last_activity_start_time: str = "",
        last_activity_end_time: str = "",
        sort_field: Any = None,
        sort_type: str = "",
    ) -> dict:
        return {
            "current": current,
            "pageSize": page_size,
            "viewType": view_type,
            "companyName": company_name,
            "province": province,
            "customerType": customer_type,
            "followUserIdList": follow_user_id_list or [],
            "createStartTime": create_start_time,
            "createEndTime": create_end_time,
            "statusList": status_list or [],
            "registerStatusList": register_status_list or [],
            "teamUserIdList": team_user_id_list or [],
            "saleOrgList": sale_org_list or [],
            "sourceTypeList": source_type_list or [],
            "lastActivityStartTime": last_activity_start_time,
            "lastActivityEndTime": last_activity_end_time,
            "sortField": sort_field,
            "sortType": sort_type,
        }

    def query_customers(self, ctx: AuthContext, payload: dict | None = None) -> dict:
        body = payload or self.build_page_payload()
        resp = self.client.request(
            "POST",
            CRM_CUSTOMER_PAGE_API_URL,
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
        total = data.get("totalCount", data.get("total"))
        try:
            return int(total or 0)
        except (TypeError, ValueError):
            return 0

    def find_by_id(self, ctx: AuthContext, customer_id: int) -> dict:
        resp = self.client.request(
            "GET",
            CRM_CUSTOMER_FIND_BY_ID_API_URL,
            params={"id": customer_id},
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def check_repeat(
        self,
        ctx: AuthContext,
        *,
        company_name: str,
        current: int = 1,
        page_size: int = 10,
    ) -> dict:
        payload = {
            "current": current,
            "pageSize": page_size,
            "companyName": company_name,
        }
        resp = self.client.request(
            "POST",
            CRM_CUSTOMER_CHECK_REPEAT_API_URL,
            json_body=payload,
            headers=self.build_headers(ctx, referer_path=CRM_CUSTOMER_DUP_REFERER),
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
        is_select_children: bool = True,
    ) -> dict:
        payload = {
            "current": current,
            "pageSize": page_size,
            "activityRecordTypeCode": activity_record_type_code,
            "isSelectChildren": is_select_children,
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

    def save_customer(self, ctx: AuthContext, payload: dict) -> dict:
        resp = self.client.request(
            "POST",
            CRM_CUSTOMER_SAVE_API_URL,
            json_body=payload,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def update_customer(self, ctx: AuthContext, payload: dict) -> dict:
        resp = self.client.request(
            "POST",
            CRM_CUSTOMER_UPDATE_API_URL,
            json_body=payload,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def find_id_by_company_name(
        self, ctx: AuthContext, company_name: str, *, page_size: int = 20
    ) -> int | None:
        """按企业名称查列表，返回首条匹配 id（供 UI 造数登记回滚）。"""
        if not company_name:
            return None
        body = self.query_customers(
            ctx,
            self.build_page_payload(company_name=company_name, page_size=page_size),
        )
        if body.get("code") != 1000:
            return None
        needle = company_name.strip()
        for row in self.extract_rows(body):
            name = str(row.get("companyName") or "").strip()
            if needle == name or needle in name or name in needle:
                try:
                    return int(row["id"])
                except (KeyError, TypeError, ValueError):
                    continue
        return None

    def rollback_created_customer(
        self,
        *,
        customer_id: int | None,
        company_name: str,
        db_conn=None,
    ) -> bool:
        """回滚骨架入口；实际 SQL 见 utils.crm_data_rollback。"""
        from utils.crm_data_rollback import CreatedCustomerRef, rollback_created_customer

        return rollback_created_customer(
            CreatedCustomerRef(customer_id=customer_id, company_name=company_name),
            db_conn=db_conn,
        )
