"""按商城、客户、销售、金额、状态批量造销售订单。"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.auth_service import AuthService
from api.services.crm_inquiry_service import CrmInquiryService
from api.services.order_service import (
    ORDER_AGENT_REFERER,
    OrderLineItem,
    OrderService,
    parse_order_line_items,
)
from config.settings import (
    API_TIMEOUT_SECONDS,
    CRM_INQUIRY_BUYER_SALE_ORG_TYPE,
    CRM_INQUIRY_EN_ORDER_CURRENCY_ID,
    CRM_INQUIRY_EN_ORDER_SHOP_CLASSIFY,
    CRM_INQUIRY_EN_ORDER_SHOP_NAME,
    CRM_INQUIRY_EN_RELATION_SKU_IDS,
    EPAK_COMMODITY_GUEST_LIST_API_URL,
    EPAK_LOGIN_PASSWORD_ENCRYPTED,
    EPAK_LOGIN_PHONE,
    EPAK_ORDER_AGENT_CREATE_API_URL,
    EPAK_PLATFORM_BASE_URL,
    EPAK_RECEIVER_ADDRESS_AGENT_PAGE_API_URL,
    LOGIN_PASSWORD_ENCRYPTED,
    LOGIN_PHONE,
    ORDER_BUYER_ROLE_ID,
    ORDER_CONTRACT_FILE_PATH,
    ORDER_SHOP_ID,
    ORDER_SKU_ID,
    ORDER_VOUCHER_FILE_PATH,
    PLATFORM_BASE_URL,
)

STATUS_PENDING_CONTRACT = "待签署合同"
STATUS_PENDING_PAY = "待支付"
STATUS_PENDING_PAY_CONFIRM = "待确认支付结果"
STATUS_STOCK_UP = "订单备货中"
STATUS_PENDING_SHIP = "待确认发货"
STATUS_CANCELLED = "已取消"
PAY_OFFLINE = "线下支付"
PAY_ACCOUNT_PERIOD = "账期"

# 英文代客下单成功报文里的贸易方式。询价转单用的是另一套默认值，不能混用。
EN_AGENT_TRADE_MODE = 3
EN_PAY_NODE = "合同签署后"

_STATUS_ALIASES: dict[str, str] = {
    "待签署合同": STATUS_PENDING_CONTRACT,
    "待签署": STATUS_PENDING_CONTRACT,
    "待支付": STATUS_PENDING_PAY,
    "待确认支付结果": STATUS_PENDING_PAY_CONFIRM,
    "待确认支付": STATUS_PENDING_PAY_CONFIRM,
    "订单备货中": STATUS_STOCK_UP,
    "备货中": STATUS_STOCK_UP,
    "有效": STATUS_STOCK_UP,
    "待确认发货": STATUS_PENDING_SHIP,
    "已取消": STATUS_CANCELLED,
    "取消": STATUS_CANCELLED,
}

_STATUS_NEED_CAPTURE: dict[str, str] = {
    "待确认收货": "从待确认发货推进到待确认收货",
    "已完成": "从待确认收货推进到已完成",
    "完成": "从待确认收货推进到已完成",
}

_MALL_ALIASES: dict[str, str] = {
    "cn": "cn",
    "zh": "cn",
    "中文": "cn",
    "中文商城": "cn",
    "en": "en",
    "英文": "en",
    "英文商城": "en",
}

_PAY_ALIASES: dict[str, str] = {
    "": PAY_OFFLINE,
    "线下": PAY_OFFLINE,
    "线下支付": PAY_OFFLINE,
    "账期": PAY_ACCOUNT_PERIOD,
    "月结": PAY_ACCOUNT_PERIOD,
    "结算": PAY_ACCOUNT_PERIOD,
    "结算支付": PAY_ACCOUNT_PERIOD,
    "结算支付-月结": PAY_ACCOUNT_PERIOD,
}


@dataclass(frozen=True)
class OrderSeedSpec:
    mall: str
    customer: str
    sales: str
    status: str
    amount: float | None = None
    quantity: int | None = None
    sku_id: int | None = None
    items: tuple[OrderLineItem, ...] | None = None
    member_id: int | None = None
    buyer_user_id: int | None = None
    free_shipping: bool = False
    currency_id: int | None = None
    pay: str = PAY_OFFLINE


@dataclass(frozen=True)
class MallOrderProfile:
    mall: str
    platform_base_url: str
    login_endpoint: str
    login_phone: str
    login_password: str
    default_sku_id: int
    currency_id: int | None = None
    shop_name: str | None = None
    shop_classify: int | None = None
    trade_mode: int | None = None

    def url(self, path: str) -> str:
        return f"{self.platform_base_url.rstrip('/')}{path}"

    @property
    def create_url(self) -> str:
        if self.mall == "en":
            return EPAK_ORDER_AGENT_CREATE_API_URL
        return self.url("/api/order/vendor/create/agent/order")

    @property
    def page_url(self) -> str:
        return self.url("/api/order/vendor/page")

    @property
    def detail_url(self) -> str:
        if self.mall == "en":
            return self.url("/api/order/vendor/detail")
        return self.url("/api/order/vendor/combination/detail")

    @property
    def contract_url(self) -> str:
        return self.url("/api/order/vendor/upload/contract")

    @property
    def valet_url(self) -> str:
        return self.url("/api/order/vendor/validate/valet/pay")

    @property
    def confirm_url(self) -> str:
        return self.url("/api/order/vendor/validate/pay/confirm")

    @property
    def upload_url(self) -> str:
        if self.mall == "en":
            return self.url("/api/file/file/upload")
        return self.url("/api/file/file/upload/batch")

    @property
    def stock_up_url(self) -> str:
        return self.url("/api/order/vendor/order/stock/up")

    @property
    def cancel_url(self) -> str:
        return self.url("/api/order/vendor/cancel")

    @property
    def commodity_url(self) -> str:
        if self.mall == "en":
            return EPAK_COMMODITY_GUEST_LIST_API_URL
        return self.url("/api/product/commodity/common/getCommodityListByGuest")

    @property
    def address_url(self) -> str:
        if self.mall == "en":
            return EPAK_RECEIVER_ADDRESS_AGENT_PAGE_API_URL
        return self.url("/api/logistics/receiverAddress/agent/page")


def parse_mall(value: str) -> str:
    key = (value or "").strip().lower()
    # 中文别名不做 lower 比较
    raw = (value or "").strip()
    found = _MALL_ALIASES.get(key) or _MALL_ALIASES.get(raw)
    if not found:
        raise ValueError(f"无法识别商城 {value!r}，请用 cn/中文商城 或 en/英文商城")
    return found


def parse_status(value: str) -> str:
    raw = (value or "").strip()
    pending = _STATUS_NEED_CAPTURE.get(raw)
    if pending:
        raise ValueError(f"订单状态 {raw} 还不能造。需要{pending}的接口请求")
    found = _STATUS_ALIASES.get(raw)
    if not found:
        supported = "、".join(dict.fromkeys(_STATUS_ALIASES.values()))
        raise ValueError(f"无法识别订单状态 {value!r}。当前可造：{supported}")
    return found


def parse_pay(value: str | None) -> str:
    raw = str(value or "").strip()
    found = _PAY_ALIASES.get(raw) or _PAY_ALIASES.get(raw.lower())
    if not found:
        raise ValueError(f"无法识别支付方式 {value!r}，可用：线下支付 / 账期")
    return found


def status_reached(expected: str, actual: str) -> bool:
    if expected in actual or actual in expected:
        return True
    return expected == STATUS_STOCK_UP and "挂账成功" in actual


def _as_bool(value: Any, default: bool) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def member_free_shipping_payload(customer: dict, *, free_shipping: bool) -> dict:
    """中文商城会员包邮。对齐 updateMemberCustomSetting，其余开关沿用客户当前值。"""
    member_id = customer.get("memberId")
    if member_id in (None, ""):
        raise ValueError("设置包邮需要 memberId")
    sale_org = customer.get("saleOrgType")
    hierarchy = customer.get("hierarchicalConfiguration")
    return {
        "memberId": int(member_id),
        "isFreeShipping": bool(free_shipping),
        "isDistribution": _as_bool(customer.get("isDistribution"), True),
        "isAutomaticInvoicing": _as_bool(customer.get("isAutomaticInvoicing"), False),
        "isSignContract": _as_bool(customer.get("isSignContract"), False),
        "saleOrgType": int(sale_org) if sale_org not in (None, "") else CRM_INQUIRY_BUYER_SALE_ORG_TYPE,
        "hierarchicalConfiguration": int(hierarchy) if hierarchy not in (None, "") else 1,
    }


def parse_amount(value: Any) -> float:
    try:
        amount = round(float(value), 2)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"订单金额无法解析: {value!r}") from exc
    if amount < 0:
        raise ValueError(f"订单金额不能为负: {amount}")
    return amount


def parse_seed_line_items(raw: Any, *, prefix: str) -> tuple[OrderLineItem, ...] | None:
    if raw in (None, ""):
        return None
    if isinstance(raw, str):
        items = tuple(parse_order_line_items(raw))
        if len(items) < 1:
            raise ValueError(f"{prefix}items 至少一行")
        return items
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{prefix}items 必须是非空数组")
    items: list[OrderLineItem] = []
    for i, row in enumerate(raw, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"{prefix}items 第 {i} 行不是对象")
        sku = row.get("sku_id", row.get("skuId"))
        qty = row.get("quantity", row.get("qty"))
        if sku in (None, "") or qty in (None, ""):
            raise ValueError(f"{prefix}items 第 {i} 行需要 sku_id 和 quantity")
        quantity = int(qty)
        if quantity < 1:
            raise ValueError(f"{prefix}items 第 {i} 行采购数量必须大于 0")
        items.append(OrderLineItem(sku_id=int(sku), quantity=quantity))
    return tuple(items)


def parse_order_spec(raw: dict, *, index: int | None = None) -> OrderSeedSpec:
    if not isinstance(raw, dict):
        raise ValueError(f"第 {index} 笔不是对象")
    prefix = f"第 {index} 笔" if index is not None else "订单"
    missing = [name for name in ("mall", "customer", "sales", "status") if raw.get(name) in (None, "")]
    if missing:
        raise ValueError(f"{prefix}缺少字段: {', '.join(missing)}")
    amount_raw = raw.get("amount")
    quantity_raw = raw.get("quantity")
    items = parse_seed_line_items(raw.get("items"), prefix=prefix)
    if amount_raw in (None, "") and quantity_raw in (None, "") and not items:
        raise ValueError(f"{prefix}需要 amount、quantity 或 items")
    sku = raw.get("sku_id", raw.get("skuId"))
    member_id = raw.get("member_id", raw.get("memberId"))
    buyer_user_id = raw.get("buyer_user_id", raw.get("buyerUserId"))
    free_shipping = raw.get("free_shipping", raw.get("freeShipping", raw.get("isFreeShipping")))
    currency_raw = raw.get("currency_id", raw.get("currencyId"))
    quantity = int(quantity_raw) if quantity_raw not in (None, "") else None
    if quantity is not None and quantity < 1:
        raise ValueError(f"{prefix}采购数量必须大于 0")
    return OrderSeedSpec(
        mall=parse_mall(str(raw["mall"])),
        customer=str(raw["customer"]).strip(),
        sales=str(raw["sales"]).strip(),
        amount=parse_amount(amount_raw) if amount_raw not in (None, "") else None,
        quantity=quantity,
        status=parse_status(str(raw["status"])),
        sku_id=int(sku) if sku not in (None, "") else None,
        items=items,
        member_id=int(member_id) if member_id not in (None, "") else None,
        buyer_user_id=int(buyer_user_id) if buyer_user_id not in (None, "") else None,
        free_shipping=_as_bool(free_shipping, False),
        currency_id=int(currency_raw) if currency_raw not in (None, "") else None,
        pay=parse_pay(raw.get("pay") or raw.get("payType") or PAY_OFFLINE),
    )


def parse_order_specs(raw: Any) -> list[OrderSeedSpec]:
    if isinstance(raw, dict):
        items = [raw]
    elif isinstance(raw, list):
        items = raw
    else:
        raise ValueError("订单清单必须是 JSON 对象或数组")
    if not items:
        raise ValueError("订单清单为空")
    return [parse_order_spec(item, index=i + 1) for i, item in enumerate(items)]


def load_order_specs(text: str) -> list[OrderSeedSpec]:
    return parse_order_specs(json.loads(text))


def mall_profile(mall: str) -> MallOrderProfile:
    kind = parse_mall(mall)
    if kind == "en":
        return MallOrderProfile(
            mall="en",
            platform_base_url=EPAK_PLATFORM_BASE_URL.rstrip("/"),
            login_endpoint="en",
            login_phone=EPAK_LOGIN_PHONE,
            login_password=EPAK_LOGIN_PASSWORD_ENCRYPTED,
            default_sku_id=int(CRM_INQUIRY_EN_RELATION_SKU_IDS[0]),
            currency_id=CRM_INQUIRY_EN_ORDER_CURRENCY_ID,
            shop_name=CRM_INQUIRY_EN_ORDER_SHOP_NAME,
            shop_classify=CRM_INQUIRY_EN_ORDER_SHOP_CLASSIFY,
            trade_mode=EN_AGENT_TRADE_MODE,
        )
    return MallOrderProfile(
        mall="cn",
        platform_base_url=PLATFORM_BASE_URL.rstrip("/"),
        login_endpoint="cn",
        login_phone=LOGIN_PHONE,
        login_password=LOGIN_PASSWORD_ENCRYPTED,
            default_sku_id=int(ORDER_SKU_ID),
    )


def solve_quantity(unit_price: float, freight: float, amount: float) -> int:
    """用商品目录单价和运费反推数量，使货款 + 运费等于订单金额。

    代客下单会校验单价必须等于商品目录价，不能直接改单价。
    """
    unit = round(float(unit_price), 2)
    ship = round(float(freight), 2)
    target = round(float(amount), 2)
    if unit <= 0:
        if target == ship:
            raise AssertionError("商品单价为 0，请直接把订单金额写成 0，或更换商品")
        raise AssertionError(f"商品单价为 0，无法造出订单金额 {target}")
    goods = round(target - ship, 2)
    if goods < 0:
        raise AssertionError(f"订单金额 {target} 小于运费 {ship}，请提高金额或换包邮商品")
    if goods == 0:
        raise AssertionError(
            f"商品单价为 {unit:g}，运费为 {ship:g}，这个商品造不出 0 元订单"
        )
    qty = goods / unit
    if abs(qty - round(qty)) > 0.001:
        raise AssertionError(
            f"商品单价 {unit:g}，运费 {ship:g}，订单金额需要是「单价 × 整数数量 + 运费」。"
            f"例如 {unit + ship:g}、{unit * 2 + ship:g}。当前金额 {target:g} 对不上"
        )
    quantity = int(round(qty))
    if quantity < 1:
        raise AssertionError(f"换算出的数量为 {quantity}，无法下单")
    return quantity


def apply_sales(payload: dict, *, user_id: int, name: str) -> None:
    payload["customerManagerId"] = int(user_id)
    payload["customerManager"] = name
    payload["customerManagerName"] = name


def minimum_order_quantity(guest: dict) -> int:
    raw = guest.get("minOrder")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 1
    return max(int(round(value)), 1)


def assert_quantity_allowed(guest: dict, quantity: int) -> None:
    minimum = minimum_order_quantity(guest)
    if int(quantity) < minimum:
        raise AssertionError(
            f"商品起订量是 {minimum}，当前采购数量 {quantity} 不够。"
            f"请把数量至少写成 {minimum}"
        )


def _buyer_user_id(row: dict) -> int | None:
    for key in ("userId", "id", "memberUserId"):
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _buyer_user_name(row: dict) -> str:
    for key in ("name", "userName", "account", "phone"):
        text = str(row.get(key) or "").strip()
        if text:
            return text
    return ""


def pick_buyer_user(rows: list[dict], *, user_id: int | None = None) -> dict:
    exact = [row for row in rows if isinstance(row, dict) and _buyer_user_id(row) is not None]
    if user_id is not None:
        matched = [row for row in exact if _buyer_user_id(row) == int(user_id)]
        if not matched:
            candidates = [
                {"userId": _buyer_user_id(row), "name": _buyer_user_name(row)} for row in exact
            ]
            raise AssertionError(f"采购会员下没有 userId={user_id} 的登录用户。候选: {candidates}")
        return matched[0]
    if not exact:
        raise AssertionError("采购会员下没有登录用户，无法代客下单")
    if len(exact) > 1:
        candidates = [
            {"userId": _buyer_user_id(row), "name": _buyer_user_name(row)} for row in exact
        ]
        raise AssertionError(f"采购会员有多个登录用户，请指定 buyer_user_id。候选: {candidates}")
    return exact[0]


def _rewrite_pay_node(node: dict, pay_node: str) -> None:
    if "payNode" in node:
        node["payNode"] = pay_node
    for child in node.get("payNodes") or []:
        if isinstance(child, dict):
            child["payNode"] = pay_node
    for channel in node.get("payChannels") or []:
        if isinstance(channel, dict):
            channel["isDefault"] = 1
            _rewrite_pay_node(channel, pay_node)


def stock_up_products(detail_body: dict) -> list[dict]:
    """从订单详情取出确认备货完成需要的商品行。"""
    data = detail_body.get("data") if isinstance(detail_body.get("data"), dict) else detail_body
    rows: list = []
    if isinstance(data, dict):
        product = data.get("product")
        if isinstance(product, dict):
            rows = product.get("products") or []
        if not rows:
            rows = data.get("products") or data.get("productList") or []
    if not isinstance(rows, list) or not rows:
        raise AssertionError(f"订单详情里没有商品行，无法确认备货完成: {detail_body}")
    products: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        line_id = row.get("orderProductId")
        if line_id in (None, ""):
            line_id = row.get("id")
        product_id = row.get("productId") or row.get("commodityId")
        sku_id = row.get("skuId")
        quantity = row.get("quantity")
        if quantity in (None, ""):
            quantity = row.get("purchaseCount")
        if line_id in (None, "") or product_id in (None, "") or sku_id in (None, "") or quantity in (None, ""):
            raise AssertionError(f"备货商品行缺少字段: {row}")
        products.append(
            {
                "orderProductId": int(line_id),
                "productId": int(product_id),
                "skuId": int(sku_id),
                "quantity": str(quantity),
            }
        )
    if not products:
        raise AssertionError(f"订单详情里没有可备货的商品行: {detail_body}")
    return products


def apply_free_shipping_freight(payload: dict) -> dict:
    """包邮客户代客下单运费必须是 0，否则 37249。"""
    freight = float(payload.get("freight") or 0)
    if freight:
        payload["sumPrice"] = round(float(payload.get("sumPrice") or 0) - freight, 2)
    payload["freight"] = 0
    for product in payload.get("products") or []:
        if isinstance(product, dict):
            product["freightPrice"] = 0
    payments = payload.get("payments") or []
    if payments and isinstance(payments[0], dict):
        payments[0]["payPrice"] = f"{float(payload.get('sumPrice') or 0):.2f}"
    return payload


def apply_account_period_pay(payload: dict) -> dict:
    """销售单改成结算支付-月结（页面上的账期）。"""
    pay_price = ""
    payments = payload.get("payments") or []
    if payments and isinstance(payments[0], dict):
        pay_price = str(payments[0].get("payPrice") or "")
    if not pay_price:
        pay_price = f"{float(payload.get('sumPrice') or 0):.2f}"
    monthly = {
        "interestRate": None,
        "payTypeName": "结算支付",
        "payType": 5,
        "payChannels": [
            {
                "payChannel": 8,
                "payChannelName": "月结",
                "isDefault": 1,
                "interestRate": None,
                "settlementDay": None,
                "canUseQuota": None,
                "orderNode": None,
                "notSelectable": None,
                "payNodes": [{"batchNo": 1, "payNode": "提交订单后", "outerStatusName": "待支付", "payRate": "100"}],
                "accountPeriod": None,
            }
        ],
        "batchNo": 1,
        "payNode": "提交订单后",
        "outerStatusName": "待支付",
        "payRate": "100",
        "payChannel": 8,
        "payChannelName": "月结",
        "isDefault": 1,
        "settlementDay": None,
        "canUseQuota": None,
        "orderNode": None,
        "notSelectable": None,
        "payNodes": [{"batchNo": 1, "payNode": "提交订单后", "outerStatusName": "待支付", "payRate": "100"}],
        "accountPeriod": None,
        "index": 0,
        "payType2": "结算支付",
        "payChannel2": "月结",
        "payPrice": pay_price,
    }
    payload["payments"] = [monthly]
    payload["payType"] = 5
    payload["payChannel"] = 8
    payload["payTypeMessageObj"] = {
        "payType": {
            "payTypeName": "结算支付",
            "payType": 5,
            "payChannels": monthly["payChannels"],
        },
        "payChannel": {
            "payChannel": 8,
            "payChannelName": "月结",
            "payNodes": monthly["payNodes"],
        },
        "interestRate": None,
    }
    return payload


def apply_en_agent_terms(payload: dict) -> None:
    """按英文商城代客下单成功报文修正支付节点和应付货款。"""
    goods = round(
        sum(float(item.get("money") or 0) for item in payload.get("products") or []),
        2,
    )
    for payment in payload.get("payments") or []:
        if not isinstance(payment, dict):
            continue
        payment["payPrice"] = f"{goods:.2f}"
        payment["isDefault"] = 1
        _rewrite_pay_node(payment, EN_PAY_NODE)
    message = payload.get("payTypeMessageObj")
    if isinstance(message, dict):
        for key in ("payType", "payChannel"):
            child = message.get(key)
            if isinstance(child, dict):
                _rewrite_pay_node(child, EN_PAY_NODE)


def supported_status_text() -> str:
    return "、".join(dict.fromkeys(_STATUS_ALIASES.values()))


class OrderSeedService:
    def __init__(self, client: ApiClient | None = None):
        self.client = client or ApiClient(timeout=API_TIMEOUT_SECONDS)
        self.orders = OrderService(self.client)
        self.inquiry = CrmInquiryService(self.client)
        self._sessions: dict[str, AuthContext] = {}

    def login(self, profile: MallOrderProfile) -> AuthContext:
        cached = self._sessions.get(profile.mall)
        if cached is not None:
            return cached
        auth = AuthService(self.client)
        data = auth.login_with_encrypted_password(
            profile.login_phone,
            profile.login_password,
            endpoint=profile.login_endpoint,
        )
        ctx = AuthContext.from_login_data(data)
        self._sessions[profile.mall] = ctx
        return ctx

    def find_customer(
        self,
        ctx: AuthContext,
        profile: MallOrderProfile,
        *,
        name: str,
        member_id: int | None = None,
    ) -> dict:
        base = profile.platform_base_url
        headers = self.inquiry.build_headers(
            ctx,
            referer_path="/memberCenter/customerAbility/customerDeposits/query",
            origin=base,
        )
        payload = {"current": 1, "pageSize": 20, "name": name}
        if member_id is not None:
            payload["memberId"] = int(member_id)
        last_error = None
        for attempt in range(3):
            resp = self.client.request(
                "POST",
                f"{base}/api/member/customer/ability/maintenance/page",
                json_body=payload,
                headers=headers,
                timeout=API_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            body = resp.json()
            try:
                self.orders._assert_success(body, f"查询商城客户 {name}")
            except AssertionError as exc:
                last_error = exc
                time.sleep(1)
                continue
            data = body.get("data") if isinstance(body.get("data"), dict) else {}
            rows = data.get("data") or data.get("records") or []
            exact = [
                row
                for row in rows
                if isinstance(row, dict) and str(row.get("name") or "").strip() == name
            ]
            if member_id is not None:
                by_id = [
                    row
                    for row in (rows if isinstance(rows, list) else [])
                    if isinstance(row, dict)
                    and self.inquiry._to_int(row.get("memberId")) == int(member_id)
                ]
                exact = by_id or exact
            if exact:
                if len(exact) > 1:
                    ids = [row.get("memberId") for row in exact]
                    raise AssertionError(f"客户名称重复 {name}，请在清单里带 member_id。候选: {ids}")
                return exact[0]
            last_error = AssertionError(f"{profile.mall} 商城未找到客户: {name}")
            time.sleep(1)
        raise last_error or AssertionError(f"{profile.mall} 商城未找到客户: {name}")

    def find_sales(self, ctx: AuthContext, profile: MallOrderProfile, name: str) -> dict:
        rows = self.inquiry.query_member_users(
            ctx, platform_base_url=profile.platform_base_url, name=name, page_size=20
        )
        exact = [
            row
            for row in rows
            if str(row.get("name") or "").strip() == name and int(row.get("status") or 0) == 1
        ]
        if not exact:
            raise AssertionError(f"{profile.mall} 商城未找到在职销售: {name}")
        if len(exact) > 1:
            ids = [row.get("userId") for row in exact]
            raise AssertionError(f"销售姓名重复 {name}，候选 userId: {ids}")
        return exact[0]

    def list_buyer_users(
        self,
        ctx: AuthContext,
        profile: MallOrderProfile,
        member_id: int,
    ) -> list[dict]:
        base = profile.platform_base_url.rstrip("/")
        headers = self.inquiry.build_headers(
            ctx,
            referer_path=ORDER_AGENT_REFERER,
            origin=base,
        )
        headers.pop("Content-Type", None)
        resp = self.client.request(
            "GET",
            f"{base}/api/member/customer/ability/maintenance/user/list",
            params={"memberId": int(member_id)},
            headers=headers,
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        body = resp.json()
        self.orders._assert_success(body, f"查询采购会员登录用户 memberId={member_id}")
        data = body.get("data")
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            rows = data.get("data") or data.get("records") or data.get("list") or []
        else:
            rows = []
        return [row for row in rows if isinstance(row, dict)]

    def find_buyer_user(
        self,
        ctx: AuthContext,
        profile: MallOrderProfile,
        *,
        member_id: int,
        buyer_user_id: int | None = None,
    ) -> dict:
        return pick_buyer_user(
            self.list_buyer_users(ctx, profile, member_id),
            user_id=buyer_user_id,
        )

    def assign_sales(
        self,
        ctx: AuthContext,
        profile: MallOrderProfile,
        *,
        customer: dict,
        sales_user_id: int,
        sales_name: str,
    ) -> dict:
        current = str(customer.get("customerManagerName") or "").strip()
        if current == sales_name:
            return {"changed": False, "customer_manager": sales_name}
        validate_id = customer.get("validateId")
        if validate_id in (None, ""):
            raise AssertionError(f"客户 {customer.get('name')} 缺少 validateId，无法设置客户经理")
        payload = {
            "validateId": int(validate_id),
            "customerManagerId": int(sales_user_id),
            "customerManagerName": sales_name,
            "isShowCustomerManager": 1,
            "isShowProductManager": 1,
            "productManagerIds": {},
            "isAllProductManager": 0,
        }
        resp = self.client.request(
            "POST",
            f"{profile.platform_base_url}/api/member/customer/ability/assigned/assign",
            json_body=payload,
            headers=self.inquiry.build_headers(
                ctx,
                referer_path="/memberCenter/customerAbility/manage/memberAssigned",
                origin=profile.platform_base_url,
            ),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        body = resp.json()
        self.orders._assert_success(body, f"设置客户经理 {sales_name}")
        return {
            "changed": True,
            "previous_customer_manager": current or None,
            "customer_manager": sales_name,
        }

    def set_member_free_shipping(
        self,
        ctx: AuthContext,
        profile: MallOrderProfile,
        customer: dict,
        *,
        free_shipping: bool,
    ) -> dict:
        """中文商城会员包邮。POST /api/member/ability/maintenance/updateMemberCustomSetting。"""
        if profile.mall != "cn":
            raise AssertionError("会员包邮只接了中文商城 updateMemberCustomSetting")
        payload = member_free_shipping_payload(customer, free_shipping=free_shipping)
        already = _as_bool(customer.get("isFreeShipping"), False) is bool(free_shipping)
        if already:
            return {"changed": False, "member_id": payload["memberId"], "isFreeShipping": bool(free_shipping)}
        resp = self.client.request(
            "POST",
            profile.url("/api/member/ability/maintenance/updateMemberCustomSetting"),
            json_body=payload,
            headers=self.inquiry.build_headers(
                ctx,
                referer_path="/memberCenter/customerAbility/customerDeposits/query",
                origin=profile.platform_base_url,
            ),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        body = resp.json()
        self.orders._assert_success(body, f"设置会员包邮 memberId={payload['memberId']}")
        return {
            "changed": True,
            "member_id": payload["memberId"],
            "isFreeShipping": bool(free_shipping),
        }

    def _order_ids(self, ctx: AuthContext, profile: MallOrderProfile, customer_name: str) -> set[int]:
        body = self.orders.query_orders(
            ctx,
            member_name=customer_name,
            page_size=20,
            api_url=profile.page_url,
            platform_base_url=profile.platform_base_url,
        )
        data = self.orders._assert_success(body, "查询订单")
        ids: set[int] = set()
        for row in data.get("data") or []:
            if isinstance(row, dict) and row.get("orderId") is not None:
                ids.add(int(row["orderId"]))
        return ids

    def _find_created_order(
        self,
        ctx: AuthContext,
        profile: MallOrderProfile,
        *,
        customer_name: str,
        before_ids: set[int],
    ) -> dict:
        last_rows: list[dict] = []
        for _ in range(8):
            body = self.orders.query_orders(
                ctx,
                member_name=customer_name,
                page_size=20,
                api_url=profile.page_url,
                platform_base_url=profile.platform_base_url,
            )
            data = self.orders._assert_success(body, "查询新订单")
            rows = [row for row in (data.get("data") or []) if isinstance(row, dict)]
            last_rows = rows
            fresh = [row for row in rows if int(row.get("orderId") or 0) not in before_ids]
            if fresh:
                return max(fresh, key=lambda row: int(row.get("orderId") or 0))
            time.sleep(1)
        raise AssertionError(f"下单后未查到新订单，客户={customer_name}，已有订单={sorted(before_ids)}")

    def _load_guest_and_address(
        self,
        ctx: AuthContext,
        profile: MallOrderProfile,
        *,
        customer: dict,
        sku_id: int,
        buyer_user_id: int,
    ) -> tuple[dict, dict]:
        member_id = int(customer["memberId"])
        role_id = int(customer.get("roleId") or ORDER_BUYER_ROLE_ID)
        guest = self.orders.get_guest_commodity(
            ctx,
            buyer_member_id=member_id,
            sku_id=sku_id,
            buyer_role_id=role_id,
            api_url=profile.commodity_url,
            platform_base_url=profile.platform_base_url,
        )
        address = self.orders.get_buyer_receiver_address(
            ctx,
            buyer_member_id=member_id,
            buyer_role_id=role_id,
            buyer_user_id=buyer_user_id,
            api_url=profile.address_url,
            platform_base_url=profile.platform_base_url,
        )
        return guest, address

    def _quantity_for_amount(
        self,
        ctx: AuthContext,
        profile: MallOrderProfile,
        *,
        customer: dict,
        sku_id: int,
        amount: float,
        buyer_user_id: int,
    ) -> int:
        guest, address = self._load_guest_and_address(
            ctx,
            profile,
            customer=customer,
            sku_id=sku_id,
            buyer_user_id=buyer_user_id,
        )
        unit = OrderService._parse_unit_price(guest.get("unitPrice"))
        quantity = 1
        for _ in range(4):
            freight = self.orders.resolve_product_freight(
                ctx,
                guest,
                quantity=quantity,
                address=address,
                platform_base_url=profile.platform_base_url,
            )
            quantity = solve_quantity(unit, freight, amount)
        assert_quantity_allowed(guest, quantity)
        return quantity

    def _build_payload(
        self,
        ctx: AuthContext,
        profile: MallOrderProfile,
        *,
        customer: dict,
        sales: dict,
        buyer_user: dict,
        items: list[OrderLineItem],
        currency_id: int | None = None,
    ) -> dict:
        member_id = int(customer["memberId"])
        role_id = int(customer.get("roleId") or ORDER_BUYER_ROLE_ID)
        buyer_user_id = _buyer_user_id(buyer_user)
        buyer_name = _buyer_user_name(buyer_user) or str(customer.get("name") or "")
        payload = self.orders.build_agent_order_payload(
            ctx,
            buyer_member_id=member_id,
            buyer_member_name=str(customer.get("name") or ""),
            buyer_role_id=role_id,
            buyer_user_id=buyer_user_id,
            buyer_user_name=buyer_name,
            items=items,
            commodity_api_url=profile.commodity_url,
            address_api_url=profile.address_url,
            referer_path=ORDER_AGENT_REFERER,
            platform_base_url=profile.platform_base_url,
        )
        apply_sales(
            payload,
            user_id=int(sales["userId"]),
            name=str(sales.get("name") or ""),
        )
        if customer.get("saleOrgType") not in (None, ""):
            payload["buyerSaleOrgType"] = int(customer["saleOrgType"])
        else:
            payload["buyerSaleOrgType"] = CRM_INQUIRY_BUYER_SALE_ORG_TYPE
        payload["shopId"] = ORDER_SHOP_ID
        resolved_currency = currency_id if currency_id is not None else profile.currency_id
        if resolved_currency is not None:
            payload["currencyId"] = resolved_currency
        if profile.shop_name:
            payload["shopName"] = profile.shop_name
        if profile.shop_classify is not None:
            payload["shopClassify"] = profile.shop_classify
        if profile.trade_mode is not None:
            payload["tradeMode"] = profile.trade_mode
        payload["vendorMemberId"] = ctx.member_id
        products = payload.get("products") or []
        first = products[0] if products else {}
        if isinstance(first, dict):
            if first.get("vendorMemberName"):
                payload["vendorMemberName"] = first["vendorMemberName"]
            if first.get("vendorRoleId") not in (None, ""):
                payload["vendorRoleId"] = first["vendorRoleId"]
        if profile.mall == "en":
            apply_en_agent_terms(payload)
        return payload

    def _upload_contract(self, ctx: AuthContext, profile: MallOrderProfile, order_id: int) -> None:
        contract_file = self.orders.upload_file(
            ctx,
            ORDER_CONTRACT_FILE_PATH,
            api_url=profile.upload_url,
            platform_base_url=profile.platform_base_url,
            file_type=1 if profile.mall == "en" else None,
        )
        contract_body = self.orders.upload_contract(
            ctx,
            order_id=order_id,
            file_url=contract_file["url"],
            file_name=contract_file["fileName"],
            api_url=profile.contract_url,
            platform_base_url=profile.platform_base_url,
        )
        self.orders._assert_success(contract_body, "上传合同")

    def _upload_pay_voucher(self, ctx: AuthContext, profile: MallOrderProfile, order_id: int) -> None:
        voucher_file = self.orders.upload_file(
            ctx,
            ORDER_VOUCHER_FILE_PATH,
            api_url=profile.upload_url,
            platform_base_url=profile.platform_base_url,
            file_type=1 if profile.mall == "en" else None,
        )
        valet_body = self.orders.valet_upload_pay_voucher(
            ctx,
            order_id=order_id,
            voucher_urls=[voucher_file["url"]],
            api_url=profile.valet_url,
            platform_base_url=profile.platform_base_url,
        )
        self.orders._assert_success(valet_body, "代客上传支付凭证")

    def _confirm_pay(self, ctx: AuthContext, profile: MallOrderProfile, *, order_id: int, customer_name: str) -> dict:
        confirm_body = self.orders.confirm_pay(
            ctx,
            order_id=order_id,
            api_url=profile.confirm_url,
            platform_base_url=profile.platform_base_url,
        )
        self.orders._assert_success(confirm_body, "确认支付结果")
        return self._wait_status_name(
            ctx,
            profile,
            order_id=order_id,
            customer_name=customer_name,
            expected=STATUS_STOCK_UP,
        )

    def _confirm_stock_up(
        self,
        ctx: AuthContext,
        profile: MallOrderProfile,
        *,
        order_id: int,
        customer_name: str,
    ) -> dict:
        detail = self.orders.get_order_detail(
            ctx,
            order_id,
            api_url=profile.detail_url,
            platform_base_url=profile.platform_base_url,
        )
        products = stock_up_products(detail)
        body = self.orders.confirm_stock_up(
            ctx,
            order_id=order_id,
            products=products,
            api_url=profile.stock_up_url,
            platform_base_url=profile.platform_base_url,
        )
        self.orders._assert_success(body, "确认备货完成")
        return self._wait_status_name(
            ctx,
            profile,
            order_id=order_id,
            customer_name=customer_name,
            expected=STATUS_PENDING_SHIP,
        )

    def _wait_status_name(
        self,
        ctx: AuthContext,
        profile: MallOrderProfile,
        *,
        order_id: int,
        customer_name: str,
        expected: str,
    ) -> dict:
        last: dict = {}
        for _ in range(8):
            last = self.orders.get_order_by_id(
                ctx,
                order_id=order_id,
                member_name=customer_name,
                max_retries=1,
                interval_seconds=0,
                api_url=profile.page_url,
                platform_base_url=profile.platform_base_url,
            )
            status_name = str(last.get("innerStatusName") or last.get("outerStatusName") or "")
            if status_reached(expected, status_name):
                return last
            time.sleep(1)
        status_name = str(last.get("innerStatusName") or last.get("outerStatusName") or "")
        raise AssertionError(
            f"订单状态未达到 {expected}，实际为 {status_name}，订单号 {last.get('orderNo')}"
        )

    def create_one(self, spec: OrderSeedSpec, *, assign_sales: bool = True) -> dict:
        profile = mall_profile(spec.mall)
        ctx = self.login(profile)
        customer = self.find_customer(
            ctx, profile, name=spec.customer, member_id=spec.member_id
        )
        sales = self.find_sales(ctx, profile, spec.sales)
        buyer_user = self.find_buyer_user(
            ctx,
            profile,
            member_id=int(customer["memberId"]),
            buyer_user_id=spec.buyer_user_id,
        )
        sku_id = spec.sku_id or profile.default_sku_id
        if spec.items:
            line_items = list(spec.items)
            sku_id = line_items[0].sku_id
            quantity = line_items[0].quantity
            buyer_uid = int(_buyer_user_id(buyer_user) or 0)
            for line in line_items:
                guest, _address = self._load_guest_and_address(
                    ctx,
                    profile,
                    customer=customer,
                    sku_id=line.sku_id,
                    buyer_user_id=buyer_uid,
                )
                assert_quantity_allowed(guest, line.quantity)
        elif spec.quantity is not None:
            guest, _address = self._load_guest_and_address(
                ctx,
                profile,
                customer=customer,
                sku_id=sku_id,
                buyer_user_id=int(_buyer_user_id(buyer_user) or 0),
            )
            assert_quantity_allowed(guest, spec.quantity)
            quantity = spec.quantity
            line_items = [OrderLineItem(sku_id=sku_id, quantity=quantity)]
        else:
            quantity = self._quantity_for_amount(
                ctx,
                profile,
                customer=customer,
                sku_id=sku_id,
                amount=float(spec.amount),
                buyer_user_id=int(_buyer_user_id(buyer_user) or 0),
            )
            line_items = [OrderLineItem(sku_id=sku_id, quantity=quantity)]
        free_shipping_result = {"changed": False, "skipped": True}
        if spec.free_shipping:
            free_shipping_result = self.set_member_free_shipping(
                ctx, profile, customer, free_shipping=True
            )
        assign_result = {"changed": False, "customer_manager": spec.sales, "skipped": True}
        if assign_sales:
            assign_result = self.assign_sales(
                ctx,
                profile,
                customer=customer,
                sales_user_id=int(sales["userId"]),
                sales_name=str(sales.get("name") or spec.sales),
            )
        before_ids = self._order_ids(ctx, profile, spec.customer)
        payload = self._build_payload(
            ctx,
            profile,
            customer=customer,
            sales=sales,
            buyer_user=buyer_user,
            items=line_items,
            currency_id=spec.currency_id,
        )
        if _as_bool(customer.get("isFreeShipping"), False):
            apply_free_shipping_freight(payload)
        if spec.pay == PAY_ACCOUNT_PERIOD:
            apply_account_period_pay(payload)
        actual_sum = round(float(payload.get("sumPrice") or 0), 2)
        if spec.amount is not None and abs(actual_sum - spec.amount) > 0.009:
            raise AssertionError(
                f"按目录价算出的订单金额是 {actual_sum}，不是 {spec.amount}"
            )
        create_body = self.orders.create_agent_order(
            ctx,
            payload,
            api_url=profile.create_url,
            referer_path=ORDER_AGENT_REFERER,
            platform_base_url=profile.platform_base_url,
        )
        self.orders._assert_success(create_body, "代客下单")
        row = self._find_created_order(
            ctx, profile, customer_name=spec.customer, before_ids=before_ids
        )
        order_id = int(row["orderId"])
        if spec.status in (
            STATUS_PENDING_PAY,
            STATUS_PENDING_PAY_CONFIRM,
            STATUS_STOCK_UP,
            STATUS_PENDING_SHIP,
        ):
            try:
                self._upload_contract(ctx, profile, order_id)
            except AssertionError:
                if spec.pay != PAY_ACCOUNT_PERIOD:
                    raise
        if spec.pay == PAY_ACCOUNT_PERIOD and spec.status in (
            STATUS_PENDING_PAY_CONFIRM,
            STATUS_STOCK_UP,
            STATUS_PENDING_SHIP,
        ):
            row = self._wait_status_name(
                ctx, profile, order_id=order_id, customer_name=spec.customer, expected=STATUS_STOCK_UP
            )
            if spec.status == STATUS_PENDING_SHIP:
                row = self._confirm_stock_up(
                    ctx, profile, order_id=order_id, customer_name=spec.customer
                )
        elif spec.status == STATUS_PENDING_PAY:
            row = self._wait_status_name(
                ctx, profile, order_id=order_id, customer_name=spec.customer, expected=spec.status
            )
        elif spec.status in (STATUS_PENDING_PAY_CONFIRM, STATUS_STOCK_UP, STATUS_PENDING_SHIP):
            self._upload_pay_voucher(ctx, profile, order_id)
            if spec.status == STATUS_PENDING_PAY_CONFIRM:
                row = self._wait_status_name(
                    ctx,
                    profile,
                    order_id=order_id,
                    customer_name=spec.customer,
                    expected=spec.status,
                )
            else:
                row = self._confirm_pay(
                    ctx, profile, order_id=order_id, customer_name=spec.customer
                )
                if spec.status == STATUS_PENDING_SHIP:
                    row = self._confirm_stock_up(
                        ctx, profile, order_id=order_id, customer_name=spec.customer
                    )
        elif spec.status == STATUS_CANCELLED:
            cancel_body = self.orders.cancel_order(
                ctx,
                order_id=order_id,
                api_url=profile.cancel_url,
                platform_base_url=profile.platform_base_url,
            )
            self.orders._assert_success(cancel_body, "取消订单")
            row = self.orders.get_order_by_id(
                ctx,
                order_id=order_id,
                member_name=spec.customer,
                api_url=profile.page_url,
                platform_base_url=profile.platform_base_url,
            )
        status_name = str(row.get("innerStatusName") or row.get("outerStatusName") or "")
        if not status_reached(spec.status, status_name):
            raise AssertionError(
                f"订单状态未达到 {spec.status}，实际为 {status_name}，订单号 {row.get('orderNo')}"
            )
        actual_amount = row.get("amount")
        # 只指定采购数量时，运费以平台回写的订单金额为准。
        expected_amount = spec.amount if spec.amount is not None else (
            round(float(actual_amount), 2) if actual_amount not in (None, "") else actual_sum
        )
        if spec.amount is not None and actual_amount not in (None, ""):
            if abs(round(float(actual_amount), 2) - expected_amount) > 0.009:
                cleanup = ""
                if spec.status != STATUS_CANCELLED:
                    try:
                        cancel_body = self.orders.cancel_order(
                            ctx,
                            order_id=order_id,
                            reason="造数金额与实单不一致，自动取消",
                            api_url=profile.cancel_url,
                            platform_base_url=profile.platform_base_url,
                        )
                        self.orders._assert_success(cancel_body, "取消金额不一致的订单")
                        cleanup = "这张订单已取消。"
                    except Exception as exc:
                        cleanup = f"尝试取消失败: {exc}"
                raise AssertionError(
                    f"订单金额不一致：期望 {expected_amount}，实际 {actual_amount}，"
                    f"订单号 {row.get('orderNo')}。{cleanup}"
                )
        manager_name = str(row.get("customerManagerName") or "")
        return {
            "ok": True,
            "mall": profile.mall,
            "customer": spec.customer,
            "member_id": customer.get("memberId"),
            "sales": spec.sales,
            "sales_user_id": sales.get("userId"),
            "assign_sales": assign_result,
            "free_shipping": free_shipping_result,
            "amount": expected_amount,
            "actual_amount": actual_amount,
            "buyer_user_id": _buyer_user_id(buyer_user),
            "buyer_user_name": _buyer_user_name(buyer_user) or None,
            "status": spec.status,
            "inner_status_name": row.get("innerStatusName"),
            "outer_status_name": row.get("outerStatusName"),
            "order_customer_manager": manager_name or None,
            "order_id": order_id,
            "order_no": row.get("orderNo"),
            "pay": spec.pay,
            "payment_type_name": row.get("paymentTypeName"),
            "sku_id": sku_id,
            "quantity": quantity,
            "items": [{"sku_id": line.sku_id, "quantity": line.quantity} for line in line_items],
            "freight": payload.get("freight"),
            "currency_id": payload.get("currencyId"),
        }

    def create_many(self, specs: list[OrderSeedSpec], *, assign_sales: bool = True) -> dict:
        results: list[dict] = []
        for index, spec in enumerate(specs, start=1):
            try:
                item = self.create_one(spec, assign_sales=assign_sales)
                item["index"] = index
                results.append(item)
            except Exception as exc:
                results.append(
                    {
                        "ok": False,
                        "index": index,
                        "mall": spec.mall,
                        "customer": spec.customer,
                        "sales": spec.sales,
                        "amount": spec.amount,
                        "quantity": spec.quantity,
                        "status": spec.status,
                        "error": str(exc),
                    }
                )
        return {
            "success": all(item.get("ok") for item in results),
            "total": len(results),
            "failed": sum(1 for item in results if not item.get("ok")),
            "orders": results,
        }

    def preview(self, specs: list[OrderSeedSpec]) -> dict:
        rows = []
        for index, spec in enumerate(specs, start=1):
            profile = mall_profile(spec.mall)
            ctx = self.login(profile)
            customer = self.find_customer(
                ctx, profile, name=spec.customer, member_id=spec.member_id
            )
            sales = self.find_sales(ctx, profile, spec.sales)
            buyer_user = self.find_buyer_user(
                ctx,
                profile,
                member_id=int(customer["memberId"]),
                buyer_user_id=spec.buyer_user_id,
            )
            rows.append(
                {
                    "index": index,
                    "mall": profile.mall,
                    "customer": spec.customer,
                    "member_id": customer.get("memberId"),
                    "buyer_user_id": _buyer_user_id(buyer_user),
                    "buyer_user_name": _buyer_user_name(buyer_user) or None,
                    "current_customer_manager": customer.get("customerManagerName") or None,
                    "sales": spec.sales,
                    "sales_user_id": sales.get("userId"),
                    "amount": spec.amount,
                    "quantity": spec.quantity,
                    "status": spec.status,
                    "sku_id": spec.sku_id or profile.default_sku_id,
                    "items": (
                        [{"sku_id": line.sku_id, "quantity": line.quantity} for line in spec.items]
                        if spec.items
                        else None
                    ),
                    "free_shipping": spec.free_shipping,
                    "is_free_shipping": customer.get("isFreeShipping"),
                }
            )
        return {"dry_run": True, "total": len(rows), "orders": rows}
