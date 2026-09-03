"""询价单按状态造数：支持创建入口 / 中英文商城 / 通用品·定制品 / 多子单 / test|uat 环境。

用法（不传 --env 时默认 test，行为与现在一致）:
  python scripts/create_inquiry.py --list-status
  python scripts/create_inquiry.py --list-routes
  python scripts/create_inquiry.py --source internal --mall en --form en --status 待平台报价
  python scripts/create_inquiry.py --source internal --mall en --form en --subs-file testdata/crm/multi_subs_quote_options.json

切换 UAT / 生产配置:
  python scripts/create_inquiry.py --env uat --source internal --mall en --form en ...
  生产环境请用只读验证（禁止默认造数）:
  python scripts/verify_prod_inquiry_env.py --env prod
  或: $env:EPAK_ENV='uat'

中文站操作英文单（默认仍是英文站；最高到「待转单」，不支持转单已完成）:
  python scripts/create_inquiry.py --env uat --operate-via cn --source internal --mall en --form en --status 待转单

环境说明:
  默认 test → 加载 .env.en.test（当前测试环境）
  --env uat  → 加载 .env.en.uat
  --env prod → 加载 .env.en.prod（默认拒绝造数，须 --allow-prod-seed）
  --operate-via en|cn → 英文单操作站点（默认 en；cn 不可做到已完成）

子单 JSON 字段（每条子单可单独配置）:
  ask_price_type   通用品 / 定制品
  target_status    待出厂报价 / 待平台报价 / 已完成 ...
  quote_channels   both / online / offline（造哪些报价）
  adopt_source     online / offline / auto（出厂采纳哪条）
  packaging_type   1|纸箱 / 2|卷类 / 3|其他
  is_pallet        1|是 / 0|否

PowerShell 多子单（不要用 \\" 转义，用 --subs-file 或环境变量）:
  $env:CRM_INQUIRY_SUBS_JSON='[{"ask_price_type":"定制品"},{"ask_price_type":"通用品"}]'
  python scripts/create_inquiry.py --source internal --mall en --form en --status 待出厂报价
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 必须在 import config.settings 之前按 --env 加载环境文件
from config.env_loader import bootstrap_env, describe_env_files, is_prod_env, peek_cli_env

_ACTIVE_ENV = bootstrap_env(peek_cli_env())

from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.auth_service import AuthService
from api.services.crm_inquiry_service import CrmInquiryService
from api.services.crm_inquiry_status import (
    InquiryMall,
    InquiryOperateVia,
    InquiryRoleMissing,
    InquiryTransitionNotWired,
    parse_ask_price_type,
    parse_create_source,
    parse_inquiry_form,
    parse_inquiry_mall,
    parse_inquiry_status,
    parse_operate_via,
)
from config.settings import (
    API_TIMEOUT_SECONDS,
    CRM_INQUIRY_ASK_PRICE_TYPE,
    CRM_INQUIRY_CREATE_SOURCE,
    CRM_INQUIRY_FORM,
    CRM_INQUIRY_MALL,
    CRM_INQUIRY_OPERATE_VIA,
    CRM_INQUIRY_SUBS_JSON,
    CRM_INQUIRY_SUPPLIER_AUTH_API_URL,
    CRM_INQUIRY_SUPPLIER_AUTH_ORIGIN,
    CRM_INQUIRY_SUPPLIER_PLATFORM_BASE_URL,
    CRM_INQUIRY_TARGET_STATUS,
    EPAK_ENV,
    EPAK_LOGIN_PASSWORD_ENCRYPTED,
    EPAK_LOGIN_PHONE,
    EPAK_PLATFORM_AUTH_ORIGIN,
    EPAK_PLATFORM_BASE_URL,
    LOGIN_PASSWORD_ENCRYPTED,
    LOGIN_PHONE,
    PLATFORM_BASE_URL,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按目标状态创建询价单测试数据")
    parser.add_argument(
        "--env",
        choices=["test", "uat", "prod"],
        default=None,
        help="英文商城环境；不传默认 test。prod 默认禁止造数，须加 --allow-prod-seed",
    )
    parser.add_argument(
        "--allow-prod-seed",
        action="store_true",
        help="显式允许在 --env prod 下造数（会写生产数据，上线验证勿用）",
    )
    parser.add_argument(
        "--status",
        default=CRM_INQUIRY_TARGET_STATUS,
        help="默认目标状态（可被 --subs 里每条子单 target_status 覆盖）",
    )
    parser.add_argument(
        "--type",
        "--ask-price-type",
        dest="ask_price_type",
        default=CRM_INQUIRY_ASK_PRICE_TYPE,
        help="子单类型：定制品/通用品/1/2",
    )
    parser.add_argument(
        "--source",
        default=CRM_INQUIRY_CREATE_SOURCE,
        help="创建入口：crm_customer|internal",
    )
    parser.add_argument(
        "--mall",
        default=CRM_INQUIRY_MALL,
        help="操作商城：cn 中文商城 | en 英文商城",
    )
    parser.add_argument(
        "--form",
        default=CRM_INQUIRY_FORM,
        help="询价单语种：cn 中文询价单 | en 英文询价单（中文商城 mallType=2）",
    )
    parser.add_argument(
        "--operate-via",
        default=CRM_INQUIRY_OPERATE_VIA or "en",
        help="英文单操作站点：en=英文站（默认，可到已完成）| cn=中文站（最高待转单，不可转单）",
    )
    parser.add_argument(
        "--subs",
        default="",
        help="多子单 JSON 字符串；PowerShell 请用单引号包裹或改用 --subs-file / CRM_INQUIRY_SUBS_JSON",
    )
    parser.add_argument(
        "--subs-file",
        default="",
        help="多子单 JSON 文件路径（内容与 --subs 相同，Windows 推荐）",
    )
    parser.add_argument(
        "--list-status",
        action="store_true",
        help="打印创建路由 + 定制品/通用品状态流水线后退出",
    )
    parser.add_argument(
        "--list-routes",
        action="store_true",
        help="打印三条内部询价创建路由（URL/Referer）后退出",
    )
    parser.add_argument(
        "--list-env",
        action="store_true",
        help="打印当前环境及配置文件路径后退出",
    )
    parser.add_argument("--material-name", default="", help="物料名称，默认自动生成")
    return parser.parse_args()


def _load_subs(args: argparse.Namespace) -> list | None:
    raw = (args.subs or CRM_INQUIRY_SUBS_JSON or "").strip()
    if args.subs_file:
        path = Path(args.subs_file)
        if not path.is_file():
            raise FileNotFoundError(f"子单配置文件不存在: {path}")
        raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    subs = json.loads(raw)
    if not isinstance(subs, list):
        raise ValueError("--subs / --subs-file 必须是 JSON 数组")
    return subs


def _login_roles(
    auth: AuthService,
    mall: InquiryMall,
    *,
    operate_via: str | None = None,
) -> tuple[dict[str, AuthContext], Callable[[str], AuthContext]]:
    via = parse_operate_via(operate_via)
    # 英文单 + 中文站操作：角色登录中文 auth（账号仍用 EPAK_*）
    if mall == InquiryMall.EN and via == InquiryOperateVia.CN:
        endpoint = "cn"
        primary_account = EPAK_LOGIN_PHONE
        primary_password = EPAK_LOGIN_PASSWORD_ENCRYPTED
    elif mall == InquiryMall.EN:
        endpoint = "en"
        primary_account = EPAK_LOGIN_PHONE
        primary_password = EPAK_LOGIN_PASSWORD_ENCRYPTED
    else:
        endpoint = "cn"
        primary_account = LOGIN_PHONE
        primary_password = LOGIN_PASSWORD_ENCRYPTED

    specs = {
        "sales": (primary_account, primary_password, endpoint),
    }
    for item in CrmInquiryService.role_login_accounts(mall, operate_via=via):
        if item.account:
            specs[item.role] = (item.account, item.password, item.endpoint)

    def _login_one(role: str) -> AuthContext:
        if role not in specs:
            raise AssertionError(f"无法重登未知角色: {role}")
        account, password, ep = specs[role]
        data = auth.login_with_encrypted_password(account, password, endpoint=ep)
        return AuthContext.from_login_data(data)

    roles: dict[str, AuthContext] = {}
    for role in ("sales", "tech", "purchaser", "support", "supplier"):
        if role not in specs:
            continue
        try:
            roles[role] = _login_one(role)
        except AssertionError as exc:
            if role == "sales":
                raise
            print(
                f"警告: 角色登录失败已跳过 role={role} account={specs[role][0]} "
                f"endpoint={specs[role][2]}: {exc}",
                file=sys.stderr,
            )
    if mall == InquiryMall.EN and "purchaser" not in roles:
        roles["purchaser"] = roles["sales"]
        if "purchaser" not in specs and "sales" in specs:
            specs["purchaser"] = specs["sales"]
    # 中文站操作英文单：EN support 常无法登录中文 auth，用 purchaser/sales 兜底（平台报价等权限已验证）
    if (
        mall == InquiryMall.EN
        and via == InquiryOperateVia.CN
        and "support" not in roles
    ):
        for fallback in ("purchaser", "sales"):
            if fallback in roles and fallback in specs:
                roles["support"] = roles[fallback]
                specs["support"] = specs[fallback]
                print(
                    f"警告: --operate-via cn 下 support 无法登录中文 auth，"
                    f"已用 {fallback}({specs[fallback][0]}) 兜底平台报价/上架等步骤。"
                    f"若需专用账号请配置 CRM_INQUIRY_SUPPORT_ACCOUNT（须能登录中文 auth）。",
                    file=sys.stderr,
                )
                break
    # 同会员后登录踢先登录：统一成最后一次有效会话（避免 sales/purchaser 互踢导致 1101）
    roles = CrmInquiryService.reconcile_same_member_sessions(roles)

    def role_relogin(role: str) -> AuthContext:
        # creator 按入口映射到 sales/purchaser
        key = role
        if role == "creator":
            key = "purchaser" if "purchaser" in specs else "sales"
        ctx = _login_one(key if key in specs else "sales")
        return ctx

    return roles, role_relogin


def main() -> int:
    args = parse_args()
    if args.env is not None and args.env != _ACTIVE_ENV:
        print(
            f"警告: 进程启动时已加载环境 {_ACTIVE_ENV!r}，与 --env {args.env!r} 不一致。"
            f"请把 --env 放在命令靠前位置后重跑。",
            file=sys.stderr,
        )
    svc = CrmInquiryService(ApiClient(timeout=API_TIMEOUT_SECONDS))
    if args.list_env:
        info = describe_env_files(args.env or _ACTIVE_ENV)
        info.update(
            {
                "platform_base_url": EPAK_PLATFORM_BASE_URL,
                "cn_platform_base_url": PLATFORM_BASE_URL,
                "auth_origin": EPAK_PLATFORM_AUTH_ORIGIN,
                "login_phone": EPAK_LOGIN_PHONE,
                "operate_via": parse_operate_via(args.operate_via).value,
                "supplier_auth_origin": CRM_INQUIRY_SUPPLIER_AUTH_ORIGIN,
                "supplier_auth_api_url": CRM_INQUIRY_SUPPLIER_AUTH_API_URL,
                "supplier_platform_base_url": CRM_INQUIRY_SUPPLIER_PLATFORM_BASE_URL,
            }
        )
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0
    if args.list_status:
        print(
            json.dumps(
                {
                    "epak_env": EPAK_ENV,
                    "platform_base_url": EPAK_PLATFORM_BASE_URL,
                    "routes": svc.describe_create_routes(),
                    "pipeline": svc.describe_seed_pipeline(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.list_routes:
        print(json.dumps(svc.describe_create_routes(), ensure_ascii=False, indent=2))
        return 0

    if is_prod_env(_ACTIVE_ENV) and not args.allow_prod_seed:
        print(
            "已拒绝：--env prod 默认禁止造数，避免误写生产。\n"
            "【现在】域名/接口/登录预检（不创建）:\n"
            "  python scripts/verify_prod_inquiry_env.py --env prod --operate-via both\n"
            "【上线当晚】全套造数（会写生产数据）:\n"
            "  python scripts/create_inquiry.py --env prod --allow-prod-seed "
            "--source internal --mall en --form en --status 已完成",
            file=sys.stderr,
        )
        return 2

    source = parse_create_source(args.source)
    mall = parse_inquiry_mall(args.mall)
    form = parse_inquiry_form(args.form) if args.form else None
    operate_via = parse_operate_via(args.operate_via)
    ask_type = parse_ask_price_type(args.ask_price_type)
    target = parse_inquiry_status(args.status)
    try:
        subs = _load_subs(args)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"子单配置解析失败: {exc}", file=sys.stderr)
        return 2

    auth = AuthService(ApiClient(timeout=API_TIMEOUT_SECONDS))
    roles, role_relogin = _login_roles(auth, mall, operate_via=operate_via)
    missing = svc.missing_seed_requirement(
        target,
        roles,
        ask_price_type=ask_type,
        source=source,
        mall=mall,
        form=form,
        operate_via=operate_via,
        subs=subs,
    )
    if missing:
        print(missing, file=sys.stderr)
        return 2

    try:
        result = svc.create_inquiry_to_status(
            roles["sales"],
            target,
            role_auths=roles,
            material_name=args.material_name or None,
            ask_price_type=ask_type,
            source=source,
            mall=mall,
            form=form,
            operate_via=operate_via,
            subs=subs,
            role_relogin=role_relogin,
        )
    except (InquiryTransitionNotWired, InquiryRoleMissing) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "epak_env": EPAK_ENV,
                "platform_base_url": EPAK_PLATFORM_BASE_URL,
                "cn_platform_base_url": PLATFORM_BASE_URL,
                "operate_via": operate_via.value,
                "operate_via_label": operate_via.label,
                "source": result.source.value,
                "source_label": result.source.label,
                "mall": result.mall.label if result.mall else None,
                "form": result.form.label if result.form else None,
                "main_id": result.main_id,
                "main_number": result.main_number,
                "quotation_no": result.quotation_no,
                "subs": [
                    {
                        "sub_id": s.sub_id,
                        "sub_number": s.sub_number,
                        "ask_price_type": s.ask_price_type,
                        "ask_price_type_name": s.ask_price_type_name,
                        "status": s.status,
                        "status_name": s.status_name,
                        "target": s.target.label if s.target else None,
                        "current_operator": s.current_operator,
                    }
                    for s in result.subs
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
