from __future__ import annotations

import json
import random
from datetime import datetime

from api.auth_context import AuthContext
from api.client import ApiClient
from config.settings import (
    API_TIMEOUT_SECONDS,
    AUTH_ENVIRONMENT,
    AUTH_SITE,
    AUTH_SOURCE,
    COUNTRY_LIST_API_URL,
    CRM_ACTIVITY_SAVE_API_URL,
    CRM_DEFAULT_FOLLOW_USER_ID,
    CRM_DEFAULT_FOLLOW_USER_NAME,
    LEAD_COUNTRY,
    LEAD_COUNTRY_CODE,
    CRM_LEAD_ASSIGN_API_URL,
    CRM_LEAD_CLAIM_API_URL,
    CRM_LEAD_MOVE_PUBLIC_SEA_API_URL,
    MEMBER_USER_EFFECTIVE_LIST_API_URL,
    CRM_LEAD_PAGE_API_URL,
    CRM_LEAD_SAVE_API_URL,
    MOVE_PUBLIC_SEA_REASON_CODE,
    MOVE_PUBLIC_SEA_REMARK,
    PLATFORM_BASE_URL,
)

CRM_SALES_CLUE_REFERER = "/memberCenter/crm2Ability/salesClue"


class CrmLeadService:
    def __init__(self, client: ApiClient):
        self.client = client

    @staticmethod
    def _parse_json_with_fallback(resp) -> dict:
        try:
            return resp.json()
        except Exception:
            pass
        raw = resp.content
        for enc in ("utf-8", "gb18030", "latin1"):
            try:
                return json.loads(raw.decode(enc))
            except Exception:
                continue
        raise AssertionError("国家接口响应无法解析为 JSON")

    @staticmethod
    def _normalize_text(value: str) -> str:
        return (value or "").strip().lower().replace(" ", "")

    @staticmethod
    def build_headers(ctx: AuthContext, referer_path: str = CRM_SALES_CLUE_REFERER) -> dict:
        return {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "environment": AUTH_ENVIRONMENT,
            "site": AUTH_SITE,
            "source": AUTH_SOURCE,
            "Origin": PLATFORM_BASE_URL,
            "Referer": f"{PLATFORM_BASE_URL}{referer_path}",
            "memberId": str(ctx.member_id),
            "userId": str(ctx.user_id),
            "token": ctx.token,
            "Authorization": ctx.token,
        }

    def build_random_lead_payload(
        self,
        ctx: AuthContext,
        *,
        follow_user_id: int = CRM_DEFAULT_FOLLOW_USER_ID,
        follow_user_name: str = CRM_DEFAULT_FOLLOW_USER_NAME,
        country: str = LEAD_COUNTRY,
        country_code: str = LEAD_COUNTRY_CODE,
    ) -> dict:
        if not country:
            raise AssertionError("country 不能为空，请在 .env 中设置 LEAD_COUNTRY")
        final_country_code = (country_code or "").strip()
        if not final_country_code:
            final_country_code = self.resolve_country_area_code(ctx, country_name=country)
        today = datetime.now().strftime("%y.%m.%d")
        suffix = random.randint(0, 999)
        phone = f"1{random.randint(30, 99)}{random.randint(1000, 9999)}{random.randint(1000, 9999)}"
        return {
            "name": f"tinker线索{today}-{suffix:03d}",
            "phone": phone,
            "email": f"{phone}@qq.com",
            "leadSourceCode": 4,
            "followUserAssignType": 2,
            "industryCode": "1,104",
            "countryCode": str(final_country_code),
            "inquiryKeywordCode": 4,
            "annualPurchaseUnitCode": 1,
            "country": country,
            "followUserId": follow_user_id,
            "followUserName": follow_user_name,
        }

    def resolve_country_area_code(self, ctx: AuthContext, *, country_name: str) -> str:
        resp = self.client.request(
            "GET",
            COUNTRY_LIST_API_URL,
            params={"pageNum": 1, "pageSize": 500},
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        body = self._parse_json_with_fallback(resp)
        rows = body.get("data", {}).get("data", [])
        target = self._normalize_text(country_name)
        for row in rows:
            name = self._normalize_text(str(row.get("name", "")))
            name_en = self._normalize_text(str(row.get("nameEn", "")))
            iso_code = self._normalize_text(str(row.get("code", "")))
            area_code = self._normalize_text(str(row.get("areaCode", "")))
            if target in (name, name_en, iso_code, area_code):
                area_code = row.get("areaCode")
                if area_code:
                    return str(area_code)
        raise AssertionError(f"未在国家接口中找到国家: {country_name}")

    def create_lead(self, ctx: AuthContext, payload: dict) -> dict:
        resp = self.client.request(
            "POST",
            CRM_LEAD_SAVE_API_URL,
            json_body=payload,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def build_activity_payload(
        *,
        relation_id: int,
        activity_type_code: int,
        activity_record_type_code: int,
    ) -> dict:
        return {
            "activityTypeCode": activity_type_code,
            "activityContent": "接口自动化test数据",
            "activityImages": [
                "https://zhaliyunoss.esbao.com/FILENAMEFIXED8c2246fd384248b5a4299d4a80305083.jpg"
            ],
            "remark": "活动记录test",
            "activityRecordTypeCode": activity_record_type_code,
            "relationId": relation_id,
        }

    def query_leads(
        self,
        ctx: AuthContext,
        *,
        phone: str | None = None,
        name: str | None = None,
        page_num: int = 1,
        page_size: int = 20,
    ) -> dict:
        payload: dict = {"pageNum": page_num, "pageSize": page_size}
        if phone:
            payload["phone"] = phone
        if name:
            payload["name"] = name
        resp = self.client.request(
            "POST",
            CRM_LEAD_PAGE_API_URL,
            json_body=payload,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def resolve_relation_id_from_created_lead(
        self,
        ctx: AuthContext,
        *,
        create_response: dict,
        create_payload: dict,
    ) -> int:
        data = create_response.get("data")
        if isinstance(data, dict):
            for key in ("id", "leadId", "relationId"):
                if data.get(key):
                    return int(data[key])
        if isinstance(data, int):
            return data

        query_body = self.query_leads(
            ctx,
            phone=create_payload.get("phone"),
            name=create_payload.get("name"),
            page_num=1,
            page_size=20,
        )
        rows = query_body.get("data", {}).get("data", [])
        for row in rows:
            if row.get("phone") == create_payload.get("phone") and row.get("name") == create_payload.get("name"):
                return int(row["id"])
        if rows and rows[0].get("id"):
            return int(rows[0]["id"])
        raise AssertionError(f"未能根据创建线索解析 relationId: {query_body}")

    def create_activity_record(self, ctx: AuthContext, payload: dict) -> dict:
        resp = self.client.request(
            "POST",
            CRM_ACTIVITY_SAVE_API_URL,
            json_body=payload,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def build_move_public_sea_payload(
        *,
        lead_ids: list[int],
        public_sea_reason_code: int | None = None,
        remark: str | None = None,
    ) -> dict:
        return {
            "leadIds": lead_ids,
            "publicSeaReasonCode": (
                public_sea_reason_code
                if public_sea_reason_code is not None
                else MOVE_PUBLIC_SEA_REASON_CODE
            ),
            "remark": remark if remark is not None else MOVE_PUBLIC_SEA_REMARK,
        }

    def move_leads_to_public_sea(self, ctx: AuthContext, payload: dict) -> dict:
        resp = self.client.request(
            "POST",
            CRM_LEAD_MOVE_PUBLIC_SEA_API_URL,
            json_body=payload,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def build_claim_lead_payload(*, lead_ids: list[int]) -> dict:
        return {"leadIds": lead_ids}

    def claim_leads(self, ctx: AuthContext, payload: dict) -> dict:
        resp = self.client.request(
            "POST",
            CRM_LEAD_CLAIM_API_URL,
            json_body=payload,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _extract_list_rows(body: dict) -> list[dict]:
        data = body.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("data", "list", "records"):
                rows = data.get(key)
                if isinstance(rows, list):
                    return rows
        return []

    def list_effective_users(self, ctx: AuthContext) -> dict:
        resp = self.client.request(
            "GET",
            MEMBER_USER_EFFECTIVE_LIST_API_URL,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return self._parse_json_with_fallback(resp)

    def resolve_follow_user_by_name(
        self,
        ctx: AuthContext,
        *,
        follow_user_name: str,
        list_body: dict | None = None,
    ) -> tuple[int, str]:
        body = list_body or self.list_effective_users(ctx)
        rows = self._extract_list_rows(body)
        target = self._normalize_text(follow_user_name)
        for row in rows:
            name_fields = (
                row.get("name"),
                row.get("userName"),
                row.get("nickName"),
                row.get("realName"),
                row.get("memberName"),
            )
            matched_name = next(
                (str(name) for name in name_fields if name and self._normalize_text(str(name)) == target),
                None,
            )
            if not matched_name:
                continue
            follow_user_id = row.get("id") or row.get("userId") or row.get("memberUserId")
            if follow_user_id:
                return int(follow_user_id), matched_name
        raise AssertionError(f"未在有效用户列表中找到跟进人: {follow_user_name}")

    @staticmethod
    def build_assign_lead_payload(
        *,
        lead_ids: list[int],
        new_follow_user_id: int,
        new_follow_user_name: str,
    ) -> dict:
        return {
            "leadIds": lead_ids,
            "newFollowUserId": new_follow_user_id,
            "newFollowUserName": new_follow_user_name,
        }

    def assign_leads(self, ctx: AuthContext, payload: dict) -> dict:
        resp = self.client.request(
            "POST",
            CRM_LEAD_ASSIGN_API_URL,
            json_body=payload,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()
