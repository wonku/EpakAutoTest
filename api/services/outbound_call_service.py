from __future__ import annotations

from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.crm_lead_service import CRM_SALES_CLUE_REFERER, CrmLeadService
from config.settings import (
    API_TIMEOUT_SECONDS,
    CRM_YUYINGCLOUD_CALL_PHONE_API_URL,
    OUTBOUND_CALL_OPERATE_TYPE_CODE,
    PLATFORM_BASE_URL,
)


class OutboundCallService:
    def __init__(self, client: ApiClient | None = None):
        self.client = client or ApiClient(timeout=API_TIMEOUT_SECONDS)
        self._lead_service = CrmLeadService(self.client)

    def build_headers(self, ctx: AuthContext) -> dict:
        return CrmLeadService.build_headers(ctx, referer_path=CRM_SALES_CLUE_REFERER)

    def resolve_relation_id(self, ctx: AuthContext, relation_id: int | None = None) -> int:
        if relation_id is not None:
            return int(relation_id)
        query_body = self._lead_service.query_leads(ctx, page_num=1, page_size=1)
        rows = query_body.get("data", {}).get("data", [])
        if not rows:
            raise AssertionError(f"未找到可用线索 relationId: {query_body}")
        lead_id = rows[0].get("id") or rows[0].get("relationId") or rows[0].get("leadId")
        if not lead_id:
            raise AssertionError(f"线索记录缺少 id/relationId: {rows[0]}")
        return int(lead_id)

    def call_phone(
        self,
        ctx: AuthContext,
        *,
        relation_id: int,
        operate_type_code: int = OUTBOUND_CALL_OPERATE_TYPE_CODE,
    ) -> dict:
        payload = {
            "relationId": relation_id,
            "operateTypeCode": operate_type_code,
        }
        resp = self.client.request(
            "POST",
            CRM_YUYINGCLOUD_CALL_PHONE_API_URL,
            json_body=payload,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 1000:
            raise AssertionError(
                f"外呼接口调用失败 ({PLATFORM_BASE_URL}): {body}"
            )
        return body
