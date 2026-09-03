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
    CRM_DIC_BY_TYPE_API_URL,
    CRM_EXHIBITION_ID,
    CRM_EXHIBITION_OPTIONS_API_URL,
    CRM_ACTIVITY_PAGE_API_URL,
    CRM_LEAD_ASSIGN_API_URL,
    CRM_LEAD_CLAIM_API_URL,
    CRM_LEAD_DELETE_API_URL,
    CRM_LEAD_DETAIL_API_URL,
    CRM_LEAD_MOVE_PUBLIC_SEA_API_URL,
    CRM_LEAD_PAGE_API_URL,
    CRM_LEAD_SAVE_API_URL,
    LEAD_COUNTRY,
    LEAD_COUNTRY_CODE,
    LEAD_EXHIBITION_NAME,
    LEAD_LEVEL,
    LEAD_LEVEL_CODE,
    LEAD_SOURCE,
    LEAD_SOURCE_CODE,
    MEMBER_USER_EFFECTIVE_LIST_API_URL,
    MOVE_PUBLIC_SEA_REASON_CODE,
    MOVE_PUBLIC_SEA_REMARK,
    PLATFORM_BASE_URL,
)

CRM_SALES_CLUE_REFERER = "/memberCenter/crm2Ability/salesClue"
LEAD_SOURCE_ENUM = "LeadSourceEnum"
LEAD_LEVEL_ENUM = "LeadLevelEnum"
DEFAULT_LEAD_SOURCE_CODE = 4
OFFLINE_EXHIBITION_SOURCE_NAME = "展会"


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

    def query_dic_by_type(self, ctx: AuthContext, types: list[str]) -> dict:
        resp = self.client.request(
            "POST",
            CRM_DIC_BY_TYPE_API_URL,
            json_body={"types": types},
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return self._parse_json_with_fallback(resp)

    def list_exhibition_options(self, ctx: AuthContext) -> dict:
        resp = self.client.request(
            "GET",
            CRM_EXHIBITION_OPTIONS_API_URL,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return self._parse_json_with_fallback(resp)

    def _extract_dic_items(self, body: dict, enum_type: str) -> list[dict]:
        data = body.get("data")
        rows: list = []
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            for key in ("data", "list", "records", "enums", "dicList"):
                value = data.get(key)
                if isinstance(value, list):
                    rows = value
                    break
            if not rows and enum_type in data and isinstance(data[enum_type], list):
                rows = data[enum_type]
        for row in rows:
            if not isinstance(row, dict):
                continue
            if self._normalize_text(str(row.get("enumType", ""))) == self._normalize_text(enum_type):
                items = row.get("items")
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, dict)]
            items = row.get("items")
            if isinstance(items, list) and self._normalize_text(str(row.get("type", ""))) == self._normalize_text(
                enum_type
            ):
                return [item for item in items if isinstance(item, dict)]
        # 扁平结构：直接是 items 列表
        if rows and all(isinstance(row, dict) and ("code" in row or "desc" in row) for row in rows):
            return rows
        raise AssertionError(f"字典响应中未找到枚举 {enum_type}: {body}")

    def resolve_dic_item_code(
        self,
        ctx: AuthContext,
        *,
        enum_type: str,
        name: str | None = None,
        code: int | None = None,
        dic_body: dict | None = None,
    ) -> tuple[int, str]:
        if code is not None and not name:
            return int(code), str(code)
        body = dic_body or self.query_dic_by_type(ctx, [enum_type])
        items = self._extract_dic_items(body, enum_type)
        if code is not None:
            for item in items:
                if item.get("code") == code or str(item.get("code")) == str(code):
                    return int(item["code"]), str(item.get("desc") or item.get("name") or code)
            raise AssertionError(f"字典 {enum_type} 中未找到 code={code}")
        if not name:
            raise AssertionError(f"解析 {enum_type} 需提供 name 或 code")
        target = self._normalize_text(name)
        for item in items:
            candidates = (
                item.get("desc"),
                item.get("name"),
                item.get("label"),
                item.get("value"),
            )
            if any(c is not None and self._normalize_text(str(c)) == target for c in candidates):
                item_code = item.get("code")
                if item_code is None:
                    raise AssertionError(f"字典 {enum_type} 匹配到 {name} 但缺少 code: {item}")
                matched = next(str(c) for c in candidates if c is not None and self._normalize_text(str(c)) == target)
                return int(item_code), matched
        raise AssertionError(f"字典 {enum_type} 中未找到: {name}")

    def resolve_lead_source_code(
        self,
        ctx: AuthContext,
        *,
        lead_source: str | None = None,
        lead_source_code: int | None = None,
        dic_body: dict | None = None,
    ) -> tuple[int, str | None]:
        source_name = (lead_source if lead_source is not None else LEAD_SOURCE) or None
        source_code = lead_source_code if lead_source_code is not None else LEAD_SOURCE_CODE
        if source_name or source_code is not None:
            code, matched = self.resolve_dic_item_code(
                ctx,
                enum_type=LEAD_SOURCE_ENUM,
                name=source_name,
                code=source_code,
                dic_body=dic_body,
            )
            return code, matched
        return DEFAULT_LEAD_SOURCE_CODE, None

    def resolve_lead_level_code(
        self,
        ctx: AuthContext,
        *,
        lead_level: str | None = None,
        lead_level_code: int | None = None,
        dic_body: dict | None = None,
    ) -> tuple[int, str] | None:
        level_name = (lead_level if lead_level is not None else LEAD_LEVEL) or None
        level_code = lead_level_code if lead_level_code is not None else LEAD_LEVEL_CODE
        if not level_name and level_code is None:
            return None
        return self.resolve_dic_item_code(
            ctx,
            enum_type=LEAD_LEVEL_ENUM,
            name=level_name,
            code=level_code,
            dic_body=dic_body,
        )

    def resolve_exhibition(
        self,
        ctx: AuthContext,
        *,
        exhibition_name: str | None = None,
        crm_exhibition_id: int | None = None,
        options_body: dict | None = None,
    ) -> tuple[int, str] | None:
        name = (exhibition_name if exhibition_name is not None else LEAD_EXHIBITION_NAME) or None
        exhibition_id = crm_exhibition_id if crm_exhibition_id is not None else CRM_EXHIBITION_ID
        if not name and exhibition_id is None:
            return None
        body = options_body or self.list_exhibition_options(ctx)
        rows = self._extract_list_rows(body)
        if exhibition_id is not None:
            for row in rows:
                row_id = row.get("id") or row.get("crmExhibitionId") or row.get("value")
                if row_id is not None and int(row_id) == int(exhibition_id):
                    row_name = (
                        row.get("name")
                        or row.get("exhibitionName")
                        or row.get("label")
                        or name
                        or str(exhibition_id)
                    )
                    return int(row_id), str(row_name)
            if name:
                return int(exhibition_id), name
            raise AssertionError(f"展会 options 中未找到 id={exhibition_id}")
        target = self._normalize_text(name or "")
        for row in rows:
            candidates = (
                row.get("name"),
                row.get("exhibitionName"),
                row.get("label"),
                row.get("title"),
            )
            if any(c is not None and self._normalize_text(str(c)) == target for c in candidates):
                row_id = row.get("id") or row.get("crmExhibitionId") or row.get("value")
                if row_id is None:
                    raise AssertionError(f"展会匹配到 {name} 但缺少 id: {row}")
                matched = next(str(c) for c in candidates if c is not None and self._normalize_text(str(c)) == target)
                return int(row_id), matched
        raise AssertionError(f"展会 options 中未找到: {name}")

    def build_random_lead_payload(
        self,
        ctx: AuthContext,
        *,
        follow_user_id: int = CRM_DEFAULT_FOLLOW_USER_ID,
        follow_user_name: str = CRM_DEFAULT_FOLLOW_USER_NAME,
        country: str = LEAD_COUNTRY,
        country_code: str = LEAD_COUNTRY_CODE,
        lead_source: str | None = None,
        lead_source_code: int | None = None,
        lead_level: str | None = None,
        lead_level_code: int | None = None,
        exhibition_name: str | None = None,
        crm_exhibition_id: int | None = None,
    ) -> dict:
        if not country:
            raise AssertionError("country 不能为空，请在 .env 中设置 LEAD_COUNTRY")
        final_country_code = (country_code or "").strip()
        if not final_country_code:
            final_country_code = self.resolve_country_area_code(ctx, country_name=country)

        effective_source = lead_source if lead_source is not None else LEAD_SOURCE
        effective_source_code = lead_source_code if lead_source_code is not None else LEAD_SOURCE_CODE
        effective_level = lead_level if lead_level is not None else LEAD_LEVEL
        effective_level_code = lead_level_code if lead_level_code is not None else LEAD_LEVEL_CODE

        exhibition = self.resolve_exhibition(
            ctx,
            exhibition_name=exhibition_name,
            crm_exhibition_id=crm_exhibition_id,
        )
        # 指定了展会但未指定来源时，默认解析为「线下展会」
        if exhibition and not effective_source and effective_source_code is None:
            effective_source = OFFLINE_EXHIBITION_SOURCE_NAME

        dic_types: list[str] = []
        if effective_source:
            dic_types.append(LEAD_SOURCE_ENUM)
        if effective_level:
            dic_types.append(LEAD_LEVEL_ENUM)
        dic_body = self.query_dic_by_type(ctx, dic_types) if dic_types else None

        source_code, _ = self.resolve_lead_source_code(
            ctx,
            lead_source=effective_source or None,
            lead_source_code=effective_source_code,
            dic_body=dic_body,
        )
        level_resolved = self.resolve_lead_level_code(
            ctx,
            lead_level=effective_level or None,
            lead_level_code=effective_level_code,
            dic_body=dic_body,
        )

        today = datetime.now().strftime("%y.%m.%d")
        suffix = random.randint(0, 999)
        phone = f"1{random.randint(30, 99)}{random.randint(1000, 9999)}{random.randint(1000, 9999)}"
        name_prefix = "tinker展会线索" if exhibition else "tinker线索"
        payload = {
            "name": f"{name_prefix}{today}-{suffix:03d}",
            "phone": phone,
            "email": f"{phone}@qq.com",
            "leadSourceCode": source_code,
            "followUserAssignType": 2,
            "industryCode": "1,104",
            "countryCode": str(final_country_code),
            "inquiryKeywordCode": 4,
            "annualPurchaseUnitCode": 1,
            "country": country,
            "followUserId": follow_user_id,
            "followUserName": follow_user_name,
        }
        if level_resolved is not None:
            payload["leadLevelCode"] = level_resolved[0]
        if exhibition is not None:
            payload["crmExhibitionId"] = exhibition[0]
            payload["exhibitionName"] = exhibition[1]
        return payload

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
        """兼容旧造数查询（pageNum）；新列表请用 query_lead_page。"""
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

    @staticmethod
    def build_page_payload(
        *,
        current: int = 1,
        page_size: int = 10,
        name: str = "",
        company_name: str = "",
        phone: str | int | None = "",
        email: str = "",
        country_code_list: list | None = None,
        lead_source_code: list | None = None,
        created_by_list: list | None = None,
        create_time_start: str = "",
        create_time_end: str = "",
        follow_id: list | None = None,
        lead_level_code: int | None = None,
        lead_status_code: list | None = None,
        last_activity_start_time: str = "",
        last_activity_end_time: str = "",
        is_public_sea: int = 0,
        lead_sort_field_type_code: int | None = None,
        lead_sort_type: str = "",
    ) -> dict:
        """对齐录制 / UI 列表查询 body（current + pageSize）。"""
        return {
            "current": current,
            "pageSize": page_size,
            "name": name,
            "companyName": company_name,
            "phone": "" if phone is None else phone,
            "email": email,
            "countryCodeList": country_code_list or [],
            "leadSourceCode": lead_source_code or [],
            "createdByList": created_by_list or [],
            "createTimeStart": create_time_start,
            "createTimeEnd": create_time_end,
            "followId": follow_id or [],
            "leadLevelCode": lead_level_code,
            "leadStatusCode": lead_status_code or [],
            "lastActivityStartTime": last_activity_start_time,
            "lastActivityEndTime": last_activity_end_time,
            "isPublicSea": is_public_sea,
            "leadSortFieldTypeCode": lead_sort_field_type_code,
            "leadSortType": lead_sort_type,
        }

    def query_lead_page(self, ctx: AuthContext, payload: dict | None = None) -> dict:
        body = payload or self.build_page_payload()
        resp = self.client.request(
            "POST",
            CRM_LEAD_PAGE_API_URL,
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

    def get_lead_detail(self, ctx: AuthContext, lead_id: int) -> dict:
        resp = self.client.request(
            "GET",
            CRM_LEAD_DETAIL_API_URL,
            params={"leadId": lead_id},
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def query_lead_activity_page(
        self,
        ctx: AuthContext,
        *,
        relation_id: int,
        activity_record_type_code: int = 1,
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

    def delete_lead(self, ctx: AuthContext, lead_id: int) -> dict:
        """删除单条线索（我的/公海均可）。现网为 GET ?leadId=。"""
        resp = self.client.request(
            "GET",
            CRM_LEAD_DELETE_API_URL,
            params={"leadId": int(lead_id)},
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def find_leads_by_name(
        self,
        ctx: AuthContext,
        name: str,
        *,
        include_public_sea: bool = True,
        page_size: int = 50,
    ) -> list[dict]:
        """按姓名在我的线索 + 公海查找（回滚用）。"""
        text = (name or "").strip()
        if not text:
            return []
        seas = (0, 1) if include_public_sea else (0,)
        found: list[dict] = []
        seen: set[int] = set()
        for sea in seas:
            body = self.query_lead_page(
                ctx,
                self.build_page_payload(
                    name=text, page_size=page_size, is_public_sea=sea
                ),
            )
            for row in self.extract_rows(body):
                row_name = str(row.get("name") or "")
                if text not in row_name:
                    continue
                lead_id = row.get("id")
                if not lead_id or int(lead_id) in seen:
                    continue
                seen.add(int(lead_id))
                found.append(row)
        return found

    def rollback_created_lead(
        self,
        ctx: AuthContext,
        *,
        lead_id: int | None = None,
        name: str = "",
    ) -> list[int]:
        """回滚一条造数线索：按 id，必要时再按姓名扫我的/公海。"""
        ids: list[int] = []
        if lead_id:
            ids.append(int(lead_id))
        if name:
            for row in self.find_leads_by_name(ctx, name):
                rid = row.get("id")
                if rid and int(rid) not in ids:
                    ids.append(int(rid))
        deleted: list[int] = []
        for lid in ids:
            body = self.delete_lead(ctx, lid)
            if body.get("code") == 1000:
                deleted.append(lid)
            else:
                raise AssertionError(f"删除线索失败 id={lid}: {body}")
        return deleted

    def rollback_leads_by_name_prefix(
        self,
        ctx: AuthContext,
        prefix: str,
        *,
        page_size: int = 100,
    ) -> list[int]:
        """按姓名前缀批量回滚（含公海），用于清理历史自动化造数。"""
        text = (prefix or "").strip()
        assert text, "回滚前缀不能为空"
        return self.rollback_created_lead(ctx, name=text)
