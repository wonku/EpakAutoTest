from __future__ import annotations

import copy
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.auth_service import LoginExpiredError
from api.services.crm_inquiry_status import (
    BRANCH_TRANSITIONS,
    CUSTOM_PIPELINE,
    GENERAL_PIPELINE,
    InquiryAskPriceType,
    InquiryCreateRoute,
    InquiryCreateSource,
    InquiryFlowResult,
    InquiryForm,
    InquiryMall,
    InquiryOperateVia,
    InquiryRoleLogin,
    InquiryRoleMissing,
    InquiryStatus,
    InquirySubFlowResult,
    InquirySubSpec,
    InquiryTransition,
    InquiryTransitionNotWired,
    PIPELINES,
    cn_operate_transfer_blocked_message,
    default_inquiry_form,
    is_transition_wired,
    parse_ask_price_type,
    parse_create_source,
    parse_inquiry_form,
    parse_inquiry_mall,
    parse_inquiry_status,
    parse_operate_via,
    pipeline_until,
    resolve_role_ctx,
)
from api.services.order_service import OrderLineItem, OrderService
from config.settings import (
    API_TIMEOUT_SECONDS,
    AUTH_ENVIRONMENT,
    AUTH_SITE,
    AUTH_SOURCE,
    CRM_INQUIRY_ADD_DRAFT_API_URL,
    CRM_INQUIRY_ASK_PRICE_TYPE,
    CRM_INQUIRY_BUYER_MEMBER_ID,
    CRM_INQUIRY_BUYER_MEMBER_NAME,
    CRM_INQUIRY_BUYER_SALE_ORG_TYPE,
    CRM_INQUIRY_BUYER_USER_ID,
    CRM_INQUIRY_BUYER_USER_NAME,
    CRM_INQUIRY_CATEGORY_FULL_ID,
    CRM_INQUIRY_CREATE_SOURCE,
    CRM_INQUIRY_CUSTOMER_BRIEF_API_URL,
    CRM_INQUIRY_CUSTOMER_ID,
    CRM_INQUIRY_DETAIL_BY_SUB_API_URL,
    CRM_INQUIRY_EN_ADD_DRAFT_API_URL,
    CRM_INQUIRY_EN_BUYER_MEMBER_ID,
    CRM_INQUIRY_EN_BUYER_MEMBER_NAME,
    CRM_INQUIRY_EN_BUYER_USER_ID,
    CRM_INQUIRY_EN_BUYER_USER_NAME,
    CRM_INQUIRY_EN_CATEGORY_FULL_ID,
    CRM_INQUIRY_EN_QUERY_API_URL,
    CRM_INQUIRY_EN_SUBMIT_API_URL,
    CRM_INQUIRY_EN_SUBMIT_FACTORY_API_URL,
    CRM_INQUIRY_EN_CONFIRM_PRICE_API_URL,
    CRM_INQUIRY_EN_RELATION_PRODUCT_API_URL,
    CRM_INQUIRY_EN_RELATION_SKU_IDS,
    CRM_INQUIRY_EN_SUBMIT_CUSTOM_ORDER_API_URL,
    CRM_INQUIRY_EN_ORDER_CURRENCY_ID,
    CRM_INQUIRY_EN_ORDER_SHOP_CLASSIFY,
    CRM_INQUIRY_EN_ORDER_SHOP_NAME,
    CRM_INQUIRY_EN_ORDER_TRADE_MODE,
    CRM_INQUIRY_EN_SUBMIT_PLATFORM_API_URL,
    CRM_INQUIRY_EN_SUBMIT_TECH_API_URL,
    CRM_INQUIRY_EN_SUPPLIER_QUERY_API_URL,
    CRM_INQUIRY_EN_ADOPT_QUOTE_API_URL,
    CRM_INQUIRY_EN_OFFLINE_ADOPT_API_URL,
    CRM_INQUIRY_EN_OFFLINE_IS_PALLET,
    CRM_INQUIRY_EN_OFFLINE_PACKAGING_TYPE,
    CRM_INQUIRY_EN_OFFLINE_QUOTE_API_URL,
    CRM_INQUIRY_EN_FACTORY_ADOPT_SOURCE,
    CRM_INQUIRY_EN_FACTORY_CITY,
    CRM_INQUIRY_EN_COMPARE_PRICE_REMARK,
    CRM_INQUIRY_EN_PUSH_SUPPLIER_API_URL,
    CRM_INQUIRY_EN_QUOTE_CHANNELS,
    CRM_INQUIRY_EN_RECORDS_BY_SUB_API_URL,
    CRM_INQUIRY_EN_PLATFORM_DESC,
    CRM_INQUIRY_EN_PLATFORM_PRICE_TYPE,
    CRM_INQUIRY_EN_PLATFORM_UNIT_PRICE,
    CRM_INQUIRY_CN_SUPPLIER_QUERY_API_URL,
    CRM_INQUIRY_CN_SUPPLIER_QUOTE_API_URL,
    CRM_INQUIRY_SUPPLIER_PLATFORM_BASE_URL,
    CRM_INQUIRY_EN_TECH_FILE_NAME,
    CRM_INQUIRY_EN_TECH_FILE_URL,
    CRM_INQUIRY_EN_TECH_PROGRAM,
    CRM_INQUIRY_FORM,
    CRM_INQUIRY_MALL,
    CRM_INQUIRY_OPERATE_VIA,
    CRM_INQUIRY_QUERY_API_URL,
    CRM_INQUIRY_REFERER,
    CRM_INQUIRY_SOURCE_MALL_TYPE,
    CRM_INQUIRY_SUBMIT_API_URL,
    CRM_INQUIRY_TX_ADD_DRAFT_API_URL,
    CRM_INQUIRY_TX_SUBMIT_API_URL,
    CRM_INQUIRY_PURCHASER_ACCOUNT,
    CRM_INQUIRY_PURCHASER_PASSWORD_ENCRYPTED,
    CRM_INQUIRY_SUPPORT_ACCOUNT,
    CRM_INQUIRY_SUPPORT_PASSWORD_ENCRYPTED,
    CRM_INQUIRY_SUPPLIER_ACCOUNT,
    CRM_INQUIRY_SUPPLIER_MEMBER_ID,
    CRM_INQUIRY_SUPPLIER_MEMBER_NAME,
    CRM_INQUIRY_SUPPLIER_PASSWORD_ENCRYPTED,
    CRM_INQUIRY_TECH_ACCOUNT,
    CRM_INQUIRY_TECH_PASSWORD_ENCRYPTED,
    EPAK_INQUIRY_PURCHASER_ACCOUNT,
    EPAK_INQUIRY_PURCHASER_PASSWORD_ENCRYPTED,
    EPAK_INQUIRY_SUPPORT_ACCOUNT,
    EPAK_INQUIRY_SUPPORT_PASSWORD_ENCRYPTED,
    EPAK_INQUIRY_SUPPLIER_MEMBER_ID,
    EPAK_INQUIRY_SUPPLIER_MEMBER_NAME,
    EPAK_INQUIRY_TECH_ACCOUNT,
    EPAK_INQUIRY_TECH_PASSWORD_ENCRYPTED,
    EPAK_COMMODITY_GUEST_LIST_API_URL,
    EPAK_ORDER_AGENT_CREATE_API_URL,
    EPAK_PLATFORM_ACCEPT_LANGUAGE,
    EPAK_PLATFORM_BASE_URL,
    EPAK_PLATFORM_LANG_COOKIE,
    EPAK_RECEIVER_ADDRESS_AGENT_PAGE_API_URL,
    ORDER_BUYER_ROLE_ID,
    PLATFORM_BASE_URL,
)


@dataclass(frozen=True)
class EnOperationUrls:
    """英文询价流转所用接口（英文站 transaction 或中文站 crm/customer）。"""

    query: str
    submit_tech: str
    push_supplier: str
    offline_quote: str
    offline_adopt: str
    adopt_quote: str
    records_by_sub: str
    submit_factory: str
    submit_platform: str
    confirm_price: str
    relation_product: str
    submit_custom_order: str
    supplier_query: str


class CrmInquiryService:
    """询价单接口。

    创建入口：CRM 客户详情 或 交易能力-内部询价单。
    商城：中文商城 / 英文商城；中文商城可同时创建英文询价单。
    英文单操作站点：默认英文站；--operate-via cn 时走中文站 CRM（sourceMallType=2）。
    子单类型：通用品(1) / 定制品(2)，流转按子单独立推进。
    """

    def __init__(self, client: ApiClient):
        self.client = client
        self._active_source = parse_create_source(CRM_INQUIRY_CREATE_SOURCE)
        self._active_mall = parse_inquiry_mall(CRM_INQUIRY_MALL)
        self._active_form = (
            parse_inquiry_form(CRM_INQUIRY_FORM)
            if CRM_INQUIRY_FORM
            else default_inquiry_form(mall=self._active_mall, source=self._active_source)
        )
        self._active_operate_via = parse_operate_via(CRM_INQUIRY_OPERATE_VIA)

    @staticmethod
    def role_login_accounts(
        mall: InquiryMall | int | str,
        operate_via: InquiryOperateVia | str | None = None,
    ) -> list[InquiryRoleLogin]:
        mall_v = parse_inquiry_mall(mall)
        via = parse_operate_via(
            operate_via if operate_via is not None else CRM_INQUIRY_OPERATE_VIA
        )
        if mall_v == InquiryMall.EN:
            # 中文站操作英文单：采购等角色登录中文 auth；供应商仍走供应商中文站
            op_endpoint = "cn" if via == InquiryOperateVia.CN else "en"
            # EN support（如 18373383111）常仅存在于英文 auth；CN 操作优先 CRM_* 中文账号
            if via == InquiryOperateVia.CN and CRM_INQUIRY_SUPPORT_ACCOUNT:
                support_account = CRM_INQUIRY_SUPPORT_ACCOUNT
                support_password = CRM_INQUIRY_SUPPORT_PASSWORD_ENCRYPTED
            else:
                support_account = EPAK_INQUIRY_SUPPORT_ACCOUNT
                support_password = EPAK_INQUIRY_SUPPORT_PASSWORD_ENCRYPTED
            if via == InquiryOperateVia.CN and CRM_INQUIRY_TECH_ACCOUNT:
                tech_account = CRM_INQUIRY_TECH_ACCOUNT
                tech_password = CRM_INQUIRY_TECH_PASSWORD_ENCRYPTED
            else:
                tech_account = EPAK_INQUIRY_TECH_ACCOUNT
                tech_password = EPAK_INQUIRY_TECH_PASSWORD_ENCRYPTED
            if via == InquiryOperateVia.CN and CRM_INQUIRY_PURCHASER_ACCOUNT:
                purchaser_account = CRM_INQUIRY_PURCHASER_ACCOUNT
                purchaser_password = CRM_INQUIRY_PURCHASER_PASSWORD_ENCRYPTED
            else:
                purchaser_account = EPAK_INQUIRY_PURCHASER_ACCOUNT
                purchaser_password = EPAK_INQUIRY_PURCHASER_PASSWORD_ENCRYPTED
            return [
                InquiryRoleLogin(
                    "tech",
                    tech_account,
                    tech_password,
                    op_endpoint,
                ),
                InquiryRoleLogin(
                    "purchaser",
                    purchaser_account,
                    purchaser_password,
                    op_endpoint,
                ),
                InquiryRoleLogin(
                    "support",
                    support_account,
                    support_password,
                    op_endpoint,
                ),
                InquiryRoleLogin(
                    "supplier",
                    CRM_INQUIRY_SUPPLIER_ACCOUNT,
                    CRM_INQUIRY_SUPPLIER_PASSWORD_ENCRYPTED,
                    "supplier",
                ),
            ]
        return [
            InquiryRoleLogin("tech", CRM_INQUIRY_TECH_ACCOUNT, CRM_INQUIRY_TECH_PASSWORD_ENCRYPTED),
            InquiryRoleLogin(
                "purchaser",
                CRM_INQUIRY_PURCHASER_ACCOUNT,
                CRM_INQUIRY_PURCHASER_PASSWORD_ENCRYPTED,
            ),
            InquiryRoleLogin(
                "support",
                CRM_INQUIRY_SUPPORT_ACCOUNT,
                CRM_INQUIRY_SUPPORT_PASSWORD_ENCRYPTED,
            ),
        ]

    @staticmethod
    def reconcile_same_member_sessions(
        roles: dict[str, AuthContext],
    ) -> dict[str, AuthContext]:
        """保留角色独立会话；同会员互踢由步骤前重登处理。"""
        return dict(roles)

    @staticmethod
    def parse_en_quote_channels(value: str | None = None) -> set[str]:
        text = (value if value is not None else CRM_INQUIRY_EN_QUOTE_CHANNELS).strip().lower()
        if not text or text in {"both", "all", "全部"}:
            return {"online", "offline"}
        aliases = {
            "online": "online",
            "线上": "online",
            "offline": "offline",
            "线下": "offline",
        }
        found = set()
        for part in text.replace("，", ",").split(","):
            key = aliases.get(part.strip(), part.strip())
            if key in {"online", "offline"}:
                found.add(key)
        return found or {"online", "offline"}

    @staticmethod
    def resolve_en_factory_adopt_source(
        channels: set[str] | None = None,
        value: str | None = None,
    ) -> str:
        """出厂报价采纳来源：online / offline。

        both 且 auto 时默认 offline，使 submitFactoryPrice 带上线下采纳包装字段。
        """
        ch = set(channels or CrmInquiryService.parse_en_quote_channels())
        text = (value if value is not None else CRM_INQUIRY_EN_FACTORY_ADOPT_SOURCE).strip().lower()
        aliases = {
            "online": "online",
            "线上": "online",
            "offline": "offline",
            "线下": "offline",
            "auto": "auto",
            "": "auto",
        }
        key = aliases.get(text, text)
        if key == "auto":
            if "offline" in ch and "online" not in ch:
                return "offline"
            if "online" in ch and "offline" not in ch:
                return "online"
            # both：默认带线下包装提交出厂（与手工采纳线下 OFF 单一致）
            return "offline" if "offline" in ch else "online"
        if key == "offline" and "offline" not in ch and "online" in ch:
            return "online"
        if key == "online" and "online" not in ch and "offline" in ch:
            return "offline"
        return key if key in {"online", "offline"} else (
            "offline" if "offline" in ch else "online"
        )

    @staticmethod
    def en_factory_desc_from_packaging(
        *,
        packaging_type: int | None = None,
        is_pallet: int | None = None,
        fallback: str = "自动化出厂报价",
    ) -> str:
        pack = int(
            packaging_type
            if packaging_type is not None
            else CRM_INQUIRY_EN_OFFLINE_PACKAGING_TYPE
        )
        pallet = int(
            is_pallet if is_pallet is not None else CRM_INQUIRY_EN_OFFLINE_IS_PALLET
        )
        if pack == 3:
            return "其他包装"
        labels = {
            (1, 1): "箱装打托",
            (1, 0): "箱装不打托",
            (2, 1): "卷装打托",
            (2, 0): "卷装不打托",
        }
        return labels.get((pack, pallet), fallback)

    def set_create_source(self, source: InquiryCreateSource | str) -> InquiryCreateSource:
        self._active_source = parse_create_source(source)
        return self._active_source

    def resolve_route(
        self,
        *,
        source: InquiryCreateSource | str | None = None,
        mall: InquiryMall | int | str | None = None,
        form: InquiryForm | int | str | None = None,
        operate_via: InquiryOperateVia | str | None = None,
    ) -> InquiryCreateRoute:
        src = parse_create_source(source) if source is not None else self._active_source
        mall_v = parse_inquiry_mall(mall) if mall is not None else self._active_mall
        if form is not None:
            form_v = parse_inquiry_form(form)
        elif source is None and mall is None:
            form_v = self._active_form
        else:
            form_v = default_inquiry_form(mall=mall_v, source=src)
        if mall_v == InquiryMall.EN:
            form_v = InquiryForm.EN
        via = parse_operate_via(
            operate_via
            if operate_via is not None
            else (
                self._active_operate_via
                if source is None and mall is None
                else CRM_INQUIRY_OPERATE_VIA
            )
        )
        # 仅英文询价单支持切换操作站；其它路由固定英文站语义（无此字段意义）
        if mall_v != InquiryMall.EN:
            via = InquiryOperateVia.EN

        cn_origin = PLATFORM_BASE_URL.rstrip("/")
        en_origin = EPAK_PLATFORM_BASE_URL.rstrip("/")
        internal_add = "/memberCenter/transactionAbility/inquiryOffer/internalInquiry/add"

        if src == InquiryCreateSource.INTERNAL and mall_v == InquiryMall.CN and form_v == InquiryForm.CN:
            return InquiryCreateRoute(
                source=src,
                mall=mall_v,
                form=form_v,
                submit_url=CRM_INQUIRY_TX_SUBMIT_API_URL,
                add_draft_url=CRM_INQUIRY_TX_ADD_DRAFT_API_URL,
                origin=cn_origin,
                referer_path=f"{internal_add}?mallType=1",
                query_params={},
                submit_creates=True,
                supports_draft=False,
                operate_via=via,
            )
        if src == InquiryCreateSource.INTERNAL and mall_v == InquiryMall.CN and form_v == InquiryForm.EN:
            return InquiryCreateRoute(
                source=src,
                mall=mall_v,
                form=form_v,
                submit_url=CRM_INQUIRY_SUBMIT_API_URL,
                add_draft_url=CRM_INQUIRY_ADD_DRAFT_API_URL,
                origin=cn_origin,
                referer_path=f"{internal_add}?mallType=2",
                query_params={"sourceMallType": 2},
                submit_creates=True,
                supports_draft=False,
                operate_via=via,
            )
        if mall_v == InquiryMall.EN and via == InquiryOperateVia.CN:
            # 中文站操作英文单：创建/流转走 CRM + sourceMallType=2
            return InquiryCreateRoute(
                source=src,
                mall=mall_v,
                form=InquiryForm.EN,
                submit_url=f"{cn_origin}/api/crm/customer/iqrMain/submitOrUpdate",
                add_draft_url=f"{cn_origin}/api/crm/customer/iqrMain/addDraft",
                origin=cn_origin,
                referer_path=f"{internal_add}?mallType=2",
                query_params={"sourceMallType": 2},
                submit_creates=True,
                supports_draft=False,
                operate_via=via,
            )
        if mall_v == InquiryMall.EN:
            return InquiryCreateRoute(
                source=src,
                mall=mall_v,
                form=InquiryForm.EN,
                submit_url=CRM_INQUIRY_EN_SUBMIT_API_URL,
                add_draft_url=CRM_INQUIRY_EN_ADD_DRAFT_API_URL,
                origin=en_origin,
                referer_path=internal_add,
                query_params={},
                submit_creates=True,
                supports_draft=False,
                operate_via=InquiryOperateVia.EN,
            )
        return InquiryCreateRoute(
            source=src,
            mall=mall_v,
            form=form_v,
            submit_url=CRM_INQUIRY_SUBMIT_API_URL,
            add_draft_url=CRM_INQUIRY_ADD_DRAFT_API_URL,
            origin=cn_origin,
            referer_path=CRM_INQUIRY_REFERER,
            query_params={"sourceMallType": form_v.code},
            submit_creates=False,
            supports_draft=True,
            operate_via=via,
        )

    @classmethod
    def en_operation_urls(cls, route: InquiryCreateRoute) -> EnOperationUrls:
        """按操作站点解析英文询价流转 URL。"""
        if route.operate_via == InquiryOperateVia.CN:
            base = route.origin.rstrip("/")
            crm = f"{base}/api/crm/customer"
            return EnOperationUrls(
                query=f"{crm}/iqrMain/pageList",
                submit_tech=f"{crm}/iqrMain/submitTechProgram",
                push_supplier=f"{crm}/iqrSupplier/pushSupplier",
                offline_quote=f"{crm}/iqrOfflineQuote/save",
                offline_adopt=f"{crm}/iqrOfflineQuote/adopt",
                adopt_quote=f"{crm}/iqrSupplier/adopt",
                records_by_sub=f"{crm}/iqrSupplier/recordsBySub",
                submit_factory=f"{crm}/iqrMain/submitFactoryPrice",
                submit_platform=f"{crm}/iqrMain/submitPlatformPrice",
                confirm_price=f"{crm}/iqrMain/confirmPrice",
                relation_product=f"{crm}/iqrMain/relationProduct",
                submit_custom_order=f"{crm}/iqrMain/submitCustomOrder",
                supplier_query=f"{crm}/iqrSupplier/page",
            )
        return EnOperationUrls(
            query=CRM_INQUIRY_EN_QUERY_API_URL,
            submit_tech=CRM_INQUIRY_EN_SUBMIT_TECH_API_URL,
            push_supplier=CRM_INQUIRY_EN_PUSH_SUPPLIER_API_URL,
            offline_quote=CRM_INQUIRY_EN_OFFLINE_QUOTE_API_URL,
            offline_adopt=CRM_INQUIRY_EN_OFFLINE_ADOPT_API_URL,
            adopt_quote=CRM_INQUIRY_EN_ADOPT_QUOTE_API_URL,
            records_by_sub=CRM_INQUIRY_EN_RECORDS_BY_SUB_API_URL,
            submit_factory=CRM_INQUIRY_EN_SUBMIT_FACTORY_API_URL,
            submit_platform=CRM_INQUIRY_EN_SUBMIT_PLATFORM_API_URL,
            confirm_price=CRM_INQUIRY_EN_CONFIRM_PRICE_API_URL,
            relation_product=CRM_INQUIRY_EN_RELATION_PRODUCT_API_URL,
            submit_custom_order=CRM_INQUIRY_EN_SUBMIT_CUSTOM_ORDER_API_URL,
            supplier_query=CRM_INQUIRY_EN_SUPPLIER_QUERY_API_URL,
        )

    def build_headers(
        self,
        ctx: AuthContext,
        *,
        referer_path: str | None = None,
        source: InquiryCreateSource | str | None = None,
        route: InquiryCreateRoute | None = None,
        origin: str | None = None,
    ) -> dict:
        route = route or self.resolve_route(source=source)
        path = referer_path if referer_path is not None else route.referer_path
        origin = (origin or route.origin).rstrip("/")
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "environment": AUTH_ENVIRONMENT,
            "site": AUTH_SITE,
            "source": AUTH_SOURCE,
            "Origin": origin,
            "Referer": f"{origin}{path}" if path.startswith("/") else path,
            "memberId": str(ctx.member_id),
            "userId": str(ctx.user_id),
            "token": ctx.token,
            "Authorization": ctx.token,
        }
        if origin == EPAK_PLATFORM_BASE_URL.rstrip("/"):
            if EPAK_PLATFORM_ACCEPT_LANGUAGE:
                headers["Accept-Language"] = EPAK_PLATFORM_ACCEPT_LANGUAGE
            if EPAK_PLATFORM_LANG_COOKIE:
                headers["Cookie"] = EPAK_PLATFORM_LANG_COOKIE
        return headers

    @staticmethod
    def source_mall_params(
        *, source_mall_type: int = CRM_INQUIRY_SOURCE_MALL_TYPE
    ) -> dict[str, int]:
        return {"sourceMallType": source_mall_type}

    @staticmethod
    def build_query_payload(
        *,
        current: int = 1,
        page_size: int = 10,
        customer_id: int | None = CRM_INQUIRY_CUSTOMER_ID,
        buyer_member_id: int | None = CRM_INQUIRY_BUYER_MEMBER_ID,
    ) -> dict:
        payload: dict[str, Any] = {
            "current": current,
            "pageSize": page_size,
        }
        if customer_id is not None:
            payload["id"] = customer_id
        if buyer_member_id is not None:
            payload["buyerMemberId"] = buyer_member_id
        return payload

    def query_inquiries(
        self,
        ctx: AuthContext,
        payload: dict | None = None,
        *,
        source_mall_type: int | None = None,
        route: InquiryCreateRoute | None = None,
    ) -> dict:
        body = payload or self.build_query_payload()
        route = route or self.resolve_route()
        if route.mall == InquiryMall.EN:
            url = self.en_operation_urls(route).query
        else:
            url = CRM_INQUIRY_QUERY_API_URL
        params = dict(route.query_params)
        if source_mall_type is not None:
            params["sourceMallType"] = source_mall_type
        elif not params and route.mall != InquiryMall.EN:
            params = self.source_mall_params(source_mall_type=route.form.code)
        resp = self.client.request(
            "POST",
            url,
            params=params or None,
            json_body=body,
            headers=self.build_headers(ctx, route=route),
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

    @staticmethod
    def extract_first_sub_id(page_body: dict) -> int | None:
        rows = CrmInquiryService.extract_rows(page_body)
        for row in rows:
            subs = row.get("subs") or []
            if isinstance(subs, list) and subs:
                sub_id = subs[0].get("iqrSubId") or subs[0].get("id")
                if sub_id is not None:
                    return int(sub_id)
            main_id = row.get("iqrMainId") or row.get("id")
            if main_id is not None:
                # 无子单时无法走 detailBySub
                continue
        return None

    def detail_by_sub(
        self,
        ctx: AuthContext,
        *,
        sub_id: int,
        source_mall_type: int = CRM_INQUIRY_SOURCE_MALL_TYPE,
    ) -> dict:
        params = {
            "id": sub_id,
            **self.source_mall_params(source_mall_type=source_mall_type),
        }
        resp = self.client.request(
            "GET",
            CRM_INQUIRY_DETAIL_BY_SUB_API_URL,
            params=params,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def get_customer_brief(
        self,
        ctx: AuthContext,
        *,
        member_id: int = CRM_INQUIRY_BUYER_MEMBER_ID,
        source_mall_type: int = CRM_INQUIRY_SOURCE_MALL_TYPE,
    ) -> dict:
        resp = self.client.request(
            "POST",
            CRM_INQUIRY_CUSTOMER_BRIEF_API_URL,
            json_body={"memberId": member_id, "sourceMallType": source_mall_type},
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def build_cn_sub_payload(
        *,
        ask_price_type: InquiryAskPriceType | int | str = InquiryAskPriceType.CUSTOM,
        material_name: str | None = None,
        category_full_id: str = CRM_INQUIRY_CATEGORY_FULL_ID,
        qty: int = 10,
        year_purchase_qty: int = 1000,
        add_files: list[dict] | None = None,
        expected_transaction_date: str | None = None,
        extra_fields: dict | None = None,
        stamp: str | None = None,
    ) -> dict:
        stamp = stamp or datetime.now().strftime("%m%d%H%M%S")
        ask = parse_ask_price_type(ask_price_type)
        name = material_name or f"自动化物料_{ask.name}_{stamp}"
        expect_date = expected_transaction_date or (
            datetime.now() + timedelta(days=26)
        ).strftime("%Y-%m-%d")
        sub: dict[str, Any] = {
            "askPriceType": ask.code,
            "yearPurchaseQty": year_purchase_qty,
            "yearPurchaseQtyUnit": "公斤" if ask == InquiryAskPriceType.GENERAL else "个",
            "remark": f"自动化备注_{stamp}",
            "addFiles": add_files or [],
            "categoryFullId": category_full_id,
            "specificationModel": f"规格_{stamp}",
            "weight": "10",
            "weightUnit": "克",
            "material": "材质要求自动化",
            "length": 10,
            "lengthUnit": "mm",
            "width": 10,
            "widthUnit": "mm",
            "height": 10,
            "heightUnit": "mm",
            "name": name,
            "inside": "内装物品自动化",
            "colorCode": 5 if ask == InquiryAskPriceType.GENERAL else 6,
            "qty": qty,
            "unit": "套",
            "usageRequirement": "使用要求自动化",
            "testCondition": "测试条件自动化",
            "storageEnvironmentCode": 2 if ask == InquiryAskPriceType.GENERAL else 4,
            "expectedTransactionDate": expect_date,
        }
        if ask == InquiryAskPriceType.CUSTOM:
            sub["sealStyle"] = f"封口_{stamp}"
        if extra_fields:
            sub.update(extra_fields)
        return sub

    @staticmethod
    def build_en_sub_payload(
        *,
        ask_price_type: InquiryAskPriceType | int | str = InquiryAskPriceType.CUSTOM,
        material_name: str | None = None,
        category_full_id: str = CRM_INQUIRY_EN_CATEGORY_FULL_ID,
        qty: int = 10,
        year_purchase_qty: int | None = None,
        add_files: list[dict] | None = None,
        extra_fields: dict | None = None,
        stamp: str | None = None,
    ) -> dict:
        stamp = stamp or datetime.now().strftime("%m%d%H%M%S")
        ask = parse_ask_price_type(ask_price_type)
        name = material_name or f"EN_物料_{ask.name}_{stamp}"
        sub: dict[str, Any] = {
            "askPriceType": ask.code,
            "yearPurchaseQtyUnit": "万",
            "remark": f"自动化英文备注_{stamp}",
            "addFiles": add_files or [],
            "relationMainInfo": name,
            "categoryFullId": category_full_id,
            "weightUnit": "克",
            "materialGramWeight": "材质克重自动化",
            "lengthUnit": "mm",
            "widthUnit": "mm",
            "name": name,
            "color": "本色",
            "printingRequirement": "印刷要求自动化",
            "productDrawing": "产品图纸说明自动化",
            "urgencyLevel": "3-5天",
            "purchaseFrequency": "两个月一次",
            "targetUnitPrice": 100 if ask == InquiryAskPriceType.GENERAL else 17,
            "isImportedFromChina": "是",
            "hasCustomsOrderRecord": "是",
            "contentType": "内容物自动化",
            "sterilizationRequirement": "不杀菌" if ask == InquiryAskPriceType.GENERAL else "耐高温（>121°C）",
            "qty": qty if qty != 10 else (1999 if ask == InquiryAskPriceType.GENERAL else 1890),
            "storageEnvironment": "冷藏（0-4°C）",
            "shelfLifeRequirement": "货架期自动化",
            "productCertificationRequirement": "HACCP",
            "foodContactComplianceRequirement": "美国FDA标准",
            "labelRequirement": "标签要求自动化",
            "innerPackingRequirement": "内包装要求自动化",
            "outerPackingRequirement": "外包装要求自动化",
            "otherComplianceRequirement": "其他合规自动化",
            "specification": "1",
            "specUnit": 2 if ask == InquiryAskPriceType.GENERAL else 1,
            "productName": name,
        }
        if extra_fields:
            sub.update(extra_fields)
        return sub

    @classmethod
    def build_sub_payload(
        cls,
        *,
        ask_price_type: InquiryAskPriceType | int | str = InquiryAskPriceType.CUSTOM,
        material_name: str | None = None,
        category_full_id: str | None = None,
        qty: int = 10,
        year_purchase_qty: int = 1000,
        add_files: list[dict] | None = None,
        expected_transaction_date: str | None = None,
        extra_fields: dict | None = None,
        stamp: str | None = None,
        form: InquiryForm | int | str = InquiryForm.CN,
    ) -> dict:
        form_v = parse_inquiry_form(form)
        if form_v == InquiryForm.EN:
            return cls.build_en_sub_payload(
                ask_price_type=ask_price_type,
                material_name=material_name,
                category_full_id=category_full_id or CRM_INQUIRY_EN_CATEGORY_FULL_ID,
                qty=qty,
                year_purchase_qty=year_purchase_qty,
                add_files=add_files,
                extra_fields=extra_fields,
                stamp=stamp,
            )
        return cls.build_cn_sub_payload(
            ask_price_type=ask_price_type,
            material_name=material_name,
            category_full_id=category_full_id or CRM_INQUIRY_CATEGORY_FULL_ID,
            qty=qty,
            year_purchase_qty=year_purchase_qty,
            add_files=add_files,
            expected_transaction_date=expected_transaction_date,
            extra_fields=extra_fields,
            stamp=stamp,
        )

    @classmethod
    def build_create_payload(
        cls,
        *,
        material_name: str | None = None,
        buyer_member_id: int | None = None,
        buyer_member_name: str | None = None,
        buyer_user_id: int | None = None,
        buyer_user_name: str | None = None,
        buyer_sale_org_type: int = CRM_INQUIRY_BUYER_SALE_ORG_TYPE,
        category_full_id: str | None = None,
        address: str = "自动化详细地址",
        qty: int = 10,
        year_purchase_qty: int = 1000,
        add_files: list[dict] | None = None,
        expected_transaction_date: str | None = None,
        ask_price_type: InquiryAskPriceType | int | str | None = None,
        subs: list[InquirySubSpec | dict] | None = None,
        extra_main_fields: dict | None = None,
        extra_sub_fields: dict | None = None,
        form: InquiryForm | int | str = InquiryForm.CN,
    ) -> dict:
        stamp = datetime.now().strftime("%m%d%H%M%S")
        form_v = parse_inquiry_form(form)
        default_type = parse_ask_price_type(ask_price_type or CRM_INQUIRY_ASK_PRICE_TYPE)
        if form_v == InquiryForm.EN:
            buyer_member_id = CRM_INQUIRY_EN_BUYER_MEMBER_ID if buyer_member_id is None else buyer_member_id
            buyer_member_name = (
                CRM_INQUIRY_EN_BUYER_MEMBER_NAME if buyer_member_name is None else buyer_member_name
            )
            buyer_user_id = CRM_INQUIRY_EN_BUYER_USER_ID if buyer_user_id is None else buyer_user_id
            buyer_user_name = (
                CRM_INQUIRY_EN_BUYER_USER_NAME if buyer_user_name is None else buyer_user_name
            )
            category_full_id = category_full_id or CRM_INQUIRY_EN_CATEGORY_FULL_ID
        else:
            buyer_member_id = CRM_INQUIRY_BUYER_MEMBER_ID if buyer_member_id is None else buyer_member_id
            buyer_member_name = (
                CRM_INQUIRY_BUYER_MEMBER_NAME if buyer_member_name is None else buyer_member_name
            )
            buyer_user_id = CRM_INQUIRY_BUYER_USER_ID if buyer_user_id is None else buyer_user_id
            buyer_user_name = (
                CRM_INQUIRY_BUYER_USER_NAME if buyer_user_name is None else buyer_user_name
            )
            category_full_id = category_full_id or CRM_INQUIRY_CATEGORY_FULL_ID
        sub_specs = cls.normalize_sub_specs(
            subs,
            default_ask_price_type=default_type,
            default_material_name=material_name,
        )
        built_subs: list[dict] = []
        for index, spec in enumerate(sub_specs):
            built_subs.append(
                cls.build_sub_payload(
                    ask_price_type=spec.resolved_type(),
                    material_name=spec.material_name
                    or (material_name if index == 0 else None),
                    category_full_id=category_full_id,
                    qty=spec.qty if spec.qty is not None else qty,
                    year_purchase_qty=(
                        spec.year_purchase_qty
                        if spec.year_purchase_qty is not None
                        else year_purchase_qty
                    ),
                    add_files=add_files if index == 0 else None,
                    expected_transaction_date=expected_transaction_date,
                    extra_fields={
                        **(extra_sub_fields or {}),
                        **(spec.extra_fields or {}),
                    }
                    or None,
                    stamp=f"{stamp}_{index + 1}",
                    form=form_v,
                )
            )
        payload: dict[str, Any] = {
            "buyerSaleOrgType": buyer_sale_org_type,
            "buyerMemberId": buyer_member_id,
            "buyerMemberName": buyer_member_name,
            "buyerUserId": buyer_user_id,
            "buyerUserName": buyer_user_name,
            "subs": built_subs,
        }
        if form_v == InquiryForm.CN:
            payload.update(
                {
                    "countryName": "中国",
                    "countryCode": "100000",
                    "provinceCode": "310000",
                    "provinceName": "上海",
                    "cityCode": "310100",
                    "cityName": "上海市",
                    "districtCode": "310101",
                    "districtName": "黄浦区",
                    "streetCode": "310101002",
                    "streetName": "南京东路街道",
                    "address": address,
                }
            )
        else:
            payload.update(
                {
                    "companyInfoRemark": f"公司信息备注_{stamp}",
                    "companyInfoFiles": [],
                    "consumeHabitRemark": f"消费习惯备注_{stamp}",
                    "consumeHabitFiles": [],
                }
            )
        if extra_main_fields:
            payload.update(extra_main_fields)
        return payload

    @staticmethod
    def parse_packaging_type(value: Any) -> int | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            code = int(value)
            if code in (1, 2, 3):
                return code
            raise ValueError(f"包装类型无效: {value!r}，期望 1纸箱/2卷类/3其他")
        text = str(value).strip().lower()
        aliases = {
            "1": 1,
            "纸箱": 1,
            "箱装": 1,
            "carton": 1,
            "2": 2,
            "卷类": 2,
            "卷装": 2,
            "roll": 2,
            "3": 3,
            "其他": 3,
            "其它": 3,
            "other": 3,
        }
        if text in aliases:
            return aliases[text]
        raise ValueError(f"包装类型无效: {value!r}，期望 1纸箱/2卷类/3其他")

    @staticmethod
    def parse_is_pallet(value: Any) -> int | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, (int, float)):
            return 1 if int(value) else 0
        text = str(value).strip().lower()
        aliases = {
            "1": 1,
            "是": 1,
            "打托": 1,
            "true": 1,
            "yes": 1,
            "y": 1,
            "0": 0,
            "否": 0,
            "不打托": 0,
            "false": 0,
            "no": 0,
            "n": 0,
        }
        if text in aliases:
            return aliases[text]
        raise ValueError(f"是否打托无效: {value!r}，期望 1/0 或 是/否")

    @staticmethod
    def normalize_sub_specs(
        subs: list[InquirySubSpec | dict] | None,
        *,
        default_ask_price_type: InquiryAskPriceType,
        default_material_name: str | None = None,
        default_target: InquiryStatus | None = None,
    ) -> list[InquirySubSpec]:
        if not subs:
            return [
                InquirySubSpec(
                    ask_price_type=default_ask_price_type,
                    target_status=default_target,
                    material_name=default_material_name,
                )
            ]
        result: list[InquirySubSpec] = []
        for item in subs:
            if isinstance(item, InquirySubSpec):
                result.append(item)
                continue
            if not isinstance(item, dict):
                raise TypeError(f"子单规格必须是 InquirySubSpec 或 dict: {item!r}")
            result.append(
                InquirySubSpec(
                    ask_price_type=item.get("ask_price_type")
                    or item.get("askPriceType")
                    or default_ask_price_type,
                    target_status=item.get("target_status")
                    or item.get("targetStatus")
                    or default_target,
                    material_name=item.get("material_name")
                    or item.get("materialName")
                    or item.get("name")
                    or default_material_name,
                    qty=item.get("qty"),
                    year_purchase_qty=item.get("year_purchase_qty")
                    or item.get("yearPurchaseQty"),
                    extra_fields=item.get("extra_fields") or item.get("extraFields"),
                    quote_channels=item.get("quote_channels")
                    or item.get("quoteChannels")
                    or item.get("channels"),
                    adopt_source=item.get("adopt_source")
                    or item.get("adoptSource")
                    or item.get("factory_adopt_source")
                    or item.get("factoryAdoptSource"),
                    packaging_type=CrmInquiryService.parse_packaging_type(
                        item.get("packaging_type")
                        if "packaging_type" in item
                        else item.get("packagingType")
                        if "packagingType" in item
                        else item.get("pack")
                    ),
                    is_pallet=CrmInquiryService.parse_is_pallet(
                        item.get("is_pallet")
                        if "is_pallet" in item
                        else item.get("isPallet")
                        if "isPallet" in item
                        else item.get("pallet")
                    ),
                )
            )
        return result

    def add_draft(
        self,
        ctx: AuthContext,
        payload: dict,
        *,
        source_mall_type: int | None = None,
        source: InquiryCreateSource | str | None = None,
        route: InquiryCreateRoute | None = None,
    ) -> dict:
        route = route or self.resolve_route(source=source)
        params = dict(route.query_params)
        if source_mall_type is not None:
            params["sourceMallType"] = source_mall_type
        resp = self.client.request(
            "POST",
            route.add_draft_url,
            params=params or None,
            json_body=payload,
            headers=self.build_headers(ctx, route=route),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def submit_or_update(
        self,
        ctx: AuthContext,
        payload: dict,
        *,
        source_mall_type: int | None = None,
        source: InquiryCreateSource | str | None = None,
        route: InquiryCreateRoute | None = None,
    ) -> dict:
        route = route or self.resolve_route(source=source)
        params = dict(route.query_params)
        if source_mall_type is not None:
            params["sourceMallType"] = source_mall_type
        resp = self.client.request(
            "POST",
            route.submit_url,
            params=params or None,
            json_body=payload,
            headers=self.build_headers(ctx, route=route),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def extract_main_id(body: dict) -> int | None:
        data = body.get("data")
        if isinstance(data, int):
            return data
        if isinstance(data, str) and data.isdigit():
            return int(data)
        if isinstance(data, dict):
            for key in ("iqrMainId", "id", "data"):
                val = data.get(key)
                if val is not None and str(val).isdigit():
                    return int(val)
        return None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def assert_success(body: dict, context: str) -> dict:
        from api.services.auth_service import LOGIN_EXPIRED_CODE, LoginExpiredError

        if body.get("code") == LOGIN_EXPIRED_CODE:
            raise LoginExpiredError(f"{context}失败: {body}")
        if body.get("code") != 1000:
            raise AssertionError(f"{context}失败: {body}")
        return body

    @staticmethod
    def prepare_submit_payload(draft_payload: dict, main_id: int) -> dict:
        payload = copy.deepcopy(draft_payload)
        payload["id"] = main_id
        if payload.get("buyerMemberId") is not None:
            payload["buyerMemberId"] = str(payload["buyerMemberId"])
        for sub in payload.get("subs") or []:
            sub.setdefault("skuName", None)
            sub.setdefault("skuAttribute", None)
        return payload

    def find_row_by_main_id(
        self,
        ctx: AuthContext,
        main_id: int,
        *,
        page_size: int = 20,
        max_pages: int = 5,
        route: InquiryCreateRoute | None = None,
    ) -> dict | None:
        target = str(main_id)
        route = route or self.resolve_route()
        for page in range(1, max_pages + 1):
            body = self.query_inquiries(
                ctx,
                self.build_query_payload_for_route(
                    route, current=page, page_size=page_size
                ),
                route=route,
            )
            self.assert_success(body, "询价列表回查")
            for row in self.extract_rows(body):
                row_id = row.get("iqrMainId") or row.get("id")
                if str(row_id or "") == target:
                    return row
            if not self.extract_rows(body):
                break
        return None

    @classmethod
    def build_query_payload_for_route(
        cls,
        route: InquiryCreateRoute,
        *,
        current: int = 1,
        page_size: int = 10,
    ) -> dict:
        buyer_member_id = (
            CRM_INQUIRY_EN_BUYER_MEMBER_ID
            if route.form == InquiryForm.EN
            else CRM_INQUIRY_BUYER_MEMBER_ID
        )
        customer_id = (
            CRM_INQUIRY_CUSTOMER_ID
            if route.source == InquiryCreateSource.CRM_CUSTOMER
            else None
        )
        return cls.build_query_payload(
            current=current,
            page_size=page_size,
            customer_id=customer_id,
            buyer_member_id=buyer_member_id,
        )

    @classmethod
    def extract_first_sub(cls, row: dict | None) -> dict | None:
        if not isinstance(row, dict):
            return None
        subs = row.get("subs") or []
        if isinstance(subs, list) and subs and isinstance(subs[0], dict):
            return subs[0]
        return None

    @classmethod
    def extract_subs(cls, row: dict | None) -> list[dict]:
        if not isinstance(row, dict):
            return []
        subs = row.get("subs") or []
        return [s for s in subs if isinstance(s, dict)] if isinstance(subs, list) else []

    @classmethod
    def sub_snapshot(cls, row: dict, sub: dict) -> dict[str, Any]:
        return {
            "main_id": cls._to_int(row.get("iqrMainId") or row.get("id")),
            "main_number": row.get("iqrMainNumber"),
            "quotation_no": row.get("quotationNo"),
            "follow_status": cls._to_int(row.get("followStatus")),
            "follow_status_name": row.get("followStatusName"),
            "sub_id": cls._to_int(sub.get("iqrSubId") or sub.get("id")),
            "sub_number": sub.get("iqrSubNumber"),
            "ask_price_type": cls._to_int(sub.get("askPriceType")),
            "ask_price_type_name": sub.get("askPriceTypeName"),
            "status": cls._to_int(sub.get("status")),
            "status_name": sub.get("statusName"),
            "current_operator": sub.get("currentOperator"),
            "operate_btns": sub.get("operateBtns") or [],
            "row": row,
            "sub": sub,
        }

    def refresh_snapshot(
        self,
        ctx: AuthContext,
        main_id: int,
        *,
        sub_id: int | None = None,
        retries: int = 5,
        interval_seconds: float = 1.0,
        expected_status: int | None = None,
        route: InquiryCreateRoute | None = None,
    ) -> dict:
        last: dict | None = None
        route = route or self.resolve_route()
        for _ in range(max(retries, 1)):
            row = self.find_row_by_main_id(ctx, main_id, route=route)
            if row:
                subs = self.extract_subs(row)
                chosen = None
                if sub_id is not None:
                    for sub in subs:
                        if self._to_int(sub.get("iqrSubId") or sub.get("id")) == sub_id:
                            chosen = sub
                            break
                if chosen is None and subs:
                    chosen = subs[0]
                if chosen is not None:
                    snapshot = self.sub_snapshot(row, chosen)
                    snapshot["subs"] = [self.sub_snapshot(row, s) for s in subs]
                    last = snapshot
                    if expected_status is None or snapshot.get("status") == expected_status:
                        return snapshot
            time.sleep(interval_seconds)
        if last:
            return last
        raise AssertionError(f"列表未找到询价主单 id={main_id}")

    @staticmethod
    def describe_create_routes() -> list[dict[str, Any]]:
        svc = CrmInquiryService.__new__(CrmInquiryService)
        svc._active_operate_via = InquiryOperateVia.EN
        rows = []
        specs = [
            (InquiryCreateSource.INTERNAL, InquiryMall.CN, InquiryForm.CN, None),
            (InquiryCreateSource.INTERNAL, InquiryMall.CN, InquiryForm.EN, None),
            (InquiryCreateSource.INTERNAL, InquiryMall.EN, InquiryForm.EN, "en"),
            (InquiryCreateSource.INTERNAL, InquiryMall.EN, InquiryForm.EN, "cn"),
            (InquiryCreateSource.CRM_CUSTOMER, InquiryMall.CN, InquiryForm.CN, None),
        ]
        for source, mall, form, via in specs:
            route = CrmInquiryService.resolve_route(
                svc, source=source, mall=mall, form=form, operate_via=via
            )
            urls = (
                CrmInquiryService.en_operation_urls(route)
                if route.mall == InquiryMall.EN
                else None
            )
            rows.append(
                {
                    "label": route.label,
                    "source": route.source.value,
                    "mall": route.mall.label,
                    "form": route.form.label,
                    "operate_via": route.operate_via.value,
                    "operate_via_label": route.operate_via.label,
                    "origin": route.origin,
                    "submit_url": route.submit_url,
                    "offline_quote_url": urls.offline_quote if urls else None,
                    "referer_path": route.referer_path,
                    "query_params": route.query_params,
                    "submit_creates": route.submit_creates,
                    "supports_draft": route.supports_draft,
                }
            )
        return rows

    @staticmethod
    def describe_seed_pipeline(
        ask_price_type: InquiryAskPriceType | int | str | None = None,
    ) -> list[dict[str, Any]]:
        types = (
            [parse_ask_price_type(ask_price_type)]
            if ask_price_type is not None
            else list(PIPELINES.keys())
        )
        rows: list[dict[str, Any]] = []
        for ask in types:
            for step in PIPELINES[ask]:
                rows.append(
                    {
                        "ask_price_type": ask.code,
                        "ask_price_type_name": ask.label,
                        "code": step.to_status.code,
                        "name": step.to_status.label,
                        "role": step.role,
                        "wired": step.wired,
                        "wired_en_mall": is_transition_wired(
                            step, mall=InquiryMall.EN
                        ),
                        "handler": step.handler,
                        "recording_title": step.recording_title,
                        "ui_action": step.ui_action,
                        "operator_hint": step.operator_hint,
                        "branch": False,
                    }
                )
        for step in BRANCH_TRANSITIONS:
            rows.append(
                {
                    "ask_price_type": None,
                    "ask_price_type_name": "分支",
                    "code": step.to_status.code,
                    "name": step.to_status.label,
                    "role": step.role,
                    "wired": step.wired,
                    "handler": step.handler,
                    "recording_title": step.recording_title,
                    "ui_action": step.ui_action,
                    "operator_hint": step.operator_hint,
                    "branch": True,
                }
            )
        return rows

    def missing_seed_requirement(
        self,
        target: InquiryStatus | int | str,
        role_auths: dict[str, AuthContext] | None = None,
        *,
        ask_price_type: InquiryAskPriceType | int | str | None = None,
        source: InquiryCreateSource | str | None = None,
        mall: InquiryMall | int | str | None = None,
        form: InquiryForm | int | str | None = None,
        operate_via: InquiryOperateVia | str | None = None,
        subs: list[InquirySubSpec | dict] | None = None,
    ) -> str | None:
        src = parse_create_source(source or self._active_source)
        route = self.resolve_route(
            source=src, mall=mall, form=form, operate_via=operate_via
        )
        roles = dict(role_auths or {})
        default_ask = parse_ask_price_type(ask_price_type or CRM_INQUIRY_ASK_PRICE_TYPE)
        target_status = parse_inquiry_status(target) if target is not None else None
        specs = self.normalize_sub_specs(
            subs,
            default_ask_price_type=default_ask,
            default_target=target_status,
        )
        for spec in specs:
            ask = spec.resolved_type()
            sub_target = spec.resolved_target() or target_status
            if sub_target is None:
                continue
            if sub_target == InquiryStatus.DRAFT and not route.supports_draft:
                return (
                    f"{route.label} 录制接口为 submitOrUpdate 一次提交，"
                    "不支持单独保存草稿。请改用待提交技术方案（定制品）"
                    "或待出厂报价（通用品）。"
                )
            for step in pipeline_until(sub_target, ask_price_type=ask):
                if route.submit_creates and step.handler == "create_draft":
                    continue
                if (
                    route.operate_via == InquiryOperateVia.CN
                    and step.handler == "transfer_to_order"
                ):
                    return cn_operate_transfer_blocked_message()
                if resolve_role_ctx(roles, step.role, source=src) is None:
                    return str(InquiryRoleMissing(step.role, step))
                if (
                    step.handler == "submit_factory_quote"
                    and route.mall == InquiryMall.EN
                    and "online" in self.parse_en_quote_channels(spec.quote_channels)
                    and roles.get("supplier") is None
                ):
                    return str(InquiryRoleMissing("supplier", step))
                if not is_transition_wired(
                    step, mall=route.mall, operate_via=route.operate_via
                ) and step.handler not in (
                    "create_draft",
                    "submit_inquiry",
                ):
                    return str(
                        InquiryTransitionNotWired(step, ask_price_type=ask, source=src)
                    )
        return None

    def create_inquiry_to_status(
        self,
        sales_ctx: AuthContext,
        target: InquiryStatus | int | str | None = None,
        *,
        role_auths: dict[str, AuthContext] | None = None,
        payload: dict | None = None,
        material_name: str | None = None,
        ask_price_type: InquiryAskPriceType | int | str | None = None,
        source: InquiryCreateSource | str | None = None,
        mall: InquiryMall | int | str | None = None,
        form: InquiryForm | int | str | None = None,
        operate_via: InquiryOperateVia | str | None = None,
        subs: list[InquirySubSpec | dict] | None = None,
        extra_main_fields: dict | None = None,
        extra_sub_fields: dict | None = None,
        role_relogin: Callable[[str], AuthContext] | None = None,
    ) -> InquiryFlowResult:
        """创建主单并按各子单类型推进到目标状态。流转以子单为单位。

        role_relogin: 收到登录过期(1101)时按角色名重登，返回新 AuthContext。
        """
        src = self.set_create_source(source or self._active_source)
        route = self.resolve_route(
            source=src, mall=mall, form=form, operate_via=operate_via
        )
        self._active_mall = route.mall
        self._active_form = route.form
        self._active_operate_via = route.operate_via
        roles = {"sales": sales_ctx, **(role_auths or {})}
        roles = self.reconcile_same_member_sessions(roles)
        default_ask = parse_ask_price_type(ask_price_type or CRM_INQUIRY_ASK_PRICE_TYPE)
        default_target = (
            parse_inquiry_status(target)
            if target is not None
            else parse_inquiry_status(
                InquiryStatus.PENDING_TECH
                if default_ask == InquiryAskPriceType.CUSTOM
                else InquiryStatus.PENDING_FACTORY_QUOTE
            )
        )
        specs = self.normalize_sub_specs(
            subs,
            default_ask_price_type=default_ask,
            default_material_name=material_name,
            default_target=default_target,
        )
        create_payload = payload or self.build_create_payload(
            material_name=material_name,
            ask_price_type=default_ask,
            subs=specs,
            extra_main_fields=extra_main_fields,
            extra_sub_fields=extra_sub_fields,
            form=route.form,
        )
        steps: list[dict[str, Any]] = []

        create_step = next(s for s in CUSTOM_PIPELINE if s.handler == "create_draft")
        creator_ctx = resolve_role_ctx(roles, "creator", source=src)
        if creator_ctx is None:
            raise InquiryRoleMissing("creator", create_step)

        need_submit = any(
            (spec.resolved_target() or default_target) != InquiryStatus.DRAFT
            for spec in specs
        )
        if not route.supports_draft and not need_submit:
            raise InquiryTransitionNotWired(
                create_step, ask_price_type=default_ask, source=src
            )

        main_id: int | None = None
        if route.submit_creates and need_submit:
            submit_step = next(s for s in CUSTOM_PIPELINE if s.handler == "submit_inquiry")
            submit_result = self.submit_inquiry(
                creator_ctx,
                payload=create_payload,
                main_id=None,
                source=src,
                route=route,
                transition=submit_step,
            )
            steps.append(submit_result)
            main_id = submit_result.get("main_id")
        else:
            draft_result = self.create_draft(
                creator_ctx,
                payload=create_payload,
                source=src,
                route=route,
                transition=create_step,
            )
            steps.append(draft_result)
            main_id = draft_result.get("main_id")
            if main_id is None:
                raise AssertionError(f"保存草稿未返回主单 id: {draft_result}")
            if need_submit:
                submit_step = next(
                    s for s in CUSTOM_PIPELINE if s.handler == "submit_inquiry"
                )
                submit_result = self.submit_inquiry(
                    creator_ctx,
                    payload=create_payload,
                    main_id=main_id,
                    source=src,
                    route=route,
                    transition=submit_step,
                )
                steps.append(submit_result)
                main_id = submit_result.get("main_id") or main_id

        if main_id is None:
            raise AssertionError(f"创建询价未返回主单 id: {steps}")

        main_snapshot = self.refresh_snapshot(creator_ctx, main_id, route=route)
        steps.append({"step": "refresh_main", "snapshot": main_snapshot})
        sub_snaps = main_snapshot.get("subs") or [main_snapshot]
        if len(sub_snaps) < len(specs):
            raise AssertionError(
                f"期望 {len(specs)} 条子单，列表仅回查到 {len(sub_snaps)} 条，main_id={main_id}"
            )

        sub_results: list[InquirySubFlowResult] = []
        for index, spec in enumerate(specs):
            ask = spec.resolved_type()
            sub_target = spec.resolved_target() or default_target
            sub_snap = sub_snaps[index] if index < len(sub_snaps) else sub_snaps[-1]
            sub_id = sub_snap.get("sub_id")
            sub_steps: list[dict[str, Any]] = []

            # 提交后按类型校验首个业务状态
            if need_submit and sub_target != InquiryStatus.DRAFT:
                expected_after_submit = (
                    InquiryStatus.PENDING_TECH
                    if ask == InquiryAskPriceType.CUSTOM
                    else InquiryStatus.PENDING_FACTORY_QUOTE
                )
                if (
                    sub_target == expected_after_submit
                    and sub_snap.get("status") != expected_after_submit.code
                ):
                    raise AssertionError(
                        f"子单#{index + 1}[{ask.label}] 提交后期望 "
                        f"{expected_after_submit.label}，实际 "
                        f"{sub_snap.get('status_name')}({sub_snap.get('status')})"
                    )

            for transition in pipeline_until(sub_target, ask_price_type=ask):
                if transition.handler in ("create_draft", "submit_inquiry"):
                    continue

                if (
                    route.operate_via == InquiryOperateVia.CN
                    and transition.handler == "transfer_to_order"
                ):
                    raise InquiryTransitionNotWired(
                        transition,
                        ask_price_type=ask,
                        source=src,
                        message=cn_operate_transfer_blocked_message(),
                    )
                if not is_transition_wired(
                    transition, mall=route.mall, operate_via=route.operate_via
                ):
                    raise InquiryTransitionNotWired(
                        transition, ask_price_type=ask, source=src
                    )

                # 中文站同会员多用户会互踢：每步前重登当前角色，保证 token/user 匹配
                if route.operate_via == InquiryOperateVia.CN and role_relogin is not None:
                    login_key = transition.role
                    if login_key == "creator":
                        login_key = "purchaser" if "purchaser" in roles else "sales"
                    try:
                        roles[login_key] = role_relogin(login_key)
                    except AssertionError:
                        if login_key != "sales" and "sales" in roles:
                            roles[login_key] = role_relogin("sales")
                        else:
                            raise

                handler = getattr(self, transition.handler)
                retried = False
                while True:
                    ctx = resolve_role_ctx(roles, transition.role, source=src)
                    if ctx is None:
                        raise InquiryRoleMissing(transition.role, transition)
                    try:
                        step_result = handler(
                            ctx,
                            payload=create_payload,
                            main_id=main_id,
                            sub_id=sub_id,
                            snapshot=sub_snap,
                            transition=transition,
                            source=src,
                            route=route,
                            ask_price_type=ask,
                            role_auths=roles,
                            sub_spec=spec,
                        )
                        break
                    except LoginExpiredError:
                        if retried or role_relogin is None:
                            raise
                        retried = True
                        login_key = transition.role
                        if login_key == "creator":
                            login_key = "purchaser" if "purchaser" in roles else "sales"
                        roles[login_key] = role_relogin(login_key)
                        creator_ctx = (
                            resolve_role_ctx(roles, "creator", source=src) or creator_ctx
                        )
                sub_steps.append(step_result)
                steps.append(step_result)
                try:
                    # 回查用创建人会话；中文站若刚切到其他角色，需再登创建人
                    if route.operate_via == InquiryOperateVia.CN and role_relogin is not None:
                        creator_key = "purchaser" if "purchaser" in roles else "sales"
                        roles[creator_key] = role_relogin(creator_key)
                        creator_ctx = (
                            resolve_role_ctx(roles, "creator", source=src) or creator_ctx
                        )
                    sub_snap = self.refresh_snapshot(
                        creator_ctx,
                        main_id,
                        sub_id=sub_id,
                        expected_status=transition.to_status.code,
                        route=route,
                    )
                except LoginExpiredError:
                    if role_relogin is None:
                        raise
                    creator_key = "purchaser" if "purchaser" in roles else "sales"
                    roles[creator_key] = role_relogin(creator_key)
                    creator_ctx = (
                        resolve_role_ctx(roles, "creator", source=src) or creator_ctx
                    )
                    sub_snap = self.refresh_snapshot(
                        creator_ctx,
                        main_id,
                        sub_id=sub_id,
                        expected_status=transition.to_status.code,
                        route=route,
                    )
                sub_steps.append(
                    {
                        "step": "refresh_sub",
                        "sub_id": sub_id,
                        "status": sub_snap.get("status_name"),
                        "snapshot": sub_snap,
                    }
                )
                actual = sub_snap.get("status")
                if actual != transition.to_status.code:
                    raise AssertionError(
                        f"子单#{index + 1}[{ask.label}] 期望 "
                        f"{transition.to_status.label}({transition.to_status.code})，"
                        f"实际 {sub_snap.get('status_name')}({actual})，"
                        f"main_id={main_id} sub_id={sub_id}"
                    )

            # 最终目标校验（含仅草稿 / 仅提交）
            if sub_snap.get("status") != sub_target.code:
                raise AssertionError(
                    f"子单#{index + 1}[{ask.label}] 最终期望 "
                    f"{sub_target.label}({sub_target.code})，"
                    f"实际 {sub_snap.get('status_name')}({sub_snap.get('status')})"
                )

            sub_results.append(
                InquirySubFlowResult(
                    sub_id=sub_snap.get("sub_id"),
                    sub_number=sub_snap.get("sub_number"),
                    ask_price_type=sub_snap.get("ask_price_type") or ask.code,
                    ask_price_type_name=sub_snap.get("ask_price_type_name") or ask.label,
                    status=sub_snap.get("status"),
                    status_name=sub_snap.get("status_name"),
                    target=sub_target,
                    current_operator=sub_snap.get("current_operator"),
                    steps=sub_steps,
                    snapshot=sub_snap,
                )
            )

        first = sub_results[0] if sub_results else None
        return InquiryFlowResult(
            main_id=main_id,
            source=src,
            mall=route.mall,
            form=route.form,
            main_number=main_snapshot.get("main_number"),
            quotation_no=main_snapshot.get("quotation_no"),
            sub_id=first.sub_id if first else None,
            sub_number=first.sub_number if first else None,
            status=first.status if first else None,
            status_name=first.status_name if first else None,
            target=first.target if first else None,
            current_operator=first.current_operator if first else None,
            subs=sub_results,
            steps=steps,
            snapshot=main_snapshot,
        )

    def create_draft(
        self,
        ctx: AuthContext,
        *,
        payload: dict,
        main_id: int | None = None,
        snapshot: dict | None = None,
        transition: InquiryTransition | None = None,
        source: InquiryCreateSource | str | None = None,
        route: InquiryCreateRoute | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        del main_id, snapshot, transition
        body = self.add_draft(ctx, payload, source=source, route=route)
        self.assert_success(body, "保存草稿")
        created_id = self.extract_main_id(body)
        return {"step": "create_draft", "main_id": created_id, "request": payload, "response": body}

    def submit_inquiry(
        self,
        ctx: AuthContext,
        *,
        payload: dict,
        main_id: int | None,
        snapshot: dict | None = None,
        transition: InquiryTransition | None = None,
        source: InquiryCreateSource | str | None = None,
        route: InquiryCreateRoute | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        del snapshot, transition
        route = route or self.resolve_route(source=source)
        submit_payload = (
            payload
            if main_id is None
            else self.prepare_submit_payload(payload, main_id)
        )
        body = self.submit_or_update(ctx, submit_payload, source=source, route=route)
        self.assert_success(body, "提交询价")
        created_id = self.extract_main_id(body) or main_id
        return {
            "step": "submit_inquiry",
            "main_id": created_id,
            "request": submit_payload,
            "response": body,
        }

    @staticmethod
    def build_en_tech_program_payload(
        *,
        sub_id: int | str,
        tech_program: str | None = None,
        files: list[dict] | None = None,
        submit_flag: bool = True,
    ) -> dict[str, Any]:
        attachments = files
        if attachments is None and CRM_INQUIRY_EN_TECH_FILE_URL:
            attachments = [
                {
                    "name": CRM_INQUIRY_EN_TECH_FILE_NAME,
                    "url": CRM_INQUIRY_EN_TECH_FILE_URL,
                }
            ]
        return {
            "iqrSubId": str(sub_id),
            "submitFlag": submit_flag,
            "techProgram": tech_program or CRM_INQUIRY_EN_TECH_PROGRAM,
            "techProgramFiles": attachments or [],
        }

    @staticmethod
    def en_tech_edit_referer(
        *,
        sub_id: int | str,
        ask_price_type: InquiryAskPriceType | int | str = InquiryAskPriceType.CUSTOM,
        status: int = InquiryStatus.PENDING_TECH.code,
        route: InquiryCreateRoute | None = None,
    ) -> str:
        ask = parse_ask_price_type(ask_price_type)
        mall_q = (
            "&mallType=2"
            if route is not None and route.operate_via == InquiryOperateVia.CN
            else ""
        )
        return (
            "/memberCenter/transactionAbility/inquiryOffer/internalInquiry/edit"
            f"?id={sub_id}&formStatus=1{mall_q}&inquirySteps=2"
            f"&askPriceType={ask.code}&status={status}"
        )

    def submit_tech_solution(
        self,
        ctx: AuthContext,
        *,
        payload: dict | None = None,
        main_id: int | None = None,
        sub_id: int | None = None,
        snapshot: dict | None = None,
        transition: InquiryTransition | None = None,
        source: InquiryCreateSource | str | None = None,
        route: InquiryCreateRoute | None = None,
        ask_price_type: InquiryAskPriceType | int | str | None = None,
        tech_program: str | None = None,
        tech_files: list[dict] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        del payload
        route = route or self.resolve_route(source=source)
        step = transition or self._transition_by_handler("submit_tech_solution")
        if route.mall != InquiryMall.EN:
            raise InquiryTransitionNotWired(
                step,
                ask_price_type=ask_price_type,
                source=source or route.source,
            )
        resolved_sub_id = sub_id or (snapshot or {}).get("sub_id")
        if resolved_sub_id is None:
            raise AssertionError("提交技术方案缺少 iqrSubId")
        ask = parse_ask_price_type(ask_price_type or InquiryAskPriceType.CUSTOM)
        body_payload = self.build_en_tech_program_payload(
            sub_id=resolved_sub_id,
            tech_program=tech_program,
            files=tech_files,
        )
        referer_path = self.en_tech_edit_referer(
            sub_id=resolved_sub_id,
            ask_price_type=ask,
            route=route,
        )
        urls = self.en_operation_urls(route)
        resp = self.client.request(
            "POST",
            urls.submit_tech,
            params=dict(route.query_params) or None,
            json_body=body_payload,
            headers=self.build_headers(ctx, referer_path=referer_path, route=route),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        body = resp.json()
        self.assert_success(body, "提交技术方案")
        return {
            "step": "submit_tech_solution",
            "main_id": main_id,
            "sub_id": int(resolved_sub_id),
            "request": body_payload,
            "response": body,
        }

    def _json_post(
        self,
        ctx: AuthContext,
        url: str,
        payload: dict,
        *,
        route: InquiryCreateRoute,
        referer_path: str,
        origin: str | None = None,
    ) -> dict:
        params = dict(route.query_params) if route.query_params else None
        resp = self.client.request(
            "POST",
            url,
            params=params,
            json_body=payload,
            headers=self.build_headers(
                ctx, referer_path=referer_path, route=route, origin=origin
            ),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def extract_push_quote_id(body: dict | None) -> int | None:
        if not isinstance(body, dict):
            return None
        data = body.get("data")
        if isinstance(data, int):
            return data
        if isinstance(data, str) and data.isdigit():
            return int(data)
        if isinstance(data, dict):
            return CrmInquiryService._to_int(data.get("id") or data.get("iqrSupplierId"))
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                return CrmInquiryService._to_int(
                    first.get("id") or first.get("iqrSupplierId")
                )
            return CrmInquiryService._to_int(first)
        return None

    @classmethod
    def extract_nested_id(cls, value: Any, keys: tuple[str, ...] = ("id", "iqrSupplierId", "giqrId")) -> int | None:
        found = cls._to_int(value) if not isinstance(value, (dict, list)) else None
        if found is not None:
            return found
        if isinstance(value, dict):
            for key in keys:
                found = cls._to_int(value.get(key))
                if found is not None:
                    return found
            data = value.get("data")
            if data is not None and data is not value:
                found = cls.extract_nested_id(data, keys)
                if found is not None:
                    return found
            for nested in value.values():
                if isinstance(nested, (dict, list)):
                    found = cls.extract_nested_id(nested, keys)
                    if found is not None:
                        return found
        if isinstance(value, list):
            for item in value:
                found = cls.extract_nested_id(item, keys)
                if found is not None:
                    return found
        return None

    @classmethod
    def extract_quote_number(cls, row: dict | None) -> str | None:
        if not isinstance(row, dict):
            return None
        for key in (
            "factorySourceNo",
            "giqrNo",
            "offNo",
            "offlineNumber",
            "offlineNo",
            "offlineQuoteNo",
            "number",
            "iqrSupplierNumber",
            "iqrSubNumber",
            "sourceNo",
        ):
            val = row.get(key)
            if val is True or val is False or val is None or val == "":
                continue
            text = str(val).strip()
            if text.lower() in {"true", "false"}:
                continue
            if text:
                return text
        return None

    @staticmethod
    def build_en_offline_factory_source_no(
        *,
        main_number: str | None = None,
        main_id: int | str | None = None,
        sub_index: int = 1,
        quote_index: int = 1,
    ) -> str:
        """线下报价单号：OFFe{主单号数字}-{子单序号}-{线下报价序号}。"""
        import re

        digits = None
        if main_number:
            matched = re.search(r"(\d+)$", str(main_number))
            if matched:
                digits = matched.group(1)
        if not digits and main_id is not None:
            digits = f"{int(main_id):08d}"
        if not digits:
            return ""
        return f"OFFe{digits}-{int(sub_index)}-{int(quote_index)}"

    @classmethod
    def build_en_push_supplier_payload(
        cls,
        *,
        sub_id: int | str,
        remark: str | None = None,
        files: list[dict] | None = None,
    ) -> dict[str, Any]:
        attachments = files or [
            {
                "name": CRM_INQUIRY_EN_TECH_FILE_NAME,
                "url": CRM_INQUIRY_EN_TECH_FILE_URL,
            }
        ]
        return {
            "iqrSubId": str(sub_id),
            "requireRemark": remark or "自动化推送供应商",
            "pushFiles": attachments,
            "supplierList": [
                {
                    "supplierMemberId": EPAK_INQUIRY_SUPPLIER_MEMBER_ID,
                    "supplierMemberName": EPAK_INQUIRY_SUPPLIER_MEMBER_NAME,
                }
            ],
        }

    @staticmethod
    def build_en_packaging_fields(
        *,
        packaging_type: int | None = None,
        is_pallet: int | None = None,
    ) -> dict[str, Any]:
        """按包装方式 × 是否打托返回线下/线上报价必填包装字段。

        packaging_type: 1纸箱 2卷类 3其他
        is_pallet: 1是 0否（包装方式=其他时固定为否）
        """
        pack = int(
            packaging_type
            if packaging_type is not None
            else CRM_INQUIRY_EN_OFFLINE_PACKAGING_TYPE
        )
        pallet = int(
            is_pallet if is_pallet is not None else CRM_INQUIRY_EN_OFFLINE_IS_PALLET
        )
        if pack == 3:
            pallet = 0

        fields: dict[str, Any] = {
            "packagingType": pack,
            "isPallet": pallet,
        }
        if pallet == 1:
            fields.update(
                {
                    "palletTotalCount": 345,
                    "palletWeightKg": 32.68,
                    "palletVolumeM3": 58.93,
                }
            )

        if pack == 1:
            # 纸箱包装
            fields.update(
                {
                    "boxPcs": 5,
                    "cartonSize": "37*55*45",
                    "cartonSizeLong": 37,
                    "cartonSizeWide": 55,
                    "cartonSizeHigh": 45,
                    "cartonSizeUnit": 2,
                    "cartonWeight": 78.34,
                }
            )
            if pallet == 1:
                fields.update(
                    {
                        "palletBoxs": 31,
                        "gp20Plts": 56,
                        "gp40Plts": 45,
                    }
                )
        elif pack == 2:
            # 卷类包装
            fields.update(
                {
                    "rollWeightKg": 45.34,
                    "rollPackagingMethod": "卷类包装方式111",
                }
            )
            if pallet == 1:
                fields.update(
                    {
                        "totalRolls": 578,
                        "palletRolls": 5,
                        "gp20RollPlts": 45,
                        "gp40RollPlts": 23,
                        "palletTotalCount": 56,
                        "palletWeightKg": 34.23,
                        "palletVolumeM3": 45.98,
                    }
                )
            else:
                # 卷装不打托：直径/卷数需足够大，否则导出 Volume(CBM) 两位小数易为 0
                fields.update(
                    {
                        "totalRolls": 666,
                        "rollDiameterMm": 232.1,
                        "rollHeightMm": 46.89,
                    }
                )
        else:
            # 其他：是否打托固定否
            fields.update(
                {
                    "packagingTypeOther": "包装方式其他",
                    "packageProductQty": 567,
                    "packageVolumeM3": 34523,
                    "packageWeightKg": 2354,
                    "totalPackages": 7891,
                }
            )
        return fields

    @classmethod
    def map_quote_packaging_to_factory_fields(
        cls,
        supplier_quote: dict | None = None,
        *,
        packaging_type: int | None = None,
        is_pallet: int | None = None,
    ) -> dict[str, Any]:
        """将线下/线上报价包装字段映射为 submitFactoryPrice（IqrSubAddFactoryPriceRequest）字段。

        包装方式决定字段集合（与后端英文商城 DTO 对齐）：
        - 纸箱：cartonQtyPerCtn / cartonSize* / cartonGrossWeightKg；打托另加 cartonCtnPerPlt、carton20/40
        - 卷类：rollWeightKg / totalRolls / rollPackingMethod；打托用 rollQtyPerPlt+roll20/40，不打托用直径/高度
        - 其他：packageProductQty / packageVolumeM3 / packageWeightKg / totalPackages（固定不打托）
        """
        quote = supplier_quote or {}
        pack = int(
            packaging_type
            if packaging_type is not None
            else quote.get("packagingType", CRM_INQUIRY_EN_OFFLINE_PACKAGING_TYPE)
        )
        pallet = int(
            is_pallet
            if is_pallet is not None
            else quote.get("isPallet", CRM_INQUIRY_EN_OFFLINE_IS_PALLET)
        )
        if pack == 3:
            pallet = 0
        labels = {1: "纸箱包装", 2: "卷类包装", 3: "其他"}
        fields: dict[str, Any] = {
            "packingMethod": labels.get(pack, "纸箱包装"),
            "isPallet": pallet,
        }
        if pallet == 1:
            fields.update(
                {
                    "palletTotalCount": quote.get("palletTotalCount", 345),
                    "palletWeightKg": quote.get("palletWeightKg", 32.68),
                    "palletVolumeM3": quote.get("palletVolumeM3", 58.93),
                }
            )
        if pack == 1:
            carton_size = str(quote.get("cartonSize", "37*55*45"))
            fields.update(
                {
                    "cartonQtyPerCtn": quote.get("boxPcs", 5),
                    "cartonSizeCm": carton_size,
                    "cartonSizeLong": quote.get("cartonSizeLong", 37),
                    "cartonSizeWide": quote.get("cartonSizeWide", 55),
                    "cartonSizeHigh": quote.get("cartonSizeHigh", 45),
                    "cartonSizeUnit": quote.get("cartonSizeUnit", 2),
                    "cartonGrossWeightKg": quote.get("cartonWeight", 78.34),
                }
            )
            if pallet == 1:
                fields.update(
                    {
                        "cartonCtnPerPlt": quote.get("palletBoxs", 31),
                        "carton20gpPlts": quote.get("gp20Plts", 56),
                        "carton40hqPlts": quote.get("gp40Plts", 45),
                    }
                )
        elif pack == 2:
            fields.update(
                {
                    "rollWeightKg": quote.get("rollWeightKg", 45.34),
                    "totalRolls": quote.get("totalRolls", 578 if pallet == 1 else 666),
                    "rollPackingMethod": quote.get(
                        "rollPackagingMethod", "卷类包装方式111"
                    ),
                }
            )
            if pallet == 1:
                fields.update(
                    {
                        "rollQtyPerPlt": quote.get("palletRolls", 5),
                        "roll20gpPlts": quote.get("gp20RollPlts", 45),
                        "roll40hqPlts": quote.get("gp40RollPlts", 23),
                    }
                )
            else:
                fields.update(
                    {
                        "rollDiameterMm": quote.get("rollDiameterMm", 232.1),
                        "rollHeightMm": quote.get("rollHeightMm", 46.89),
                    }
                )
        else:
            # DTO 无 packingMethodOther；其他包装靠 packingMethod=其他 + package* 字段
            fields.update(
                {
                    "packageProductQty": quote.get("packageProductQty", 567),
                    "packageVolumeM3": quote.get("packageVolumeM3", 34523),
                    "packageWeightKg": quote.get("packageWeightKg", 2354),
                    "totalPackages": quote.get("totalPackages", 7891),
                }
            )
        return fields

    @classmethod
    def build_en_offline_quote_payload(
        cls,
        *,
        sub_id: int | str,
        packaging_type: int | None = None,
        is_pallet: int | None = None,
    ) -> dict[str, Any]:
        expire = (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d")
        packaging = cls.build_en_packaging_fields(
            packaging_type=packaging_type, is_pallet=is_pallet
        )
        supplier: dict[str, Any] = {
            "supplierMemberId": EPAK_INQUIRY_SUPPLIER_MEMBER_ID,
            "supplierMemberName": EPAK_INQUIRY_SUPPLIER_MEMBER_NAME,
            "price": 1344,
            "priceUnit": "元",
            "priceType": 3,
            "serviceFeeRate": 6,
            "mouldFlag": 1,
            "mouldDeliveryDate": 51,
            "mouldSampleFee": 567756,
            "sampleTime": 3,
            "specUnit": 2,
            "specLong": 34,
            "specWide": 23,
            "specHigh": 35,
            "spec": "34*23*35",
            "quoteMaterial": "塑料",
            "moq": 6586878,
            "supplyCycle": 5,
            "addPicture": CRM_INQUIRY_EN_TECH_FILE_URL,
            "supplierRemark": "自动化线下询价备注",
            "contactName": "自动化线下联系人",
            "contactPhone": "19838782733",
            "addSupplierFiles": [
                {
                    "name": CRM_INQUIRY_EN_TECH_FILE_NAME,
                    "url": CRM_INQUIRY_EN_TECH_FILE_URL,
                }
            ],
            "expireDate": expire,
        }
        supplier.update(packaging)
        return {
            "iqrSubId": str(sub_id),
            "sourceMall": 2,
            "supplier": supplier,
        }

    @classmethod
    def build_cn_supplier_quote_payload(
        cls,
        *,
        quote_id: int | str,
        packaging_type: int | None = None,
        is_pallet: int | None = None,
    ) -> dict[str, Any]:
        """供应商线上报价 submitQuote 入参（与线下包装字段同源，含规格拆分）。"""
        expire = (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d")
        packaging = cls.build_en_packaging_fields(
            packaging_type=packaging_type, is_pallet=is_pallet
        )
        stamp = datetime.now().strftime("%m%d%H%M%S")
        payload: dict[str, Any] = {
            "id": int(quote_id),
            "sourceMall": 2,
            "price": 11.23,
            "priceUnit": "元",
            "priceType": 3,
            "spec": "12*23*34",
            "specLong": 12,
            "specWide": 23,
            "specHigh": 34,
            "specUnit": 3,
            "quoteMaterial": "树脂",
            "serviceFeeRate": 6,
            "mouldFlag": 1,
            "mouldDeliveryDate": 5,
            "mouldSampleFee": 6564,
            "sampleTime": 3,
            "moq": 35435,
            "supplyCycle": 4,
            "expireDate": expire,
            "supplierRemark": f"自动化英文备注_{stamp}",
            "contactName": "自动化联系人",
            "contactPhone": "18947837843",
            "addFiles": [
                {
                    "name": CRM_INQUIRY_EN_TECH_FILE_NAME,
                    "url": CRM_INQUIRY_EN_TECH_FILE_URL,
                }
            ],
            "addPicture": CRM_INQUIRY_EN_TECH_FILE_URL,
        }
        # 包装字段随 packaging_type × is_pallet 变化（与线下 save 同源）
        payload.update(packaging)
        return payload

    @classmethod
    def build_en_factory_price_payload(
        cls,
        *,
        sub_id: int | str,
        quote_row: dict | None = None,
        supplier_quote: dict | None = None,
        factory_source: int = 1,
        factory_city: str | None = None,
    ) -> dict[str, Any]:
        quote_row = quote_row or {}
        supplier_quote = supplier_quote or cls.build_cn_supplier_quote_payload(quote_id=0)
        picture = supplier_quote.get("addPicture") or CRM_INQUIRY_EN_TECH_FILE_URL
        files = (
            supplier_quote.get("addSupplierFiles")
            or supplier_quote.get("addFiles")
            or [{"name": CRM_INQUIRY_EN_TECH_FILE_NAME, "url": CRM_INQUIRY_EN_TECH_FILE_URL}]
        )
        picture_name = str(picture).rsplit("/", 1)[-1] if picture else CRM_INQUIRY_EN_TECH_FILE_NAME
        spec_long = supplier_quote.get("specLong")
        spec_wide = supplier_quote.get("specWide")
        spec_high = supplier_quote.get("specHigh")
        if supplier_quote.get("spec"):
            spec = str(supplier_quote["spec"])
        elif all(v is not None for v in (spec_long, spec_wide, spec_high)):
            spec = f"{spec_long}*{spec_wide}*{spec_high}"
        else:
            spec = "12"
        payload: dict[str, Any] = {
            "iqrSubId": str(sub_id),
            "factorySource": factory_source,
            "factorySourceNo": cls.extract_quote_number(quote_row) or "",
            "supplyMemberId": supplier_quote.get(
                "supplierMemberId", EPAK_INQUIRY_SUPPLIER_MEMBER_ID
            ),
            "supplyMemberName": supplier_quote.get(
                "supplierMemberName", EPAK_INQUIRY_SUPPLIER_MEMBER_NAME
            ),
            "factoryUnitPrice": supplier_quote.get("price", 12),
            "serviceFee": supplier_quote.get("serviceFeeRate", 6),
            "priceUnit": supplier_quote.get("priceUnit", "元"),
            "factoryPriceType": "含税不含运",
            "expireDate": supplier_quote.get("expireDate"),
            "factoryDesc": (
                supplier_quote.get("supplierRemark")
                or supplier_quote.get("remark")
                or cls.en_factory_desc_from_packaging(
                    packaging_type=cls._to_int(supplier_quote.get("packagingType")),
                    is_pallet=cls._to_int(supplier_quote.get("isPallet")),
                    fallback="自动化出厂报价",
                )
            ),
            "moq": supplier_quote.get("moq", 12999),
            "spec": spec,
            "specLong": spec_long,
            "specWide": spec_wide,
            "specHigh": spec_high,
            "specUnit": supplier_quote.get("specUnit", 1),
            "quoteMaterial": supplier_quote.get("quoteMaterial", "树脂"),
            "deliveryCycle": supplier_quote.get("supplyCycle", 12),
            "moldExists": "有" if supplier_quote.get("mouldFlag", 1) == 1 else "无",
            "moldDeliveryDays": supplier_quote.get("mouldDeliveryDate", 2),
            "singleMoldSampleFee": supplier_quote.get("mouldSampleFee", 1890),
            "sampleDays": supplier_quote.get("sampleTime", 3),
            "factoryCity": factory_city or CRM_INQUIRY_EN_FACTORY_CITY,
            "pictureFiles": [{"name": picture_name, "url": picture}],
            "factoryFiles": files,
            "compareFiles": [
                {
                    "name": CRM_INQUIRY_EN_TECH_FILE_NAME,
                    "url": CRM_INQUIRY_EN_TECH_FILE_URL,
                }
            ]
            if CRM_INQUIRY_EN_TECH_FILE_URL
            else [],
            "comparePriceRemark": CRM_INQUIRY_EN_COMPARE_PRICE_REMARK,
        }
        # 把采纳报价的包装字段原样映射到出厂报价（卷装打托含 rollWeightKg/pallet* 等）
        payload.update(cls.map_quote_packaging_to_factory_fields(supplier_quote))
        return payload

    @staticmethod
    def en_factory_edit_referer(
        *,
        sub_id: int | str,
        ask_price_type: InquiryAskPriceType | int | str = InquiryAskPriceType.GENERAL,
        status: int = InquiryStatus.PENDING_FACTORY_QUOTE.code,
        route: InquiryCreateRoute | None = None,
    ) -> str:
        ask = parse_ask_price_type(ask_price_type)
        mall_q = (
            "&mallType=2"
            if route is not None and route.operate_via == InquiryOperateVia.CN
            else ""
        )
        return (
            "/memberCenter/transactionAbility/inquiryOffer/internalInquiry/edit"
            f"?id={sub_id}&formStatus=3{mall_q}&inquirySteps=3"
            f"&askPriceType={ask.code}&status={status}"
        )

    def find_supplier_quote_row(
        self,
        purchaser_ctx: AuthContext,
        supplier_ctx: AuthContext | None,
        sub_id: int | str,
        *,
        route: InquiryCreateRoute,
        push_body: dict | None = None,
        referer_path: str,
    ) -> dict | None:
        quote_id = self.extract_push_quote_id(push_body or {})
        if quote_id is not None:
            row = {"id": quote_id}
        else:
            row = {}
        for ctx, url, origin, ref in (
            (purchaser_ctx, self.en_operation_urls(route).supplier_query, None, referer_path),
            (
                supplier_ctx,
                CRM_INQUIRY_CN_SUPPLIER_QUERY_API_URL,
                CRM_INQUIRY_SUPPLIER_PLATFORM_BASE_URL,
                "/memberCenter/transactionAbility/supplierGiqrInquiry/list",
            ),
        ):
            if ctx is None or not url:
                continue
            try:
                body = self._json_post(
                    ctx,
                    url,
                    {"iqrSubId": str(sub_id), "current": 1, "pageSize": 20},
                    route=route,
                    referer_path=ref,
                    origin=origin,
                )
            except Exception:
                continue
            rows = self.extract_rows(body)
            if not rows and isinstance(body.get("data"), list):
                rows = [item for item in body["data"] if isinstance(item, dict)]
            if quote_id is not None:
                for item in rows:
                    if self._to_int(item.get("id") or item.get("iqrSupplierId")) == quote_id:
                        return item
            if rows:
                picked = rows[0]
                if quote_id is not None:
                    picked.setdefault("id", quote_id)
                return picked
        return row or None

    def fetch_supplier_records_by_sub(
        self,
        ctx: AuthContext,
        sub_id: int | str,
        *,
        route: InquiryCreateRoute,
        referer_path: str,
    ) -> dict[str, Any]:
        body = self._json_post(
            ctx,
            self.en_operation_urls(route).records_by_sub,
            {"id": str(sub_id)},
            route=route,
            referer_path=referer_path,
        )
        self.assert_success(body, "查询子单报价记录")
        data = body.get("data")
        if not isinstance(data, dict):
            return {"giqrRecordList": [], "offlineQuoteRecordList": [], "raw": body}
        return {
            "giqrRecordList": [
                item for item in (data.get("giqrRecordList") or []) if isinstance(item, dict)
            ],
            "offlineQuoteRecordList": [
                item
                for item in (data.get("offlineQuoteRecordList") or [])
                if isinstance(item, dict)
            ],
            "raw": body,
        }

    @staticmethod
    def pick_quote_record(
        rows: list[dict],
        *,
        quote_id: int | None = None,
        prefer_adopted: bool = True,
    ) -> dict | None:
        if not rows:
            return None
        if quote_id is not None:
            for item in rows:
                if CrmInquiryService._to_int(item.get("id")) == quote_id:
                    return item
        if prefer_adopted:
            for item in rows:
                if item.get("isAdopted") in (1, True, "1"):
                    return item
        return rows[-1]

    @classmethod
    def normalize_quote_record_for_factory(cls, record: dict | None) -> dict[str, Any]:
        """把 recordsBySub 报价行转成 submitFactoryPrice 可用的 supplier_quote。"""
        row = dict(record or {})
        if not row.get("spec") and all(
            row.get(k) is not None for k in ("specLong", "specWide", "specHigh")
        ):
            row["spec"] = f"{row['specLong']}*{row['specWide']}*{row['specHigh']}"
        if row.get("price") is not None:
            try:
                row["price"] = float(row["price"])
            except (TypeError, ValueError):
                pass
        if not row.get("supplierRemark") and row.get("remark"):
            row["supplierRemark"] = row["remark"]
        return row

    def submit_factory_quote(
        self,
        ctx: AuthContext,
        *,
        payload: dict | None = None,
        main_id: int | None = None,
        sub_id: int | None = None,
        snapshot: dict | None = None,
        transition: InquiryTransition | None = None,
        source: InquiryCreateSource | str | None = None,
        route: InquiryCreateRoute | None = None,
        ask_price_type: InquiryAskPriceType | int | str | None = None,
        role_auths: dict[str, AuthContext] | None = None,
        sub_spec: InquirySubSpec | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        del payload
        route = route or self.resolve_route(source=source)
        step = transition or self._transition_by_handler("submit_factory_quote")
        if route.mall != InquiryMall.EN:
            raise InquiryTransitionNotWired(
                step,
                ask_price_type=ask_price_type,
                source=source or route.source,
            )
        resolved_sub_id = sub_id or (snapshot or {}).get("sub_id")
        if resolved_sub_id is None:
            raise AssertionError("提交出厂报价缺少 iqrSubId")
        ask = parse_ask_price_type(ask_price_type or InquiryAskPriceType.GENERAL)
        packaging_type = self.parse_packaging_type(
            None if sub_spec is None else sub_spec.packaging_type
        )
        is_pallet = self.parse_is_pallet(None if sub_spec is None else sub_spec.is_pallet)
        channels = self.parse_en_quote_channels(
            None if sub_spec is None else sub_spec.quote_channels
        )
        adopt_source = self.resolve_en_factory_adopt_source(
            channels,
            value=None if sub_spec is None else sub_spec.adopt_source,
        )
        roles = dict(role_auths or {})
        supplier_ctx = roles.get("supplier")
        referer_path = self.en_factory_edit_referer(
            sub_id=resolved_sub_id, ask_price_type=ask, route=route
        )
        urls = self.en_operation_urls(route)
        inner_steps: list[dict[str, Any]] = []
        quote_row: dict | None = None
        supplier_quote: dict | None = None
        offline_payload: dict | None = None
        offline_quote_row: dict | None = None

        if "online" in channels:
            push_payload = self.build_en_push_supplier_payload(
                sub_id=resolved_sub_id,
                remark=(snapshot or {}).get("remark") or None,
            )
            push_resp = self._json_post(
                ctx,
                urls.push_supplier,
                push_payload,
                route=route,
                referer_path=referer_path,
            )
            self.assert_success(push_resp, "推送供应商")
            inner_steps.append({"step": "push_supplier", "request": push_payload, "response": push_resp})
            quote_row = self.find_supplier_quote_row(
                ctx,
                supplier_ctx,
                resolved_sub_id,
                route=route,
                push_body=push_resp,
                referer_path=referer_path,
            )
            if quote_row is None or self._to_int(quote_row.get("id")) is None:
                raise AssertionError(f"推送供应商后未拿到线上询价单 id: {push_resp}")

        if "offline" in channels:
            offline_payload = self.build_en_offline_quote_payload(
                sub_id=resolved_sub_id,
                packaging_type=packaging_type,
                is_pallet=is_pallet,
            )
            offline_resp = self._json_post(
                ctx,
                urls.offline_quote,
                offline_payload,
                route=route,
                referer_path=referer_path,
            )
            self.assert_success(offline_resp, "保存线下报价")
            inner_steps.append(
                {"step": "save_offline_quote", "request": offline_payload, "response": offline_resp}
            )
            records = self.fetch_supplier_records_by_sub(
                ctx,
                resolved_sub_id,
                route=route,
                referer_path=referer_path,
            )
            inner_steps.append(
                {
                    "step": "records_by_sub_after_offline_save",
                    "request": {"id": str(resolved_sub_id)},
                    "response": records.get("raw"),
                }
            )
            offline_quote_row = self.pick_quote_record(
                records["offlineQuoteRecordList"],
                quote_id=self.extract_push_quote_id(offline_resp),
                prefer_adopted=False,
            )
            if offline_quote_row is None:
                raise AssertionError(
                    f"保存线下报价后 recordsBySub 未返回线下记录: {records.get('raw')}"
                )
            off_no = self.extract_quote_number(offline_quote_row)
            if not off_no:
                main_number = (snapshot or {}).get("main_number") or (
                    ((snapshot or {}).get("row") or {}).get("iqrMainNumber")
                )
                off_no = self.build_en_offline_factory_source_no(
                    main_number=main_number,
                    main_id=main_id,
                    quote_index=len(records["offlineQuoteRecordList"]),
                )
            offline_quote_row = {
                **offline_quote_row,
                "offNo": off_no,
                "offlineNumber": offline_quote_row.get("offlineNumber") or off_no,
                "factorySourceNo": off_no,
            }

        if "online" in channels:
            if supplier_ctx is None:
                raise InquiryRoleMissing("supplier", step)
            quote_id = self._to_int((quote_row or {}).get("id"))
            online_quote = self.build_cn_supplier_quote_payload(
                quote_id=quote_id or 0,
                packaging_type=packaging_type,
                is_pallet=is_pallet,
            )
            cn_referer = (
                "/memberCenter/transactionAbility/supplierGiqrInquiry/detail"
                f"?id={quote_id}"
            )
            quote_resp = self._json_post(
                supplier_ctx,
                CRM_INQUIRY_CN_SUPPLIER_QUOTE_API_URL,
                online_quote,
                route=route,
                referer_path=cn_referer,
                origin=CRM_INQUIRY_SUPPLIER_PLATFORM_BASE_URL,
            )
            self.assert_success(quote_resp, "供应商提交线上报价")
            inner_steps.append(
                {"step": "supplier_submit_quote", "request": online_quote, "response": quote_resp}
            )
            if adopt_source == "online":
                adopt_payload = {"id": quote_id}
                adopt_resp = self._json_post(
                    ctx,
                    urls.adopt_quote,
                    adopt_payload,
                    route=route,
                    referer_path=referer_path,
                )
                self.assert_success(adopt_resp, "采纳线上报价")
                inner_steps.append(
                    {"step": "adopt_online_quote", "request": adopt_payload, "response": adopt_resp}
                )
                records = self.fetch_supplier_records_by_sub(
                    ctx,
                    resolved_sub_id,
                    route=route,
                    referer_path=referer_path,
                )
                inner_steps.append(
                    {
                        "step": "records_by_sub_after_online_adopt",
                        "request": {"id": str(resolved_sub_id)},
                        "response": records.get("raw"),
                    }
                )
                adopted = self.pick_quote_record(
                    records["giqrRecordList"], quote_id=quote_id, prefer_adopted=True
                )
                if adopted is None:
                    raise AssertionError(
                        f"采纳线上报价后 recordsBySub 未返回 GIQR 记录: {records.get('raw')}"
                    )
                quote_row = {
                    **adopted,
                    "id": quote_id,
                    "giqrNo": self.extract_quote_number(adopted) or "",
                    "factorySourceNo": self.extract_quote_number(adopted) or "",
                }
                supplier_quote = self.normalize_quote_record_for_factory(adopted)
                supplier_quote = {**online_quote, **supplier_quote}
                factory_source = 1

        if adopt_source == "offline":
            factory_source = 2
            if offline_quote_row is None:
                raise AssertionError("出厂采纳线下报价但未保存线下报价")
            offline_id = self._to_int(offline_quote_row.get("id"))
            if offline_id is None:
                raise AssertionError(f"线下报价缺少 id，无法采纳: {offline_quote_row}")
            adopt_payload = {"id": offline_id}
            adopt_resp = self._json_post(
                ctx,
                urls.offline_adopt,
                adopt_payload,
                route=route,
                referer_path=referer_path,
            )
            self.assert_success(adopt_resp, "采纳线下报价")
            inner_steps.append(
                {"step": "adopt_offline_quote", "request": adopt_payload, "response": adopt_resp}
            )
            records = self.fetch_supplier_records_by_sub(
                ctx,
                resolved_sub_id,
                route=route,
                referer_path=referer_path,
            )
            inner_steps.append(
                {
                    "step": "records_by_sub_after_offline_adopt",
                    "request": {"id": str(resolved_sub_id)},
                    "response": records.get("raw"),
                }
            )
            adopted = self.pick_quote_record(
                records["offlineQuoteRecordList"],
                quote_id=offline_id,
                prefer_adopted=True,
            )
            if adopted is None:
                raise AssertionError(
                    f"采纳线下报价后 recordsBySub 未返回线下记录: {records.get('raw')}"
                )
            off_no = self.extract_quote_number(adopted) or self.extract_quote_number(
                offline_quote_row
            )
            if not off_no:
                main_number = (snapshot or {}).get("main_number") or (
                    ((snapshot or {}).get("row") or {}).get("iqrMainNumber")
                )
                off_no = self.build_en_offline_factory_source_no(
                    main_number=main_number,
                    main_id=main_id,
                    quote_index=1,
                )
            quote_row = {
                **adopted,
                "id": offline_id,
                "offNo": off_no,
                "offlineNumber": adopted.get("offlineNumber") or off_no,
                "factorySourceNo": off_no,
            }
            supplier_quote = self.normalize_quote_record_for_factory(adopted)
            if offline_payload and isinstance(offline_payload.get("supplier"), dict):
                supplier_quote = {**offline_payload["supplier"], **supplier_quote}

        if supplier_quote is None:
            raise AssertionError(
                f"出厂报价缺少采纳数据: adopt_source={adopt_source}, channels={sorted(channels)}"
            )

        factory_payload = self.build_en_factory_price_payload(
            sub_id=resolved_sub_id,
            quote_row=quote_row,
            supplier_quote=supplier_quote,
            factory_source=factory_source,
        )
        if factory_source == 1 and not factory_payload.get("factorySourceNo"):
            raise AssertionError(f"采纳后未拿到线上询价单号: {quote_row}")
        if factory_source == 2 and not factory_payload.get("factorySourceNo"):
            raise AssertionError(f"线下报价后未拿到线下询价单号: {quote_row}")
        required_pack = ("packingMethod", "isPallet")
        missing_pack = [k for k in required_pack if factory_payload.get(k) is None]
        if missing_pack:
            raise AssertionError(
                f"出厂报价缺少采纳包装字段 {missing_pack}: {factory_payload}"
            )
        factory_resp = self._json_post(
            ctx,
            urls.submit_factory,
            factory_payload,
            route=route,
            referer_path=referer_path,
        )
        self.assert_success(factory_resp, "提交出厂报价")
        inner_steps.append(
            {"step": "submit_factory_price", "request": factory_payload, "response": factory_resp}
        )
        return {
            "step": "submit_factory_quote",
            "main_id": main_id,
            "sub_id": int(resolved_sub_id),
            "channels": sorted(channels),
            "adopt_source": adopt_source,
            "factory_source": factory_source,
            "packaging_type": packaging_type
            if packaging_type is not None
            else CRM_INQUIRY_EN_OFFLINE_PACKAGING_TYPE,
            "is_pallet": is_pallet
            if is_pallet is not None
            else CRM_INQUIRY_EN_OFFLINE_IS_PALLET,
            "quote_id": (quote_row or {}).get("id") if quote_row else None,
            "factory_source_no": factory_payload.get("factorySourceNo"),
            "steps": inner_steps,
            "response": factory_resp,
        }

    @classmethod
    def build_en_platform_price_payload(
        cls,
        *,
        sub_id: int | str,
        platform_unit_price: float | None = None,
        platform_price_type: str | None = None,
        platform_desc: str | None = None,
        logistics_files: list[dict] | None = None,
    ) -> dict[str, Any]:
        files = logistics_files
        if files is None and CRM_INQUIRY_EN_TECH_FILE_URL:
            files = [
                {
                    "name": CRM_INQUIRY_EN_TECH_FILE_NAME,
                    "url": CRM_INQUIRY_EN_TECH_FILE_URL,
                }
            ]
        return {
            "iqrSubId": str(sub_id),
            "platformPriceType": platform_price_type or CRM_INQUIRY_EN_PLATFORM_PRICE_TYPE,
            "platformDesc": platform_desc or CRM_INQUIRY_EN_PLATFORM_DESC,
            "logisticsFiles": files or [],
            "platformUnitPrice": (
                CRM_INQUIRY_EN_PLATFORM_UNIT_PRICE
                if platform_unit_price is None
                else platform_unit_price
            ),
        }

    @staticmethod
    def en_platform_edit_referer(
        *,
        sub_id: int | str,
        ask_price_type: InquiryAskPriceType | int | str = InquiryAskPriceType.GENERAL,
        status: int = InquiryStatus.PENDING_PLATFORM_QUOTE.code,
        route: InquiryCreateRoute | None = None,
    ) -> str:
        ask = parse_ask_price_type(ask_price_type)
        mall_q = (
            "&mallType=2"
            if route is not None and route.operate_via == InquiryOperateVia.CN
            else ""
        )
        return (
            "/memberCenter/transactionAbility/inquiryOffer/internalInquiry/edit"
            f"?id={sub_id}&formStatus=1{mall_q}&inquirySteps=4"
            f"&askPriceType={ask.code}&status={status}"
        )

    @staticmethod
    def build_en_confirm_price_payload(
        *,
        sub_id: int | str,
        is_launch: int = 1,
    ) -> dict[str, Any]:
        return {
            "iqrSubId": str(sub_id),
            "isLaunch": is_launch,
        }

    @staticmethod
    def en_listing_edit_referer(
        *,
        sub_id: int | str,
        ask_price_type: InquiryAskPriceType | int | str = InquiryAskPriceType.GENERAL,
        status: int = InquiryStatus.PENDING_LISTING.code,
        route: InquiryCreateRoute | None = None,
    ) -> str:
        ask = parse_ask_price_type(ask_price_type)
        mall_q = (
            "&mallType=2"
            if route is not None and route.operate_via == InquiryOperateVia.CN
            else ""
        )
        return (
            "/memberCenter/transactionAbility/inquiryOffer/internalInquiry/edit"
            f"?id={sub_id}&formStatus=3{mall_q}&inquirySteps=5"
            f"&askPriceType={ask.code}&status={status}"
        )

    def submit_platform_quote(
        self,
        ctx: AuthContext,
        *,
        payload: dict | None = None,
        main_id: int | None = None,
        sub_id: int | None = None,
        snapshot: dict | None = None,
        transition: InquiryTransition | None = None,
        source: InquiryCreateSource | str | None = None,
        route: InquiryCreateRoute | None = None,
        ask_price_type: InquiryAskPriceType | int | str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        """业务支撑提交平台报价（英文商城：张四，独立登录 token）。"""
        del payload
        route = route or self.resolve_route(source=source)
        step = transition or self._transition_by_handler("submit_platform_quote")
        if route.mall != InquiryMall.EN:
            raise InquiryTransitionNotWired(
                step,
                ask_price_type=ask_price_type,
                source=source or route.source,
            )
        resolved_sub_id = sub_id or (snapshot or {}).get("sub_id")
        if resolved_sub_id is None:
            raise AssertionError("提交平台报价缺少 iqrSubId")
        ask = parse_ask_price_type(ask_price_type or InquiryAskPriceType.GENERAL)
        body_payload = self.build_en_platform_price_payload(sub_id=resolved_sub_id)
        referer_path = self.en_platform_edit_referer(
            sub_id=resolved_sub_id, ask_price_type=ask, route=route
        )
        body = self._json_post(
            ctx,
            self.en_operation_urls(route).submit_platform,
            body_payload,
            route=route,
            referer_path=referer_path,
        )
        self.assert_success(body, "提交平台报价")
        return {
            "step": "submit_platform_quote",
            "main_id": main_id,
            "sub_id": int(resolved_sub_id),
            "request": body_payload,
            "response": body,
        }

    def apply_listing(
        self,
        ctx: AuthContext,
        *,
        payload: dict | None = None,
        main_id: int | None = None,
        sub_id: int | None = None,
        snapshot: dict | None = None,
        transition: InquiryTransition | None = None,
        source: InquiryCreateSource | str | None = None,
        route: InquiryCreateRoute | None = None,
        ask_price_type: InquiryAskPriceType | int | str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        del payload
        route = route or self.resolve_route(source=source)
        step = transition or self._transition_by_handler("apply_listing")
        if route.mall != InquiryMall.EN:
            raise InquiryTransitionNotWired(
                step,
                ask_price_type=ask_price_type,
                source=source or route.source,
            )
        resolved_sub_id = sub_id or (snapshot or {}).get("sub_id")
        if resolved_sub_id is None:
            raise AssertionError("发起上架申请缺少 iqrSubId")
        ask = parse_ask_price_type(ask_price_type or InquiryAskPriceType.GENERAL)
        body_payload = self.build_en_confirm_price_payload(sub_id=resolved_sub_id)
        referer_path = self.en_listing_edit_referer(
            sub_id=resolved_sub_id, ask_price_type=ask, route=route
        )
        body = self._json_post(
            ctx,
            self.en_operation_urls(route).confirm_price,
            body_payload,
            route=route,
            referer_path=referer_path,
        )
        self.assert_success(body, "发起上架申请")
        return {
            "step": "apply_listing",
            "main_id": main_id,
            "sub_id": int(resolved_sub_id),
            "request": body_payload,
            "response": body,
        }

    @staticmethod
    def build_en_relation_product_payload(
        *,
        sub_id: int | str,
        sku_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        return {
            "iqrSubId": int(sub_id),
            "skuId": list(sku_ids or CRM_INQUIRY_EN_RELATION_SKU_IDS),
        }

    @staticmethod
    def build_en_submit_custom_order_payload(*, sub_id: int | str) -> dict[str, Any]:
        return {"id": str(sub_id)}

    @staticmethod
    def en_transfer_order_referer(*, sub_id: int | str) -> str:
        return f"/memberCenter/orderAbility/saleOrder/agentOrder?iqrSubId={sub_id}"

    @classmethod
    def resolve_sub_quantity(
        cls,
        snapshot: dict | None,
        *,
        ask_price_type: InquiryAskPriceType | int | str | None = None,
        quantity: int | None = None,
    ) -> int:
        if quantity is not None:
            return int(quantity)
        sub = (snapshot or {}).get("sub") or {}
        resolved = cls._to_int(sub.get("qty"))
        if resolved:
            return resolved
        ask = parse_ask_price_type(ask_price_type or InquiryAskPriceType.GENERAL)
        return 1999 if ask == InquiryAskPriceType.GENERAL else 1890

    def build_en_transfer_order_payload(
        self,
        ctx: AuthContext,
        *,
        sub_id: int | str,
        snapshot: dict | None = None,
        ask_price_type: InquiryAskPriceType | int | str | None = None,
        sku_ids: list[int] | None = None,
        quantity: int | None = None,
        unit_price: float | None = None,
    ) -> dict[str, Any]:
        sku_id = int((sku_ids or CRM_INQUIRY_EN_RELATION_SKU_IDS)[0])
        qty = self.resolve_sub_quantity(
            snapshot,
            ask_price_type=ask_price_type,
            quantity=quantity,
        )
        referer_path = self.en_transfer_order_referer(sub_id=sub_id)
        order_svc = OrderService(self.client)
        payload = order_svc.build_agent_order_payload(
            ctx,
            buyer_member_id=CRM_INQUIRY_EN_BUYER_MEMBER_ID,
            buyer_member_name=CRM_INQUIRY_EN_BUYER_MEMBER_NAME,
            buyer_user_id=CRM_INQUIRY_EN_BUYER_USER_ID,
            buyer_user_name=CRM_INQUIRY_EN_BUYER_USER_NAME,
            buyer_role_id=ORDER_BUYER_ROLE_ID,
            items=[
                OrderLineItem(
                    sku_id=sku_id,
                    quantity=qty,
                    unit_price=unit_price,
                )
            ],
            commodity_api_url=EPAK_COMMODITY_GUEST_LIST_API_URL,
            address_api_url=EPAK_RECEIVER_ADDRESS_AGENT_PAGE_API_URL,
            referer_path=referer_path,
            platform_base_url=EPAK_PLATFORM_BASE_URL,
        )
        payload["iqrSubId"] = int(sub_id)
        payload["currencyId"] = CRM_INQUIRY_EN_ORDER_CURRENCY_ID
        payload["tradeMode"] = CRM_INQUIRY_EN_ORDER_TRADE_MODE
        payload["shopName"] = CRM_INQUIRY_EN_ORDER_SHOP_NAME
        payload["shopClassify"] = CRM_INQUIRY_EN_ORDER_SHOP_CLASSIFY
        payload["buyerSaleOrgType"] = CRM_INQUIRY_BUYER_SALE_ORG_TYPE
        pay_node = "合同签署后"
        for payment in payload.get("payments") or []:
            payment["payNode"] = pay_node
            for channel in payment.get("payChannels") or []:
                for node in channel.get("payNodes") or []:
                    node["payNode"] = pay_node
            for node in payment.get("payNodes") or []:
                node["payNode"] = pay_node
        pay_message = payload.get("payTypeMessageObj") or {}
        for key in ("payType", "payChannel"):
            section = pay_message.get(key) or {}
            for channel in section.get("payChannels") or []:
                for node in channel.get("payNodes") or []:
                    node["payNode"] = pay_node
        payload["payTypeMessageObj"] = pay_message
        payload["vendorMemberId"] = ctx.member_id
        for product in payload.get("products") or []:
            product["buyerMemberId"] = str(CRM_INQUIRY_EN_BUYER_MEMBER_ID)
            product["buyerRoleId"] = str(ORDER_BUYER_ROLE_ID)
        return payload

    @staticmethod
    def en_associate_edit_referer(
        *,
        sub_id: int | str,
        ask_price_type: InquiryAskPriceType | int | str = InquiryAskPriceType.GENERAL,
        status: int = InquiryStatus.PENDING_ASSOCIATE_PRODUCT.code,
        route: InquiryCreateRoute | None = None,
    ) -> str:
        ask = parse_ask_price_type(ask_price_type)
        mall_q = (
            "&mallType=2"
            if route is not None and route.operate_via == InquiryOperateVia.CN
            else ""
        )
        return (
            "/memberCenter/transactionAbility/inquiryOffer/internalInquiry/edit"
            f"?id={sub_id}&formStatus=3{mall_q}&inquirySteps=6"
            f"&askPriceType={ask.code}&status={status}"
        )

    def associate_product(
        self,
        ctx: AuthContext,
        *,
        payload: dict | None = None,
        main_id: int | None = None,
        sub_id: int | None = None,
        snapshot: dict | None = None,
        transition: InquiryTransition | None = None,
        source: InquiryCreateSource | str | None = None,
        route: InquiryCreateRoute | None = None,
        ask_price_type: InquiryAskPriceType | int | str | None = None,
        sku_ids: list[int] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        """业务支撑关联商品：relationProduct 后 submitCustomOrder。"""
        del payload
        route = route or self.resolve_route(source=source)
        step = transition or self._transition_by_handler("associate_product")
        if route.mall != InquiryMall.EN:
            raise InquiryTransitionNotWired(
                step,
                ask_price_type=ask_price_type,
                source=source or route.source,
            )
        resolved_sub_id = sub_id or (snapshot or {}).get("sub_id")
        if resolved_sub_id is None:
            raise AssertionError("关联商品缺少 iqrSubId")
        ask = parse_ask_price_type(ask_price_type or InquiryAskPriceType.GENERAL)
        referer_path = self.en_associate_edit_referer(
            sub_id=resolved_sub_id, ask_price_type=ask, route=route
        )
        relation_payload = self.build_en_relation_product_payload(
            sub_id=resolved_sub_id, sku_ids=sku_ids
        )
        urls = self.en_operation_urls(route)
        relation_resp = self._json_post(
            ctx,
            urls.relation_product,
            relation_payload,
            route=route,
            referer_path=referer_path,
        )
        self.assert_success(relation_resp, "关联商品")
        submit_payload = self.build_en_submit_custom_order_payload(sub_id=resolved_sub_id)
        submit_resp = self._json_post(
            ctx,
            urls.submit_custom_order,
            submit_payload,
            route=route,
            referer_path=referer_path,
        )
        self.assert_success(submit_resp, "提交关联商品")
        return {
            "step": "associate_product",
            "main_id": main_id,
            "sub_id": int(resolved_sub_id),
            "request": {
                "relationProduct": relation_payload,
                "submitCustomOrder": submit_payload,
            },
            "response": {
                "relationProduct": relation_resp,
                "submitCustomOrder": submit_resp,
            },
        }

    def transfer_to_order(
        self,
        ctx: AuthContext,
        *,
        payload: dict | None = None,
        main_id: int | None = None,
        sub_id: int | None = None,
        snapshot: dict | None = None,
        transition: InquiryTransition | None = None,
        source: InquiryCreateSource | str | None = None,
        route: InquiryCreateRoute | None = None,
        ask_price_type: InquiryAskPriceType | int | str | None = None,
        sku_ids: list[int] | None = None,
        quantity: int | None = None,
        unit_price: float | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        """业务支撑转单：英文商城代客创建销售订单。"""
        del payload
        route = route or self.resolve_route(source=source)
        step = transition or self._transition_by_handler("transfer_to_order")
        if route.mall != InquiryMall.EN:
            raise InquiryTransitionNotWired(
                step,
                ask_price_type=ask_price_type,
                source=source or route.source,
            )
        if route.operate_via == InquiryOperateVia.CN:
            raise InquiryTransitionNotWired(
                step,
                ask_price_type=ask_price_type,
                source=source or route.source,
                message=cn_operate_transfer_blocked_message(),
            )
        resolved_sub_id = sub_id or (snapshot or {}).get("sub_id")
        if resolved_sub_id is None:
            raise AssertionError("转单缺少 iqrSubId")
        ask = parse_ask_price_type(ask_price_type or InquiryAskPriceType.GENERAL)
        order_payload = self.build_en_transfer_order_payload(
            ctx,
            sub_id=resolved_sub_id,
            snapshot=snapshot,
            ask_price_type=ask,
            sku_ids=sku_ids,
            quantity=quantity,
            unit_price=unit_price,
        )
        referer_path = self.en_transfer_order_referer(sub_id=resolved_sub_id)
        order_svc = OrderService(self.client)
        body = order_svc.create_agent_order(
            ctx,
            order_payload,
            api_url=EPAK_ORDER_AGENT_CREATE_API_URL,
            referer_path=referer_path,
            platform_base_url=EPAK_PLATFORM_BASE_URL,
        )
        self.assert_success(body, "创建销售订单")
        return {
            "step": "transfer_to_order",
            "main_id": main_id,
            "sub_id": int(resolved_sub_id),
            "request": order_payload,
            "response": body,
        }

    def close_inquiry(self, *args: Any, **kwargs: Any) -> dict:
        raise InquiryTransitionNotWired(
            self._transition_by_handler("close_inquiry"),
            ask_price_type=kwargs.get("ask_price_type"),
            source=kwargs.get("source"),
        )

    def save_pending_submit(self, *args: Any, **kwargs: Any) -> dict:
        raise InquiryTransitionNotWired(
            self._transition_by_handler("save_pending_submit"),
            ask_price_type=kwargs.get("ask_price_type"),
            source=kwargs.get("source"),
        )

    @staticmethod
    def _transition_by_handler(handler: str) -> InquiryTransition:
        for step in (*CUSTOM_PIPELINE, *GENERAL_PIPELINE, *BRANCH_TRANSITIONS):
            if step.handler == handler:
                return step
        raise KeyError(handler)
