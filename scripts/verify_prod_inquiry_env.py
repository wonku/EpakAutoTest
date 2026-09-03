"""生产环境上线前预检：全套配置核对 + 域名/接口可达 + 登录/只读查询。

不会创建询价单、不会改状态、不会下单。
上线当晚全套造数请用:
  python scripts/create_inquiry.py --env prod --allow-prod-seed ...

用法:
  Copy-Item .env.en.prod.example .env.en.prod   # 按全套流程填齐参数
  python scripts/verify_prod_inquiry_env.py --env prod
  python scripts/verify_prod_inquiry_env.py --env prod --operate-via both
  python scripts/verify_prod_inquiry_env.py --env prod --dump-urls-only

预检会调用（只读）:
  - POST /api/member/login（en / cn / supplier）
  - POST pageList（询价列表，不创建）
  - POST getCommodityListByGuest（商品）
  - GET  receiverAddress/agent/page（地址，可选）
  - HTTPS 探测各 origin / 写接口 URL 是否可达（不提交业务写操作）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.env_loader import bootstrap_env, describe_env_files, peek_cli_env

_ACTIVE_ENV = bootstrap_env(peek_cli_env())

from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.auth_service import AuthService
from api.services.crm_inquiry_service import CrmInquiryService
from api.services.crm_inquiry_status import (
    InquiryCreateSource,
    InquiryForm,
    InquiryMall,
    InquiryOperateVia,
    parse_operate_via,
)
from api.services.order_service import OrderService
from config.settings import (
    API_TIMEOUT_SECONDS,
    AUTH_API_URL,
    CRM_INQUIRY_CN_SUPPLIER_QUOTE_API_URL,
    CRM_INQUIRY_CN_SUPPLIER_QUERY_API_URL,
    CRM_INQUIRY_EN_BUYER_MEMBER_ID,
    CRM_INQUIRY_EN_BUYER_MEMBER_NAME,
    CRM_INQUIRY_EN_BUYER_USER_ID,
    CRM_INQUIRY_EN_CATEGORY_FULL_ID,
    CRM_INQUIRY_EN_COMPARE_PRICE_REMARK,
    CRM_INQUIRY_EN_FACTORY_CITY,
    CRM_INQUIRY_EN_RELATION_SKU_IDS,
    CRM_INQUIRY_EN_TECH_FILE_URL,
    CRM_INQUIRY_SUPPLIER_ACCOUNT,
    CRM_INQUIRY_SUPPLIER_AUTH_API_URL,
    CRM_INQUIRY_SUPPLIER_AUTH_ORIGIN,
    CRM_INQUIRY_SUPPLIER_PASSWORD_ENCRYPTED,
    CRM_INQUIRY_SUPPLIER_PLATFORM_BASE_URL,
    EPAK_COMMODITY_GUEST_LIST_API_URL,
    EPAK_ENV,
    EPAK_INQUIRY_PURCHASER_ACCOUNT,
    EPAK_INQUIRY_SUPPORT_ACCOUNT,
    EPAK_INQUIRY_SUPPLIER_MEMBER_ID,
    EPAK_INQUIRY_TECH_ACCOUNT,
    EPAK_LOGIN_PASSWORD_ENCRYPTED,
    EPAK_LOGIN_PHONE,
    EPAK_ORDER_AGENT_CREATE_API_URL,
    EPAK_PLATFORM_AUTH_API_URL,
    EPAK_PLATFORM_AUTH_ORIGIN,
    EPAK_PLATFORM_BASE_URL,
    EPAK_RECEIVER_ADDRESS_AGENT_PAGE_API_URL,
    ORDER_BUYER_ROLE_ID,
    PLATFORM_BASE_URL,
)


# 写接口：只做 HTTPS 可达探测，绝不 POST 业务 body
_WRITE_STEP_KEYS = (
    "submit",
    "submit_tech",
    "push_supplier",
    "offline_quote",
    "offline_adopt",
    "adopt_quote",
    "submit_factory",
    "submit_platform",
    "confirm_price",
    "relation_product",
    "submit_custom_order",
    "supplier_quote",
    "transfer_order",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="生产全套配置预检：域名/接口可达 + 登录/只读，不造数"
    )
    p.add_argument("--env", choices=["test", "uat", "prod"], default=None)
    p.add_argument(
        "--operate-via",
        default="en",
        help="en=默认英文站角色登录；cn=中文站；both=两边都验（供应商始终走 esbao）",
    )
    p.add_argument("--skip-commodity", action="store_true")
    p.add_argument("--skip-list", action="store_true", help="跳过询价 pageList 只读查询")
    p.add_argument("--skip-address", action="store_true", help="跳过收货地址只读查询")
    p.add_argument(
        "--dump-urls-only",
        action="store_true",
        help="只打印全套流程 URL 矩阵与配置完整性，不发业务请求",
    )
    p.add_argument("--list-env", action="store_true")
    return p.parse_args()


def _ok(item: dict[str, Any], **extra: Any) -> dict[str, Any]:
    row = {"ok": True, **item}
    row.update(extra)
    return row


def _fail(item: dict[str, Any], error: str) -> dict[str, Any]:
    return {"ok": False, "error": error, **item}


def _warn(item: dict[str, Any], message: str, **extra: Any) -> dict[str, Any]:
    row = {"ok": True, "warn": True, "message": message, **item}
    row.update(extra)
    return row


def _pipeline_url_matrix() -> dict[str, Any]:
    """按 operate-via 列出上线全套会打到的 URL（供域名比对）。"""
    matrix: dict[str, Any] = {"auth": {}, "routes": {}}
    matrix["auth"] = {
        "en_login": EPAK_PLATFORM_AUTH_API_URL,
        "en_origin": EPAK_PLATFORM_AUTH_ORIGIN,
        "cn_login": AUTH_API_URL,
        "cn_platform": PLATFORM_BASE_URL,
        "supplier_login": CRM_INQUIRY_SUPPLIER_AUTH_API_URL,
        "supplier_auth_origin": CRM_INQUIRY_SUPPLIER_AUTH_ORIGIN,
        "supplier_platform": CRM_INQUIRY_SUPPLIER_PLATFORM_BASE_URL,
        "supplier_query": CRM_INQUIRY_CN_SUPPLIER_QUERY_API_URL,
        "commodity_guest": EPAK_COMMODITY_GUEST_LIST_API_URL,
        "receiver_address": EPAK_RECEIVER_ADDRESS_AGENT_PAGE_API_URL,
        "transfer_order": EPAK_ORDER_AGENT_CREATE_API_URL,
        "supplier_submit_quote": CRM_INQUIRY_CN_SUPPLIER_QUOTE_API_URL,
    }
    svc = CrmInquiryService(ApiClient(timeout=API_TIMEOUT_SECONDS))
    for via in (InquiryOperateVia.EN, InquiryOperateVia.CN):
        route = svc.resolve_route(
            source=InquiryCreateSource.INTERNAL,
            mall=InquiryMall.EN,
            form=InquiryForm.EN,
            operate_via=via,
        )
        urls = CrmInquiryService.en_operation_urls(route)
        q = dict(route.query_params)
        matrix["routes"][via.value] = {
            "origin": route.origin,
            "query_params": q,
            "submit": route.submit_url,
            "query_list": urls.query,
            "submit_tech": urls.submit_tech,
            "push_supplier": urls.push_supplier,
            "offline_quote": urls.offline_quote,
            "offline_adopt": urls.offline_adopt,
            "adopt_quote": urls.adopt_quote,
            "records_by_sub": urls.records_by_sub,
            "supplier_query": urls.supplier_query,
            "submit_factory": urls.submit_factory,
            "submit_platform": urls.submit_platform,
            "confirm_price": urls.confirm_price,
            "relation_product": urls.relation_product,
            "submit_custom_order": urls.submit_custom_order,
            "note": (
                "可到已完成（含转单）"
                if via == InquiryOperateVia.EN
                else "最高待转单；不可转单"
            ),
        }
    return matrix


def _required_config_checklist() -> list[dict[str, Any]]:
    required = [
        ("EPAK_PLATFORM_BASE_URL", EPAK_PLATFORM_BASE_URL),
        ("EPAK_PLATFORM_AUTH_ORIGIN", EPAK_PLATFORM_AUTH_ORIGIN),
        ("PLATFORM_BASE_URL", PLATFORM_BASE_URL),
        ("AUTH_API_URL", AUTH_API_URL),
        ("EPAK_LOGIN_PHONE", EPAK_LOGIN_PHONE),
        ("EPAK_LOGIN_PASSWORD_ENCRYPTED", EPAK_LOGIN_PASSWORD_ENCRYPTED),
        ("EPAK_INQUIRY_TECH_ACCOUNT", EPAK_INQUIRY_TECH_ACCOUNT),
        ("EPAK_INQUIRY_PURCHASER_ACCOUNT", EPAK_INQUIRY_PURCHASER_ACCOUNT),
        ("EPAK_INQUIRY_SUPPORT_ACCOUNT", EPAK_INQUIRY_SUPPORT_ACCOUNT),
        ("CRM_INQUIRY_SUPPLIER_ACCOUNT", CRM_INQUIRY_SUPPLIER_ACCOUNT),
        ("CRM_INQUIRY_SUPPLIER_PLATFORM_BASE_URL", CRM_INQUIRY_SUPPLIER_PLATFORM_BASE_URL),
        ("CRM_INQUIRY_EN_BUYER_MEMBER_ID", CRM_INQUIRY_EN_BUYER_MEMBER_ID),
        ("CRM_INQUIRY_EN_BUYER_MEMBER_NAME", CRM_INQUIRY_EN_BUYER_MEMBER_NAME),
        ("CRM_INQUIRY_EN_BUYER_USER_ID", CRM_INQUIRY_EN_BUYER_USER_ID),
        ("EPAK_INQUIRY_SUPPLIER_MEMBER_ID", EPAK_INQUIRY_SUPPLIER_MEMBER_ID),
        ("CRM_INQUIRY_EN_CATEGORY_FULL_ID", CRM_INQUIRY_EN_CATEGORY_FULL_ID),
        ("CRM_INQUIRY_EN_RELATION_SKU_IDS", CRM_INQUIRY_EN_RELATION_SKU_IDS),
        ("CRM_INQUIRY_EN_TECH_FILE_URL", CRM_INQUIRY_EN_TECH_FILE_URL),
        ("CRM_INQUIRY_EN_FACTORY_CITY", CRM_INQUIRY_EN_FACTORY_CITY),
        ("CRM_INQUIRY_EN_COMPARE_PRICE_REMARK", CRM_INQUIRY_EN_COMPARE_PRICE_REMARK),
    ]
    rows: list[dict[str, Any]] = []
    for key, value in required:
        present = value not in (None, "", [], ())
        if isinstance(value, (list, tuple)):
            present = bool(value)
        rows.append(
            _ok({"check": "config", "key": key}, present=present)
            if present
            else _fail({"check": "config", "key": key}, "未配置（上线全套流程需要）")
        )
    return rows


def _probe_https(url: str, *, label: str, write: bool = False) -> dict[str, Any]:
    """探测 URL 是否可达：优先 HEAD，失败再 GET；不提交业务写 body。"""
    base = {
        "check": "https_probe",
        "label": label,
        "url": url,
        "write_api": write,
        "called": "HEAD/GET only" if write else "HEAD/GET",
    }
    if not url or not str(url).startswith("http"):
        return _fail(base, "URL 无效")
    try:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        session = requests.Session()
        last_status = None
        for method in ("HEAD", "GET"):
            try:
                resp = session.request(
                    method,
                    url,
                    timeout=min(API_TIMEOUT_SECONDS, 15),
                    allow_redirects=True,
                    verify=True,
                )
                last_status = resp.status_code
                # 401/403/405 也说明网关/服务活着；5xx/连接失败才算不通
                if resp.status_code < 500:
                    return _ok(
                        base,
                        origin=origin,
                        http_status=resp.status_code,
                        method=method,
                    )
            except requests.RequestException:
                continue
        if last_status is not None:
            return _fail(base, f"HTTP {last_status}")
        return _fail(base, "连接失败")
    except Exception as exc:  # noqa: BLE001
        return _fail(base, str(exc)[:200])


def _login(
    auth: AuthService,
    *,
    role: str,
    account: str,
    password: str,
    endpoint: str,
) -> dict[str, Any]:
    base = {
        "check": "login",
        "role": role,
        "account": account,
        "endpoint": endpoint,
    }
    if not account or not password:
        return _fail(base, "账号或密码未配置")
    try:
        data = auth.login_with_encrypted_password(account, password, endpoint=endpoint)
        ctx = AuthContext.from_login_data(data)
        return _ok(
            base,
            member_id=ctx.member_id,
            user_id=ctx.user_id,
            token_prefix=(ctx.token or "")[:12],
            _ctx=ctx,
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(base, str(exc)[:240])


def _check_category_config() -> dict[str, Any]:
    base = {"check": "category_config", "category_full_id": CRM_INQUIRY_EN_CATEGORY_FULL_ID}
    if not (CRM_INQUIRY_EN_CATEGORY_FULL_ID or "").strip():
        return _fail(base, "未配置 CRM_INQUIRY_EN_CATEGORY_FULL_ID")
    parts = [p for p in CRM_INQUIRY_EN_CATEGORY_FULL_ID.split(".") if p.strip()]
    if len(parts) < 2:
        return _fail(base, "品类路径级数过少，期望多级 id（点号分隔）")
    return _ok(base, levels=len(parts), parts=parts)


def _query_commodity(ctx: AuthContext, sku_id: int) -> dict[str, Any]:
    base = {
        "check": "commodity_query",
        "sku_id": sku_id,
        "api": EPAK_COMMODITY_GUEST_LIST_API_URL,
        "buyer_member_id": CRM_INQUIRY_EN_BUYER_MEMBER_ID,
    }
    if not CRM_INQUIRY_EN_BUYER_MEMBER_ID:
        return _fail(base, "未配置 CRM_INQUIRY_EN_BUYER_MEMBER_ID")
    try:
        svc = OrderService(ApiClient(timeout=API_TIMEOUT_SECONDS))
        row = svc.get_guest_commodity(
            ctx,
            buyer_member_id=int(CRM_INQUIRY_EN_BUYER_MEMBER_ID),
            sku_id=int(sku_id),
            buyer_role_id=ORDER_BUYER_ROLE_ID,
            api_url=EPAK_COMMODITY_GUEST_LIST_API_URL,
            platform_base_url=EPAK_PLATFORM_BASE_URL,
        )
        return _ok(
            base,
            commodity_id=row.get("commodityId") or row.get("id"),
            name=row.get("name") or row.get("productName"),
            shop_category_id=row.get("shopCategoryId"),
            shop_category_name=row.get("shopCategoryName"),
            member_name=row.get("memberName"),
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(base, str(exc)[:240])


def _query_page_list(ctx: AuthContext, via: InquiryOperateVia) -> dict[str, Any]:
    svc = CrmInquiryService(ApiClient(timeout=API_TIMEOUT_SECONDS))
    route = svc.resolve_route(
        source=InquiryCreateSource.INTERNAL,
        mall=InquiryMall.EN,
        form=InquiryForm.EN,
        operate_via=via,
    )
    urls = CrmInquiryService.en_operation_urls(route)
    base = {
        "check": "page_list",
        "operate_via": via.value,
        "api": urls.query,
        "query_params": dict(route.query_params),
    }
    try:
        body = svc.query_inquiries(
            ctx,
            svc.build_query_payload_for_route(route, current=1, page_size=5),
            route=route,
        )
        svc.assert_success(body, "询价列表只读")
        rows = svc.extract_rows(body)
        return _ok(base, row_count=len(rows), code=body.get("code"))
    except Exception as exc:  # noqa: BLE001
        return _fail(base, str(exc)[:240])


def _query_address(ctx: AuthContext) -> dict[str, Any]:
    base = {
        "check": "receiver_address",
        "api": EPAK_RECEIVER_ADDRESS_AGENT_PAGE_API_URL,
        "buyer_member_id": CRM_INQUIRY_EN_BUYER_MEMBER_ID,
        "buyer_user_id": CRM_INQUIRY_EN_BUYER_USER_ID,
    }
    if not CRM_INQUIRY_EN_BUYER_MEMBER_ID:
        return _fail(base, "未配置 CRM_INQUIRY_EN_BUYER_MEMBER_ID")
    try:
        svc = OrderService(ApiClient(timeout=API_TIMEOUT_SECONDS))
        addr = svc.get_buyer_receiver_address(
            ctx,
            buyer_member_id=int(CRM_INQUIRY_EN_BUYER_MEMBER_ID),
            buyer_user_id=(
                int(CRM_INQUIRY_EN_BUYER_USER_ID)
                if CRM_INQUIRY_EN_BUYER_USER_ID
                else None
            ),
            api_url=EPAK_RECEIVER_ADDRESS_AGENT_PAGE_API_URL,
            platform_base_url=EPAK_PLATFORM_BASE_URL,
        )
        return _ok(
            base,
            address_id=addr.get("id"),
            consignee=addr.get("consignee") or addr.get("name"),
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(base, str(exc)[:240])


def _probe_all_pipeline_urls(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    auth = matrix.get("auth") or {}
    for key, url in auth.items():
        write = key in {"transfer_order", "supplier_submit_quote"}
        results.append(_probe_https(str(url), label=f"auth.{key}", write=write))
    for via, route_urls in (matrix.get("routes") or {}).items():
        for key, url in route_urls.items():
            if key in {"origin", "query_params", "note"} or not isinstance(url, str):
                continue
            write = key in _WRITE_STEP_KEYS or key == "submit"
            results.append(
                _probe_https(url, label=f"route.{via}.{key}", write=write)
            )
    return results


def _strip_ctx(row: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in row.items() if k != "_ctx"}
    return out


def main() -> int:
    args = parse_args()
    if args.env is not None and args.env != _ACTIVE_ENV:
        print(
            f"警告: 进程启动已加载 {_ACTIVE_ENV!r}，与 --env {args.env!r} 不一致。"
            f"请把 --env 放在命令靠前位置。",
            file=sys.stderr,
        )

    matrix = _pipeline_url_matrix()

    if args.list_env:
        info = describe_env_files(args.env or _ACTIVE_ENV)
        info.update(
            {
                "platform_base_url": EPAK_PLATFORM_BASE_URL,
                "cn_platform_base_url": PLATFORM_BASE_URL,
                "auth_origin": EPAK_PLATFORM_AUTH_ORIGIN,
                "category_full_id": CRM_INQUIRY_EN_CATEGORY_FULL_ID,
                "relation_sku_ids": CRM_INQUIRY_EN_RELATION_SKU_IDS,
                "pipeline_urls": matrix,
            }
        )
        print(json.dumps(info, ensure_ascii=False, indent=2))
        if not info.get("profile_exists") and EPAK_ENV == "prod":
            print(
                "警告: 未找到 .env.en.prod，请复制 .env.en.prod.example 并填全套参数。",
                file=sys.stderr,
            )
            return 2
        return 0

    env_info = describe_env_files(args.env or _ACTIVE_ENV)
    if EPAK_ENV == "prod" and not env_info.get("profile_exists"):
        print(
            "未找到 .env.en.prod。请先复制 .env.en.prod.example，按全套流程填齐参数后再预检。",
            file=sys.stderr,
        )
        return 2

    config_checks = _required_config_checklist()
    if args.dump_urls_only:
        report = {
            "epak_env": EPAK_ENV,
            "mode": "dump_urls_and_config",
            "note": "未发业务写请求；上线造数请用 create_inquiry.py --allow-prod-seed",
            "pipeline_urls": matrix,
            "config_checks": config_checks,
            "summary": {
                "config_missing": sum(1 for r in config_checks if not r.get("ok")),
            },
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if any(not r.get("ok") for r in config_checks) else 0

    via_raw = (args.operate_via or "both").strip().lower()
    if via_raw == "both":
        vias = [InquiryOperateVia.EN, InquiryOperateVia.CN]
    else:
        vias = [parse_operate_via(via_raw)]

    results: list[dict[str, Any]] = []
    results.extend(config_checks)
    results.append(_check_category_config())
    results.extend(_probe_all_pipeline_urls(matrix))

    auth = AuthService(ApiClient(timeout=API_TIMEOUT_SECONDS))
    sales_account = EPAK_LOGIN_PHONE
    sales_password = EPAK_LOGIN_PASSWORD_ENCRYPTED
    en_sales_ctx: AuthContext | None = None
    cn_sales_ctx: AuthContext | None = None
    supplier_checked = False

    for via in vias:
        endpoint = "cn" if via == InquiryOperateVia.CN else "en"
        sales_row = _login(
            auth,
            role="sales",
            account=sales_account,
            password=sales_password,
            endpoint=endpoint,
        )
        results.append(_strip_ctx(sales_row))
        ctx = sales_row.pop("_ctx", None)
        if sales_row.get("ok") and isinstance(ctx, AuthContext):
            if endpoint == "en":
                en_sales_ctx = ctx
            else:
                cn_sales_ctx = ctx

        for item in CrmInquiryService.role_login_accounts(
            InquiryMall.EN, operate_via=via
        ):
            if item.role == "supplier":
                continue
            row = _login(
                auth,
                role=item.role,
                account=item.account,
                password=item.password,
                endpoint=item.endpoint,
            )
            results.append(_strip_ctx(row))
            if (
                via == InquiryOperateVia.CN
                and item.role == "support"
                and not row.get("ok")
            ):
                results.append(
                    _warn(
                        {"check": "note"},
                        "CN support 登录失败时造数会用 purchaser 兜底；"
                        "可配 CRM_INQUIRY_SUPPORT_ACCOUNT",
                    )
                )

        if not supplier_checked and CRM_INQUIRY_SUPPLIER_ACCOUNT:
            supplier_checked = True
            results.append(
                _strip_ctx(
                    _login(
                        auth,
                        role="supplier",
                        account=CRM_INQUIRY_SUPPLIER_ACCOUNT,
                        password=CRM_INQUIRY_SUPPLIER_PASSWORD_ENCRYPTED,
                        endpoint="supplier",
                    )
                )
            )

        if not args.skip_list:
            list_ctx = cn_sales_ctx if via == InquiryOperateVia.CN else en_sales_ctx
            if list_ctx is None:
                results.append(
                    _fail(
                        {"check": "page_list", "operate_via": via.value},
                        f"{endpoint} sales 未登录，跳过列表",
                    )
                )
            else:
                results.append(_query_page_list(list_ctx, via))

    if not args.skip_commodity:
        skus = list(CRM_INQUIRY_EN_RELATION_SKU_IDS or [])
        if not skus:
            results.append(
                _fail({"check": "commodity_query"}, "未配置 CRM_INQUIRY_EN_RELATION_SKU_IDS")
            )
        elif en_sales_ctx is None:
            results.append(
                _fail({"check": "commodity_query"}, "英文站 sales 登录失败，无法查商品")
            )
        else:
            for sku in skus:
                results.append(_query_commodity(en_sales_ctx, int(sku)))

    if not args.skip_address:
        if en_sales_ctx is None:
            results.append(
                _fail({"check": "receiver_address"}, "英文站 sales 登录失败，无法查地址")
            )
        else:
            results.append(_query_address(en_sales_ctx))

    failed = [r for r in results if not r.get("ok")]
    hard_failed = [
        r
        for r in failed
        if not (
            r.get("check") == "login"
            and r.get("role") == "support"
            and r.get("endpoint") == "cn"
        )
    ]

    report = {
        "epak_env": EPAK_ENV,
        "mode": "preflight_no_create",
        "note": (
            "本报告不含创建/改状态/下单。"
            "上线全套请: python scripts/create_inquiry.py --env prod --allow-prod-seed ..."
        ),
        "platform_base_url": EPAK_PLATFORM_BASE_URL,
        "cn_platform_base_url": PLATFORM_BASE_URL,
        "operate_via": via_raw,
        "pipeline_urls": matrix,
        "checks": results,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.get("ok")),
            "failed": len(failed),
            "hard_failed": len(hard_failed),
            "write_apis_probed_only": True,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if hard_failed:
        print(
            f"预检未通过: {len(hard_failed)} 项硬失败（写接口仅做可达探测，未创建数据）",
            file=sys.stderr,
        )
        return 1
    if failed:
        print("预检通过（有警告：CN support 登录失败可 purchaser 兜底）", file=sys.stderr)
    else:
        print(
            "预检通过：配置/域名可达/登录/只读查询均 OK。上线再用 --allow-prod-seed 跑全套。",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
