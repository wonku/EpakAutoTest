from __future__ import annotations

from api.auth_context import AuthContext
from api.client import ApiClient
from config.settings import (
    API_TIMEOUT_SECONDS,
    AUTH_ENVIRONMENT,
    AUTH_SITE,
    AUTH_SOURCE,
    CRM_VISIT_SCHEDULE_DELETE_API_URL,
    CRM_VISIT_SCHEDULE_PAGE_API_URL,
    PLATFORM_BASE_URL,
)

CRM_VISIT_REFERER = "/memberCenter/crm2Ability/visitSchedule"


class CrmVisitScheduleService:
    def __init__(self, client: ApiClient):
        self.client = client

    @staticmethod
    def build_headers(ctx: AuthContext) -> dict:
        return {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "environment": AUTH_ENVIRONMENT,
            "site": AUTH_SITE,
            "source": AUTH_SOURCE,
            "Origin": PLATFORM_BASE_URL,
            "Referer": f"{PLATFORM_BASE_URL}{CRM_VISIT_REFERER}",
            "memberId": str(ctx.member_id),
            "userId": str(ctx.user_id),
            "token": ctx.token,
            "Authorization": ctx.token,
        }

    @staticmethod
    def build_page_payload(
        *,
        current: int = 1,
        page_size: int = 20,
        schedule_name: str = "",
        customer_ids: list | None = None,
    ) -> dict:
        return {
            "current": current,
            "pageSize": page_size,
            "scheduleName": schedule_name,
            "customerIds": customer_ids or [],
        }

    def query_page(self, ctx: AuthContext, payload: dict | None = None) -> dict:
        resp = self.client.request(
            "POST",
            CRM_VISIT_SCHEDULE_PAGE_API_URL,
            json_body=payload or self.build_page_payload(),
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

    def find_by_name(self, ctx: AuthContext, name: str) -> list[dict]:
        body = self.query_page(
            ctx, self.build_page_payload(schedule_name=name, page_size=50)
        )
        rows = []
        for row in self.extract_rows(body):
            if name in str(row.get("scheduleName") or row.get("name") or ""):
                rows.append(row)
        return rows

    def delete_schedule(self, ctx: AuthContext, schedule_id: int) -> dict:
        resp = self.client.request(
            "GET",
            CRM_VISIT_SCHEDULE_DELETE_API_URL,
            params={"id": int(schedule_id)},
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def rollback_by_name(self, ctx: AuthContext, name: str) -> list[int]:
        deleted: list[int] = []
        for row in self.find_by_name(ctx, name):
            sid = row.get("id") or row.get("scheduleId")
            if not sid:
                continue
            body = self.delete_schedule(ctx, int(sid))
            if body.get("code") == 1000:
                deleted.append(int(sid))
        return deleted
