"""销售订单转采购（测试/UAT）。

真正的转单不在销售订单列表的 /api/order/vendor/transfer（那是另一套批量转单，
易食包商家角色会 37203）。订单采购员在「订单查询」点转单，进入
/memberCenter/orderAbility/saleOrder/transitionOrder/operate，提交：

  GET  /api/order/vendor/detail?orderId=
  GET  /api/product/commodity/getFormalCommoditySkuUpperCommodity?commoditySkuId=
  GET  /api/srm/supplier/framework/contract/getEffectContract?supplierId=
  POST /api/order/transition/submit

操作人：雷翰（采购员）userId=103853，账号 CRM_INQUIRY_PURCHASER_ACCOUNT。
提交 body.memberRoleId=26（商家采购商）。上游供应商 roleId=25。

供应商确认交期（页面「订单确认中」）：
  POST /api/order/vendor/order/change/deliveryTime
  {"orderId","agree":1,"deliveryTimeList":[{"orderProductId","confirmDeliveryDate"}]}

采购完成（供应商销售单视角，和销售造数同一套备货）：
  POST /api/order/vendor/order/stock/up          # 备货中 → 待确认发货，showStockUp=true
  GET  /api/order/vendor/validate/delivery/product
  POST /api/order/vendor/validate/delivery/confirm  # 待确认发货 → 待确认收货，showDelivery=true
  GET  /api/order/buyer/validate/delivery/short-shipment/products?orderId=
  POST /api/order/buyer/validate/delivery/short-shipment/confirm  # 采购员待发货订单短装确认，少发关剩余
  POST /api/order/buyer/validate/receive/confirm    # 易食包确认收货，bizScene=PURCHASE

确认中取消：
  POST /api/order/buyer/cancel  {"orderId","reason"}
  备货中 showCancel=false，确认交期之后不能点取消。
  易食包商家订单调减到 0 → 已取消：
  GET  /api/order/buyer/reduce/preview?orderId=
  POST /api/order/buyer/reduce  {"orderId","confirmed":false,"products":[{"orderProductId","reduceQuantity","reduceGiftQuantity"}]}

采购退货：完成后 showAfterSales=true，走 AftersaleSeedService.return_purchase。

不要沿用聊天里的 token。生产禁止写入。默认 dry-run。
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta

from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.auth_service import AuthService
from api.services.order_seed import OrderSeedService, OrderSeedSpec, parse_mall, stock_up_products
from api.services.order_service import OrderService
from config.settings import (
    API_TIMEOUT_SECONDS,
    CN_PO_SUPPLIERS,
    CRM_INQUIRY_PURCHASER_ACCOUNT,
    CRM_INQUIRY_PURCHASER_PASSWORD_ENCRYPTED,
    EPAK_INQUIRY_PURCHASER_ACCOUNT,
    EPAK_INQUIRY_PURCHASER_PASSWORD_ENCRYPTED,
    EPAK_LOGIN_PASSWORD_ENCRYPTED,
    EPAK_LOGIN_PHONE,
    EPAK_PLATFORM_BASE_URL,
    LOGIN_PASSWORD_ENCRYPTED,
    LOGIN_PHONE,
    PLATFORM_BASE_URL,
)

EN_PO_VENDOR_MEMBER_ID = 648

YSB_CONSUMER_ROLE_ID = 26
UPSTREAM_ROLE_ID = 25
PREPAY_PAYMENT_METHOD = 1  # SRM_PaymentRulesEnum 预付款（全款预付）
TRANSITION_REFERER = "/memberCenter/orderAbility/saleOrder/transitionOrder/operate"
VENDOR_ORDER_REFERER = "/memberCenter/orderAbility/saleOrder/orderList"
PURCHASE_ORDER_REFERER = "/memberCenter/orderAbility/purchaseOrder/orderList"
SHIP_REFERER = "/memberCenter/orderAbility/saleOrder/readyConfirmDelevedOrder"
RECEIVE_REFERER = "/memberCenter/orderAbility/purchaseOrder/readyReceiveOrder"
SHORT_SHIP_REFERER = "/memberCenter/orderAbility/purchaseOrder/readyDelevedOrder"
DEFAULT_CANCEL_REASON = "毛利看板造数取消"
SHIP_NOTE_IMG = "https://tj-prod.oss-cn-hangzhou.aliyuncs.com/FILENAMEFIXED7777238a5ca847c6b16e396a2692bf05.jpg"
SHIP_QUALITY_IMG = "https://tj-prod.oss-cn-hangzhou.aliyuncs.com/FILENAMEFIXEDbe9f740297ae44e1bb2ad2dfbb712c7a.jpg"
SHIP_LABEL_IMG = "https://tj-prod.oss-cn-hangzhou.aliyuncs.com/FILENAMEFIXEDee74cdcec3d4492a9d15f77207820bc4.jpg"

PO_STATUS_CONFIRMING = "确认中"
PO_STATUS_STOCK_UP = "备货中"
PO_STATUS_PENDING_SHIP = "待确认发货"
PO_STATUS_PENDING_RECEIVE = "待确认收货"
PO_STATUS_DONE = "已完成"
PO_STATUS_CANCELLED = "已取消"
PO_STATUS_RETURN = "退货"

_PO_STATUS_ALIASES = {
    "确认中": PO_STATUS_CONFIRMING,
    "订单确认中": PO_STATUS_CONFIRMING,
    "备货中": PO_STATUS_STOCK_UP,
    "订单备货中": PO_STATUS_STOCK_UP,
    "供应商确认": PO_STATUS_STOCK_UP,
    "确认交期": PO_STATUS_STOCK_UP,
    "待确认发货": PO_STATUS_PENDING_SHIP,
    "待确认收货": PO_STATUS_PENDING_RECEIVE,
    "完成": PO_STATUS_DONE,
    "已完成": PO_STATUS_DONE,
    "取消": PO_STATUS_CANCELLED,
    "已取消": PO_STATUS_CANCELLED,
    "退货": PO_STATUS_RETURN,
    "采购退货": PO_STATUS_RETURN,
}

# 从当前状态推到目标，要依次做的步骤（转单提交本身不在这里）
_STEPS_AFTER_SUBMIT = {
    PO_STATUS_CONFIRMING: (),
    PO_STATUS_STOCK_UP: ("agree_delivery",),
    PO_STATUS_PENDING_SHIP: ("agree_delivery", "stock_up"),
    PO_STATUS_PENDING_RECEIVE: ("agree_delivery", "stock_up", "ship"),
    PO_STATUS_DONE: ("agree_delivery", "stock_up", "ship", "receive"),
    PO_STATUS_CANCELLED: ("cancel",),
    PO_STATUS_RETURN: ("agree_delivery", "stock_up", "ship", "receive", "after_sale"),
}


def parse_po_status(value: str) -> str:
    raw = (value or "").strip()
    found = _PO_STATUS_ALIASES.get(raw)
    if not found:
        raise ValueError(
            f"无法识别采购目标状态 {value!r}，可用："
            f"{sorted(set(_PO_STATUS_ALIASES.values()))}"
        )
    return found


def show_flags(row: dict | None) -> dict:
    row = row or {}
    return {k: row.get(k) for k in sorted(row) if str(k).startswith("show")}


def _positive_int(raw) -> int:
    try:
        value = int(raw or 0)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def vendor_member_id_of(*sources: dict | None) -> int:
    """列表接口常把 vendorMemberId 放空，详情或嵌套 vendor 里才有。"""
    for source in sources:
        if not isinstance(source, dict):
            continue
        value = _positive_int(source.get("vendorMemberId") or source.get("vendor_member_id"))
        if value:
            return value
        nested = source.get("vendor")
        if isinstance(nested, dict):
            value = vendor_member_id_of(nested)
            if value:
                return value
            value = _positive_int(nested.get("memberId"))
            if value:
                return value
    return 0


def configured_supplier_member_id(name: str | None) -> int:
    blob = str(name or "")
    for spec in CN_PO_SUPPLIERS:
        if spec.get("name") and spec["name"] in blob:
            return int(spec["member_id"])
    return 0


def supplier_login_account(phone: str | None, account: str | None) -> str:
    return str(phone or "").strip() or str(account or "").strip()


def lookup_supplier_login(member_id: int, mall: str = "cn") -> dict:
    """转采购只配了字节/银河。采购退货要登单据上的上游时，用会员手机号 + 同一套供应商密文。"""
    from utils.customer_test_data_cleanup import mall_db_config, open_pg_conn

    conn = open_pg_conn(mall_db_config(mall))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, phone, account FROM ms_mc_member WHERE id = %s",
            (int(member_id),),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise AssertionError(f"找不到供应商会员 {member_id}")
    found_id, name, phone, account = row
    login_account = supplier_login_account(phone, account)
    if not login_account:
        raise AssertionError(f"供应商会员 {found_id} {name} 没有登录手机号")
    password = str((CN_PO_SUPPLIERS[0].get("password") if CN_PO_SUPPLIERS else "") or "")
    if not password:
        raise AssertionError("未配置供应商登录密码")
    return {
        "key": f"member-{found_id}",
        "account": login_account,
        "password": password,
        "member_id": int(found_id),
        "supplier_id": 0,
        "name": name or str(found_id),
    }


def build_ship_payload(order_id: int, products: list[dict], quantity: int | None = None) -> dict:
    if not products:
        raise AssertionError("没有待发货商品行")
    rows: list[dict] = []
    for item in products:
        left = item.get("leftCount")
        if left in (None, ""):
            left = item.get("quantity")
        if left in (None, ""):
            raise AssertionError(f"发货商品行缺少数量: {item}")
        ship_qty = left if quantity is None else quantity
        rows.append(
            {
                "orderProductId": int(item["orderProductId"]),
                "productId": int(item["productId"]),
                "skuId": int(item.get("skuId") or 0),
                "quantity": str(item.get("quantity") if item.get("quantity") not in (None, "") else left),
                "deliveryCount": str(ship_qty),
                "giftDeliveryCount": str(item.get("giftLeftCount") or item.get("giftDeliveryCount") or 0),
            }
        )
    return {"orderId": int(order_id), "products": rows}


def current_po_stage(buyer: dict | None, vendor: dict | None) -> str:
    """用买卖双方列表行判断采购单现在停在哪一步。"""
    buyer = buyer or {}
    vendor = vendor or {}
    buyer_name = str(buyer.get("innerStatusName") or buyer.get("outerStatusName") or "")
    vendor_name = str(vendor.get("innerStatusName") or vendor.get("outerStatusName") or "")
    names = buyer_name + vendor_name
    if "取消" in names or "中止" in names:
        return PO_STATUS_CANCELLED
    if "完成" in buyer_name:
        return PO_STATUS_DONE
    if buyer.get("showConfirmReceipt") is True or "待确认收货" in buyer_name or "待确认收货" in names:
        return PO_STATUS_PENDING_RECEIVE
    if "完成" in vendor_name:
        return PO_STATUS_DONE
    if vendor.get("showDelivery") is True or "待确认发货" in vendor_name:
        return PO_STATUS_PENDING_SHIP
    if vendor.get("showStockUp") is True or "备货" in vendor_name or "备货" in buyer_name:
        return PO_STATUS_STOCK_UP
    if "确认中" in names:
        return PO_STATUS_CONFIRMING
    return buyer_name or vendor_name or "未知"


def advance_target_met(target: str, inspect: dict | None) -> bool:
    """实际收货方收货时买家停在待确认收货，按已完成可售后处理。"""
    inspect = inspect or {}
    stage = inspect.get("stage")
    if stage == target:
        return True
    # UAT：买家待确认收货即视为可售后的完成态（供应商侧多为已完成）
    return target == PO_STATUS_DONE and stage == PO_STATUS_PENDING_RECEIVE


def remaining_steps(current: str, target: str) -> tuple[str, ...]:
    wanted = _STEPS_AFTER_SUBMIT[target]
    if target == PO_STATUS_CANCELLED:
        if current == PO_STATUS_CONFIRMING:
            return wanted
        if current == PO_STATUS_STOCK_UP:
            return ("reduce",)
        raise AssertionError(f"当前是{current}，只有确认中或备货中（供应商已确认后）才能取消")
    if current == target:
        return ()
    order = (
        PO_STATUS_CONFIRMING,
        PO_STATUS_STOCK_UP,
        PO_STATUS_PENDING_SHIP,
        PO_STATUS_PENDING_RECEIVE,
        PO_STATUS_DONE,
        PO_STATUS_RETURN,
    )
    if current not in order or target not in order:
        return wanted
    if order.index(current) > order.index(target) and target != PO_STATUS_RETURN:
        raise AssertionError(f"当前已经是{current}，不能再停到{target}")
    done = set(_STEPS_AFTER_SUBMIT.get(current) or ())
    return tuple(step for step in wanted if step not in done)


def with_short_ship_step(
    steps: tuple[str, ...],
    *,
    ship_qty: int | None,
    order_qty: int | None,
) -> tuple[str, ...]:
    """少发：实发小于确认数量时，采购员在待发货订单点短装确认，关掉剩余未发。"""
    if ship_qty is None or order_qty is None:
        return steps
    if int(ship_qty) >= int(order_qty):
        return steps
    if "short_ship" in steps:
        return steps
    rows = list(steps)
    if "receive" in rows:
        rows.insert(rows.index("receive"), "short_ship")
    elif "ship" in rows:
        rows.insert(rows.index("ship") + 1, "short_ship")
    else:
        rows.insert(0, "short_ship")
    return tuple(rows)


class PurchaseFromSalesSeedService:
    def __init__(self, client: ApiClient | None = None, mall: str = "cn"):
        self.client = client or ApiClient(timeout=API_TIMEOUT_SECONDS)
        self.mall = parse_mall(mall)
        self.orders = OrderService(self.client)
        self.sales_seed = OrderSeedService(self.client)

    @property
    def platform_base_url(self) -> str:
        return EPAK_PLATFORM_BASE_URL if self.mall == "en" else PLATFORM_BASE_URL

    @property
    def login_endpoint(self) -> str:
        return "en" if self.mall == "en" else "cn"

    def _purchaser_password(self) -> str:
        if self.mall == "en":
            return EPAK_INQUIRY_PURCHASER_PASSWORD_ENCRYPTED or CRM_INQUIRY_PURCHASER_PASSWORD_ENCRYPTED
        return CRM_INQUIRY_PURCHASER_PASSWORD_ENCRYPTED or EPAK_INQUIRY_PURCHASER_PASSWORD_ENCRYPTED

    def login_purchaser(self) -> AuthContext:
        if self.mall == "en":
            account = EPAK_INQUIRY_PURCHASER_ACCOUNT or CRM_INQUIRY_PURCHASER_ACCOUNT
        else:
            account = CRM_INQUIRY_PURCHASER_ACCOUNT or EPAK_INQUIRY_PURCHASER_ACCOUNT
        password = self._purchaser_password()
        if not account or not password:
            raise AssertionError("未配置订单采购员账号 CRM_INQUIRY_PURCHASER_ACCOUNT")
        return self.login_user_account(account)

    def login_user_account(self, account: str) -> AuthContext:
        password = self._purchaser_password()
        if not account or not password:
            raise AssertionError("未配置订单采购员账号或密码")
        data = AuthService(self.client).login_with_encrypted_password(
            account, password, endpoint=self.login_endpoint
        )
        return AuthContext.from_login_data(data)

    def lookup_member_user(
        self,
        ctx: AuthContext,
        *,
        name: str = "",
        user_id: int | None = None,
    ) -> dict | None:
        body = self._call(
            ctx,
            "GET",
            "/api/member/user/page",
            params={"current": 1, "pageSize": 20, "name": name or ""},
            referer=VENDOR_ORDER_REFERER,
        )
        rows = ((body.get("data") or {}).get("data") or [])
        wanted = int(user_id or 0)
        for row in rows:
            if wanted and int(row.get("userId") or 0) == wanted:
                return row
        if name:
            exact = [row for row in rows if str(row.get("name") or "").strip() == name]
            if exact:
                return exact[0]
        return rows[0] if rows else None

    def login_purchaser_for_order(self, detail: dict) -> AuthContext:
        """转单要单据上的选品经理/采购员操作。询价采购员和选品经理不是同一人时会 37203。"""
        ctx = self.login_purchaser()
        products = ((detail.get("product") or {}).get("products") or detail.get("products") or [])
        line = products[0] if products else {}
        manager_id = int(line.get("selectionManagerId") or detail.get("selectionManagerId") or 0)
        manager_name = str(
            line.get("selectionManagerName") or detail.get("selectionManagerName") or ""
        ).strip()
        if manager_id and int(ctx.user_id) == manager_id:
            return ctx
        if not manager_id and not manager_name:
            return ctx
        row = self.lookup_member_user(ctx, name=manager_name, user_id=manager_id or None) or {}
        account = str(row.get("account") or row.get("phone") or "").strip()
        if not account:
            return ctx
        other = self.login_user_account(account)
        if manager_id and int(other.user_id) != manager_id:
            return ctx
        return other

    def pick_upper_commodity(
        self,
        ctx: AuthContext,
        uppers: list[dict],
        *,
        vendor_member_id: int | None = None,
    ) -> tuple[dict | None, dict | None, dict | None]:
        """优先用有生效框架合同的上游。UAT 上同一 SKU 第一个上游常常没有合同。"""
        if vendor_member_id is not None:
            matched = [
                row for row in uppers if int(row.get("memberId") or 0) == int(vendor_member_id)
            ]
            if not matched:
                return None, None, {
                    "error": f"SKU 上游没有 memberId={vendor_member_id}",
                    "uppers": [
                        {
                            "memberId": r.get("memberId"),
                            "memberName": r.get("memberName"),
                            "supplierId": r.get("supplierId"),
                        }
                        for r in uppers
                    ],
                }
            upper = matched[0]
            supplier_id = int(upper.get("supplierId") or 0)
            contract = self.effect_contract(ctx, supplier_id) if supplier_id else None
            return upper, contract, None
        with_contract = []
        without = []
        for row in uppers:
            supplier_id = int(row.get("supplierId") or 0)
            contract = self.effect_contract(ctx, supplier_id) if supplier_id else None
            if contract:
                with_contract.append((row, contract))
            else:
                without.append(row)
        if with_contract:
            return with_contract[0][0], with_contract[0][1], None
        if without:
            return without[0], None, None
        return None, None, {"error": "SKU 没有正式上游商品，无法新增转单"}

    @staticmethod
    def po_supplier(member_id: int | None = None, key: str | None = None) -> dict:
        if member_id is not None:
            for row in CN_PO_SUPPLIERS:
                if int(row["member_id"]) == int(member_id):
                    return row
        if key:
            for row in CN_PO_SUPPLIERS:
                if row["key"] == key:
                    return row
        raise AssertionError(
            f"未配置转采购上游供应商 member_id={member_id} key={key}。"
            f"已配置: {[(r['key'], r['member_id'], r['name']) for r in CN_PO_SUPPLIERS]}"
        )

    def login_supplier(self, *, member_id: int | None = None, key: str | None = None) -> AuthContext:
        if self.mall == "en":
            if member_id is None:
                member_id = EN_PO_VENDOR_MEMBER_ID
            spec = lookup_supplier_login(int(member_id), mall="en")
        else:
            if member_id is None and not key:
                key = "bytedance"
            try:
                spec = self.po_supplier(member_id=member_id, key=key)
            except AssertionError:
                if member_id is None:
                    raise
                spec = lookup_supplier_login(int(member_id), mall="cn")
        data = AuthService(self.client).login_with_encrypted_password(
            spec["account"], spec["password"], endpoint=self.login_endpoint
        )
        ctx = AuthContext.from_login_data(data)
        if int(ctx.member_id) != int(spec["member_id"]):
            raise AssertionError(
                f"供应商登录会员不一致：期望 {spec['name']} memberId={spec['member_id']}，"
                f"实际 memberId={ctx.member_id} userId={ctx.user_id}"
            )
        return ctx

    def login_ysb(self) -> AuthContext:
        if self.mall == "en":
            phone = EPAK_LOGIN_PHONE or LOGIN_PHONE
            password = EPAK_LOGIN_PASSWORD_ENCRYPTED or LOGIN_PASSWORD_ENCRYPTED
        else:
            phone = LOGIN_PHONE
            password = LOGIN_PASSWORD_ENCRYPTED
        if not phone or not password:
            raise AssertionError("未配置易食包商家账号 LOGIN_PHONE")
        data = AuthService(self.client).login_with_encrypted_password(
            phone, password, endpoint=self.login_endpoint
        )
        return AuthContext.from_login_data(data)

    def _call(
        self,
        ctx: AuthContext,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        scene: str | None = None,
        referer: str = TRANSITION_REFERER,
    ) -> dict:
        heads = self.orders.build_headers(
            ctx,
            referer_path=referer,
            content_type="" if method == "GET" else "application/json",
            platform_base_url=self.platform_base_url,
        )
        if scene:
            heads["bizScene"] = scene
        url = f"{self.platform_base_url.rstrip('/')}{path}"
        if method == "GET":
            resp = self.client.request("GET", url, params=params or {}, headers=heads, timeout=30)
        else:
            resp = self.client.request("POST", url, json_body=json_body or {}, headers=heads, timeout=30)
        return resp.json()

    def sales_order_detail(self, ctx: AuthContext, order_id: int) -> dict:
        body = self._call(
            ctx,
            "GET",
            "/api/order/vendor/detail",
            params={"orderId": order_id},
            referer=f"{TRANSITION_REFERER}?id={order_id}",
        )
        self.orders._assert_success(body, "查询转单销售单")
        return body.get("data") or {}

    def upper_commodities(self, ctx: AuthContext, sku_id: int) -> list[dict]:
        body = self._call(
            ctx,
            "GET",
            "/api/product/commodity/getFormalCommoditySkuUpperCommodity",
            params={"commoditySkuId": sku_id},
        )
        self.orders._assert_success(body, "查询 SKU 上游供应商")
        data = body.get("data") or []
        return data if isinstance(data, list) else []

    def effect_contract(self, ctx: AuthContext, supplier_id: int) -> dict | None:
        body = self._call(
            ctx,
            "GET",
            "/api/srm/supplier/framework/contract/getEffectContract",
            params={"supplierId": supplier_id},
        )
        if body.get("code") != 1000:
            return None
        rows = body.get("data") or []
        if isinstance(rows, list) and rows:
            return rows[0]
        return rows if isinstance(rows, dict) else None

    def build_transition_payload(
        self,
        detail: dict,
        upper: dict,
        contract: dict | None,
        *,
        quantity: float | None = None,
        remark: str = "转单测试",
        payment_method: int = PREPAY_PAYMENT_METHOD,
        delivery_date: str | None = None,
    ) -> dict:
        products = ((detail.get("product") or {}).get("products") or detail.get("products") or [])
        if not products:
            raise AssertionError("销售单没有商品行，无法转单")
        line = products[0]
        qty = float(quantity if quantity is not None else line.get("quantity") or 0)
        if qty <= 0:
            raise AssertionError("转单数量必须大于 0")
        unit_price = upper.get("unitPrice") or {}
        if isinstance(unit_price, dict) and unit_price:
            price = float(next(iter(unit_price.values())))
        else:
            price = float(upper.get("min") or upper.get("max") or 0)
        amount = round(price * qty, 2)
        days = int(upper.get("deliveryDays") or 30)
        delivery = delivery_date or (date.today() + timedelta(days=days)).isoformat()
        vendor_member_id = int(upper["memberId"])
        vendor_role_id = int(upper.get("memberRoleId") or UPSTREAM_ROLE_ID)
        vendor_name = str(upper.get("memberName") or "")
        contract_id = (contract or {}).get("id")
        return {
            "orderId": int(detail["orderId"]),
            "memberRoleId": YSB_CONSUMER_ROLE_ID,
            "orderRemark": remark,
            "supplierPaymentMethod": payment_method,
            "vendors": [
                {
                    "vendorMemberId": vendor_member_id,
                    "vendorMemberName": vendor_name,
                    "vendorRoleId": vendor_role_id,
                    "deliverMode": 1,
                    "consignee": None,
                    "vendorProducts": [
                        {
                            "orderProductId": line.get("orderProductId"),
                            "productId": line.get("productId") or upper.get("commodityId"),
                            "skuId": line.get("skuId") or upper.get("id"),
                            "price": price,
                            "quantity": qty,
                            "isGift": 0,
                            "giftQuantity": 0,
                            "totalQuantity": qty,
                            "totalAmount": amount,
                            "vendorMemberId": vendor_member_id,
                            "vendorMemberName": vendor_name,
                            "vendorRoleId": vendor_role_id,
                            "name": line.get("name") or upper.get("name"),
                            "category": line.get("category") or upper.get("shopCategoryName"),
                            "brand": line.get("brand") or upper.get("brandName"),
                            "unit": line.get("unit") or upper.get("unitName"),
                            "amount": f"{amount:.2f}",
                            "transitionStatus": 1,
                            "orderNo": "——",
                            "deliveryTime": delivery,
                            "supplierContractId": contract_id,
                            "serviceRate": float(upper.get("serviceRate") or 0),
                            "retainedSampleMarking": 0,
                        }
                    ],
                }
            ],
        }

    def submit_transition(self, ctx: AuthContext, payload: dict) -> dict:
        return self._call(
            ctx,
            "POST",
            "/api/order/transition/submit",
            json_body=payload,
            referer=f"{TRANSITION_REFERER}?id={payload.get('orderId')}",
        )

    def confirm_delivery_as_supplier(
        self,
        ctx: AuthContext,
        *,
        order_id: int,
        order_product_id: int,
        confirm_delivery_date: str,
        agree: int = 1,
    ) -> dict:
        payload = {
            "orderId": order_id,
            "agree": agree,
            "deliveryTimeList": [
                {
                    "orderProductId": order_product_id,
                    "confirmDeliveryDate": confirm_delivery_date,
                }
            ],
        }
        body = self._call(
            ctx,
            "POST",
            "/api/order/vendor/order/change/deliveryTime",
            json_body=payload,
            referer="/memberCenter/orderAbility/saleOrder/confirming",
        )
        purchaser = self.login_purchaser()
        confirming = self._call(
            purchaser,
            "POST",
            "/api/order/vendor/order/confirming",
            json_body=payload,
            scene="PURCHASE",
            referer=PURCHASE_ORDER_REFERER,
        )
        if confirming.get("code") == 1000:
            return confirming
        return body

    def _order_detail(
        self,
        ctx: AuthContext,
        paths: tuple[str, ...],
        order_id: int,
        *,
        scene: str | None = None,
        referer: str,
        action: str | None = None,
    ) -> dict:
        last: dict = {}
        for path in paths:
            body = self._call(
                ctx,
                "GET",
                path,
                params={"orderId": int(order_id)},
                scene=scene,
                referer=referer,
            )
            last = body
            data = body.get("data") or {}
            if body.get("code") == 1000 and (
                data.get("orderId") or data.get("orderNo") or data.get("product") or data.get("products")
            ):
                return data
        if action:
            self.orders._assert_success(last, action)
        return (last.get("data") or {}) if last else {}

    def vendor_order_detail(self, ctx: AuthContext, order_id: int) -> dict:
        return self._order_detail(
            ctx,
            ("/api/order/vendor/combination/detail", "/api/order/vendor/detail"),
            order_id,
            referer=VENDOR_ORDER_REFERER,
            action="查询供应商销售单详情",
        )

    def buyer_order_detail(self, ctx: AuthContext, order_id: int) -> dict:
        return self._order_detail(
            ctx,
            ("/api/order/buyer/combination/detail", "/api/order/buyer/detail"),
            order_id,
            scene="PURCHASE",
            referer=PURCHASE_ORDER_REFERER,
        )

    def find_vendor_order(self, ctx: AuthContext, order_no: str) -> dict | None:
        body = self._call(
            ctx,
            "GET",
            "/api/order/vendor/page",
            params={"pageSize": 5, "current": 1, "orderNo": order_no},
            referer=VENDOR_ORDER_REFERER,
        )
        rows = ((body.get("data") or {}).get("data") or [])
        return rows[0] if rows else None

    def find_purchase_by_no(self, ctx: AuthContext, order_no: str) -> dict | None:
        body = self._call(
            ctx,
            "GET",
            "/api/order/buyer/page",
            params={"pageSize": 5, "current": 1, "orderNo": order_no},
            scene="PURCHASE",
            referer=PURCHASE_ORDER_REFERER,
        )
        rows = ((body.get("data") or {}).get("data") or [])
        return rows[0] if rows else None

    def find_purchase_by_id(self, ctx: AuthContext, order_id: int) -> dict | None:
        data = self.buyer_order_detail(ctx, order_id)
        order_no = data.get("orderNo")
        if order_no:
            row = self.find_purchase_by_no(ctx, str(order_no))
            if row:
                return row
        if data.get("orderId"):
            return data
        return None

    def delivery_products(self, ctx: AuthContext, order_id: int) -> list[dict]:
        body = self._call(
            ctx,
            "GET",
            "/api/order/vendor/validate/delivery/product",
            params={"orderId": order_id},
            referer=SHIP_REFERER,
        )
        self.orders._assert_success(body, "查询待发货商品")
        data = body.get("data") or []
        return data if isinstance(data, list) else []

    def stock_up_as_supplier(self, ctx: AuthContext, order_id: int) -> dict:
        detail = self.vendor_order_detail(ctx, order_id)
        products = stock_up_products(detail)
        return self._call(
            ctx,
            "POST",
            "/api/order/vendor/order/stock/up",
            json_body={"orderId": int(order_id), "products": products},
            referer=VENDOR_ORDER_REFERER,
        )

    def confirm_ship_as_supplier(self, ctx: AuthContext, order_id: int, quantity: int | None = None) -> dict:
        products = self.delivery_products(ctx, order_id)
        if quantity is not None:
            return self._ship_by_delivery_apply(ctx, order_id, products, quantity=quantity)
        payload = build_ship_payload(order_id, products, quantity=quantity)
        body = self._call(
            ctx,
            "POST",
            "/api/order/vendor/validate/delivery/confirm",
            json_body=payload,
            referer=SHIP_REFERER,
        )
        if body.get("code") == 1000:
            return body
        return self._ship_by_delivery_apply(ctx, order_id, products, quantity=quantity)

    def list_shipper_address(self, ctx: AuthContext) -> dict:
        body = self._call(
            ctx,
            "GET",
            "/api/logistics/select/listShipperAddress",
            referer=f"{SHIP_REFERER}/detail",
        )
        rows = body.get("data") or []
        if isinstance(rows, list) and rows:
            return rows[0] if isinstance(rows[0], dict) else {}
        return {}

    def confirm_sale_manual_ship(
        self,
        ctx: AuthContext,
        order_id: int,
        *,
        ship_qty: int,
        all_shipments: bool = True,
    ) -> dict:
        """不转单销售单手工发货：填发货数量并勾选全部发货完成（多发/少发）。

        少发（实发 < 订购）勾选全部发货完成后，系统会自动生成关联售后单。
        """
        from datetime import datetime

        products = self.delivery_products(ctx, int(order_id))
        if not products:
            return {"code": 0, "message": "没有待发货商品行"}
        addr = self.list_shipper_address(ctx)
        rows: list[dict] = []
        for item in products:
            row = dict(item)
            row["deliveryCount"] = int(ship_qty)
            row["giftDeliveryCount"] = str(item.get("giftLeftCount") or item.get("giftDeliveryCount") or 0)
            row["isAllShipments"] = 1 if all_shipments else 0
            rows.append(row)
        payload = {
            "deliveryTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "freight": 0,
            "logisticCompanyBOList": [],
            "addresId": int(addr.get("id") or addr.get("addressId") or 0),
            "address": addr.get("fullAddress") or addr.get("address") or "",
            "orderId": int(order_id),
            "products": rows,
            "qualityInspectionReports": [
                {"name": "quality.jpg", "url": SHIP_QUALITY_IMG, "size": "21299"}
            ],
            "productLabels": [
                {"name": "label.jpg", "url": SHIP_LABEL_IMG, "size": "21299"}
            ],
            "deliveryNote": [SHIP_NOTE_IMG],
        }
        return self._call(
            ctx,
            "POST",
            "/api/order/vendor/validate/delivery/confirm",
            json_body=payload,
            referer=f"{SHIP_REFERER}/detail?id={int(order_id)}&batchNo=0",
        )

    def _ship_by_delivery_apply(
        self,
        ctx: AuthContext,
        order_id: int,
        products: list[dict],
        quantity: int | None = None,
    ) -> dict:
        detail = self.vendor_order_detail(ctx, order_id)
        order_no = str(detail.get("orderNo") or "")
        init = self._call(
            ctx,
            "GET",
            "/api/order/delivery/apply/init",
            params={"orderId": int(order_id)},
            referer=f"{SHIP_REFERER}/detail",
        )
        init_data = init.get("data") or []
        init_products = init_data if isinstance(init_data, list) else (
            (init_data.get("products") or init_data.get("productList") or []) if isinstance(init_data, dict) else []
        )
        if not init_products:
            init_products = products
        addresses = self._call(
            ctx,
            "GET",
            "/api/logistics/select/listShipperAddress",
            referer=f"{SHIP_REFERER}/detail",
        )
        addr_rows = addresses.get("data") or []
        addr = addr_rows[0] if isinstance(addr_rows, list) and addr_rows else {}
        apply_products = []
        for item in init_products:
            if not isinstance(item, dict):
                continue
            apply_products.append({
                "orderProductId": int(item.get("orderProductId") or item.get("id")),
                "skuId": int(item.get("skuId") or 0),
                "name": item.get("name") or "",
                "spec": item.get("spec") or "",
                "model": item.get("model") or "",
                "unit": item.get("unit") or "",
                "applyQuantity": int(
                    quantity
                    if quantity is not None
                    else float(item.get("leftCount") or item.get("quantity") or item.get("applyQuantity") or 0)
                ),
                "giftApplyQuantity": 0,
                "giftUnlimited": True,
                "allowOverShip": True,
            })
        saved = self._call(
            ctx,
            "POST",
            "/api/order/delivery/apply/save",
            json_body={
                "orderId": int(order_id),
                "orderNo": order_no,
                "addresId": int(addr.get("id") or addr.get("addressId") or 0),
                "address": addr.get("fullAddress") or addr.get("address") or "",
                "shipTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "freight": 0,
                "uploadFileUrlList": [],
                "deliveryNoteUrlList": [SHIP_NOTE_IMG],
                "qualityInspectionReports": [{"name": "quality.jpg", "url": SHIP_QUALITY_IMG, "size": "21299"}],
                "productLabels": [{"name": "label.jpg", "url": SHIP_LABEL_IMG, "size": "21299"}],
                "products": apply_products,
            },
            referer=f"{SHIP_REFERER}/detail",
        )
        if saved.get("code") != 1000:
            return saved
        apply_id = saved.get("data")
        if isinstance(apply_id, dict):
            apply_id = apply_id.get("id") or apply_id.get("applyId")
        apply_id = int(apply_id)
        apply_no = ""
        apply_detail = self._call(
            ctx,
            "GET",
            "/api/order/delivery/apply/detail",
            params={"applyId": apply_id},
            referer=f"{SHIP_REFERER}/detail",
        )
        apply_no = str((apply_detail.get("data") or {}).get("applyNo") or "")
        # 审批中心异步落单，稍等再捞待办，避免刚保存就找不到
        time.sleep(3)
        approved = self._approve_delivery_apply(order_no, apply_id, apply_no=apply_no)
        if approved.get("code") != 1000:
            return approved
        return self._call(
            ctx,
            "POST",
            "/api/order/delivery/apply/confirm",
            json_body={
                "applyId": apply_id,
                "deliveryTime": datetime.now().strftime("%Y-%m-%d 00:00:00"),
                "logisticCompanyBOList": [],
                "products": [
                    {
                        "orderProductId": int(item["orderProductId"]),
                        "isAllShipments": 1 if quantity is not None else 0,
                    }
                    for item in apply_products
                ],
            },
            referer=f"{SHIP_REFERER}/detail",
        )

    def _approval_candidate_contexts(self) -> list[AuthContext]:
        """UAT 发货审批人常是易嘉欣/张六；英文申请也挂在中文审批中心。"""
        workflow = (
            self
            if self.mall == "cn"
            else PurchaseFromSalesSeedService(ApiClient(timeout=API_TIMEOUT_SECONDS), mall="cn")
        )
        seen: set[int] = set()
        contexts: list[AuthContext] = []
        bootstrap = workflow.login_purchaser()

        def _add(ctx: AuthContext) -> None:
            uid = int(ctx.user_id)
            if uid in seen:
                return
            seen.add(uid)
            contexts.append(ctx)

        # 易嘉欣优先：UAT 中文发货申请多在她待办里
        for name in ("易嘉欣", "张六（采购员）", "张六"):
            row = workflow.lookup_member_user(bootstrap, name=name) or {}
            account = str(row.get("account") or row.get("phone") or "").strip()
            if not account:
                continue
            try:
                _add(workflow.login_user_account(account))
            except Exception:
                continue
        _add(bootstrap)
        return contexts

    def _approve_delivery_apply(self, order_no: str, apply_id: int, apply_no: str = "") -> dict:
        # 英文发货申请的供应链审批挂在中文审批中心。
        workflow = (
            self
            if self.mall == "cn"
            else PurchaseFromSalesSeedService(ApiClient(timeout=API_TIMEOUT_SECONDS), mall="cn")
        )
        apply_id = int(apply_id)
        task = None
        purchaser = None
        contexts = workflow._approval_candidate_contexts()

        def _score(item: dict) -> int:
            name = str(item.get("processName") or "")
            blob = str(item)
            biz_id = item.get("businessDocumentId")
            try:
                biz_match = int(biz_id) == apply_id
            except (TypeError, ValueError):
                biz_match = False
            if "发货" not in name and "FHSQ" not in name and not biz_match:
                return -1
            score = 0
            if biz_match:
                score += 100
            if apply_no and apply_no in name:
                score += 80
            if apply_no and apply_no in blob:
                score += 40
            if order_no and order_no in blob:
                score += 10
            return score

        for _attempt in range(15):
            best: tuple[int, dict, AuthContext] | None = None
            for ctx in contexts:
                page = workflow._call(
                    ctx,
                    "POST",
                    "/api/workflow/newVersion/approvalCenter/page",
                    json_body={
                        "current": 1,
                        "pageSize": 100,
                        "documentType": [],
                        "processCode": "",
                        "processName": "",
                        "applicantUserId": None,
                        "applicationTimeStart": "",
                        "applicationTimeEnd": "",
                        "receiveTimeStart": "",
                        "receiveTimeEnd": "",
                        "tabType": 1,
                    },
                    referer="/memberCenter/approvalAbility/pendingApproval",
                )
                tasks = ((page.get("data") or {}).get("data") or [])
                for item in tasks:
                    score = _score(item)
                    if score < 10:
                        continue
                    if best is None or score > best[0]:
                        best = (score, item, ctx)
            if best is not None:
                task = best[1]
                purchaser = best[2]
                break
            time.sleep(3)
        if not task or purchaser is None:
            return {"code": 0, "message": f"审批中心没有发货申请 {apply_no or order_no}/{apply_id}"}
        task_id = task.get("taskId") or task.get("id")
        workflow._call(
            purchaser,
            "POST",
            "/api/workflow/newVersion/approvalCenter/reviewAndApprove",
            json_body={"taskId": task_id},
            referer="/memberCenter/approvalAbility/pendingApproval",
        )
        return workflow._call(
            purchaser,
            "POST",
            "/api/workflow/newVersion/tasks/complete",
            json_body={"taskId": task_id, "comment": "", "approved": True},
            referer="/memberCenter/approvalAbility/pendingApproval",
        )

    def short_shipment_products(self, ctx: AuthContext, order_id: int) -> list[dict]:
        body = self._call(
            ctx,
            "GET",
            "/api/order/buyer/validate/delivery/short-shipment/products",
            params={"orderId": int(order_id)},
            scene="PURCHASE",
            referer=SHORT_SHIP_REFERER,
        )
        if body.get("code") != 1000:
            return []
        data = body.get("data") or []
        if isinstance(data, dict):
            data = data.get("products") or data.get("productList") or data.get("orderProducts") or []
        return data if isinstance(data, list) else []

    def confirm_short_shipment_as_purchaser(
        self,
        order_id: int,
        order_product_ids: list[int] | None = None,
    ) -> dict:
        """采购员在待发货订单点短装确认，把未发剩余关成少发。"""
        purchaser = self.login_purchaser()
        product_ids = [int(item) for item in (order_product_ids or []) if int(item)]
        if not product_ids:
            products = self.short_shipment_products(purchaser, order_id)
            for item in products:
                if not isinstance(item, dict):
                    continue
                pid = item.get("orderProductId") or item.get("id")
                if pid:
                    product_ids.append(int(pid))
        if not product_ids:
            return {"code": 0, "message": "没有可短装确认的商品行"}
        return self._call(
            purchaser,
            "POST",
            "/api/order/buyer/validate/delivery/short-shipment/confirm",
            json_body={"orderId": int(order_id), "orderProductIds": product_ids},
            scene="PURCHASE",
            referer=SHORT_SHIP_REFERER,
        )

    def confirm_receive_as_buyer(self, ctx: AuthContext, order_id: int, quantity: int | None = None) -> dict:
        body = self._call(
            ctx,
            "POST",
            "/api/order/buyer/validate/receive/confirm",
            json_body={"orderId": int(order_id)},
            scene="PURCHASE",
            referer=RECEIVE_REFERER,
        )
        msg = str(body.get("message") or "")
        actual_receiver = (
            body.get("code") == 37212
            or "实际收货" in msg
            or "actual receiver" in msg.lower()
        )
        if actual_receiver:
            return {"code": 1000, "message": msg or "实际收货方收货，无需确认收货"}
        if body.get("code") == 1000:
            return {"code": 1000, "message": msg or "操作成功"}
        detail = self._order_detail(
            ctx,
            ("/api/order/vendor/combination/detail", "/api/order/vendor/detail", "/api/order/buyer/detail"),
            int(order_id),
            scene="PURCHASE",
            referer=PURCHASE_ORDER_REFERER,
        )
        products = ((detail.get("product") or {}).get("products") or detail.get("products") or [])
        lines = []
        for item in products:
            sku_id = item.get("skuId")
            delivered = item.get("delivered") or item.get("quantity") or 0
            receive_qty = int(quantity) if quantity is not None else int(float(delivered or 0))
            lines.append({
                "orderProductId": item.get("orderProductId"),
                "skuId": sku_id,
                "batchProId": f"1-{sku_id}",
                "receiveQuantity": receive_qty,
            })
        receive_img = "https://zhaliyunoss.esbao.com/FILENAMEFIXEDc6a1ac88c9d049b4b81398b563d2e7dc.jpg"
        batch = self._call(
            ctx,
            "POST",
            "/api/order/buyer/validate/receive/confirm/batch",
            json_body={
                "orderId": int(order_id),
                "batchNo": 1,
                "receiveBill": [{"uid": "rc-po", "status": "done", "name": "receive.jpg", "url": receive_img}],
                "receiveBills": [receive_img],
                "warehousingOrderProductDetailVOS": lines,
            },
            scene="PURCHASE",
            referer=RECEIVE_REFERER,
        )
        batch_msg = str(batch.get("message") or "")
        if batch.get("code") == 1000 and "实际收货" not in batch_msg and "actual receiver" not in batch_msg.lower():
            return {"code": 1000, "message": batch_msg or "操作成功"}
        return batch if batch.get("code") not in (None, 1000) else {
            "code": body.get("code") or 37212,
            "message": batch_msg or msg or "实际收货方未确认收货",
        }

    def cancel_purchase_as_buyer(
        self,
        ctx: AuthContext,
        order_id: int,
        reason: str = DEFAULT_CANCEL_REASON,
    ) -> dict:
        return self._call(
            ctx,
            "POST",
            "/api/order/buyer/cancel",
            json_body={"orderId": int(order_id), "reason": reason},
            scene="PURCHASE",
            referer=PURCHASE_ORDER_REFERER,
        )

    def preview_reduce_as_buyer(self, ctx: AuthContext, order_id: int) -> dict:
        return self._call(
            ctx,
            "GET",
            "/api/order/buyer/reduce/preview",
            params={"orderId": int(order_id)},
            scene="PURCHASE",
            referer=PURCHASE_ORDER_REFERER,
        )

    def reduce_purchase_to_zero_as_buyer(self, ctx: AuthContext, order_id: int) -> dict:
        """易食包商家把采购数量调减到 0，确认后的采购单变成已取消。"""
        preview = self.preview_reduce_as_buyer(ctx, order_id)
        if preview.get("code") != 1000:
            return preview
        data = preview.get("data") or {}
        products = []
        if isinstance(data, list):
            products = data
        elif isinstance(data, dict):
            products = (
                data.get("products")
                or data.get("productList")
                or data.get("orderProducts")
                or ((data.get("product") or {}).get("products") if isinstance(data.get("product"), dict) else None)
                or []
            )
        rows: list[dict] = []
        for item in products:
            if not isinstance(item, dict):
                continue
            pid = item.get("orderProductId") or item.get("id")
            if not pid:
                continue
            qty = item.get("maxReduceQuantity") or item.get("unshippedQuantity") or item.get("quantity") or item.get("leftCount") or 0
            gift = item.get("maxReduceGiftQuantity") or item.get("unshippedGiftQuantity") or item.get("giftQuantity") or item.get("giftLeftCount") or 0
            rows.append(
                {
                    "orderProductId": int(pid),
                    "reduceQuantity": int(float(qty or 0)),
                    "reduceGiftQuantity": int(float(gift or 0)),
                }
            )
        if not rows:
            detail = self.buyer_order_detail(ctx, order_id)
            for item in ((detail.get("product") or {}).get("products") or []):
                pid = item.get("orderProductId")
                if not pid:
                    continue
                rows.append(
                    {
                        "orderProductId": int(pid),
                        "reduceQuantity": int(float(item.get("quantity") or item.get("leftCount") or 0)),
                        "reduceGiftQuantity": int(float(item.get("giftQuantity") or item.get("giftLeftCount") or 0)),
                    }
                )
        if not rows:
            return {"code": 0, "message": "没有可调减的商品行"}
        return self._call(
            ctx,
            "POST",
            "/api/order/buyer/reduce",
            json_body={"orderId": int(order_id), "confirmed": False, "products": rows},
            scene="PURCHASE",
            referer=PURCHASE_ORDER_REFERER,
        )

    def inspect_purchase(self, *, order_id: int | None = None, order_no: str | None = None) -> dict:
        ysb = self.login_ysb()
        buyer = None
        if order_no:
            buyer = self.find_purchase_by_no(ysb, order_no)
        if buyer is None and order_id is not None:
            buyer = self.find_purchase_by_id(ysb, order_id)
        if not buyer:
            return {"ok": False, "step": "inspect", "error": "找不到采购单", "order_id": order_id, "order_no": order_no}
        po_id = int(buyer["orderId"])
        po_no = str(buyer.get("orderNo") or "")
        vendor_name = str(buyer.get("vendorMemberName") or "")
        vendor_member_id = vendor_member_id_of(buyer)
        if not vendor_member_id:
            detail = self.buyer_order_detail(ysb, po_id)
            vendor_member_id = vendor_member_id_of(buyer, detail)
            vendor_name = vendor_name or str((detail or {}).get("vendorMemberName") or "")
        if not vendor_member_id:
            vendor_member_id = configured_supplier_member_id(vendor_name)
        supplier = None
        if vendor_member_id:
            try:
                supplier = self.login_supplier(member_id=vendor_member_id)
            except AssertionError:
                supplier = None
        vendor = self.find_vendor_order(supplier, po_no) if supplier else None
        stage = current_po_stage(buyer, vendor)
        return {
            "ok": True,
            "step": "inspect",
            "order_id": po_id,
            "order_no": po_no,
            "relation_no": buyer.get("relationNo"),
            "stage": stage,
            "amount": buyer.get("amount"),
            "vendor": {
                "memberId": vendor_member_id,
                "memberName": vendor_name,
            },
            "buyer": {
                "innerStatusName": buyer.get("innerStatusName"),
                "outerStatusName": buyer.get("outerStatusName"),
                "flags": show_flags(buyer),
            },
            "supplier_order": {
                "innerStatusName": (vendor or {}).get("innerStatusName"),
                "outerStatusName": (vendor or {}).get("outerStatusName"),
                "flags": show_flags(vendor),
            },
        }

    def _preview_step_payloads(self, inspect: dict, steps: tuple[str, ...], *, cancel_reason: str) -> list[dict]:
        previews: list[dict] = []
        order_id = int(inspect["order_id"])
        vendor_member_id = int((inspect.get("vendor") or {}).get("memberId") or 0)
        supplier_flags = ((inspect.get("supplier_order") or {}).get("flags") or {})
        for step in steps:
            item = {"step": step, "order_id": order_id}
            if step == "agree_delivery":
                item["api"] = "POST /api/order/vendor/order/change/deliveryTime"
                item["note"] = "供应商同意交期；需要 orderProductId + confirmDeliveryDate"
            elif step == "stock_up":
                item["api"] = "POST /api/order/vendor/order/stock/up"
                if supplier_flags.get("showStockUp") is True and vendor_member_id:
                    supplier = self.login_supplier(member_id=vendor_member_id)
                    detail = self.vendor_order_detail(supplier, order_id)
                    item["payload"] = {"orderId": order_id, "products": stock_up_products(detail)}
                else:
                    item["note"] = "当前还不能备货，先完成上一步后再拉商品行"
            elif step == "ship":
                item["api"] = "POST /api/order/vendor/validate/delivery/confirm"
                if supplier_flags.get("showDelivery") is True and vendor_member_id:
                    supplier = self.login_supplier(member_id=vendor_member_id)
                    item["payload"] = build_ship_payload(order_id, self.delivery_products(supplier, order_id))
                else:
                    item["note"] = "备货完成、showDelivery=true 后再 GET validate/delivery/product 拼 payload"
            elif step == "short_ship":
                item["api"] = "POST /api/order/buyer/validate/delivery/short-shipment/confirm"
                item["note"] = "采购员待发货订单短装确认，关闭剩余未发数量"
            elif step == "receive":
                item["api"] = "POST /api/order/buyer/validate/receive/confirm"
                item["payload"] = {"orderId": order_id}
            elif step == "cancel":
                item["api"] = "POST /api/order/buyer/cancel"
                item["payload"] = {"orderId": order_id, "reason": cancel_reason}
            elif step == "reduce":
                item["api"] = "GET /api/order/buyer/reduce/preview + POST /api/order/buyer/reduce"
                item["note"] = "易食包商家把数量调减到 0，采购单变为已取消"
            elif step == "after_sale":
                item["api"] = "POST /api/as/returnGoods/save + 供应商审核/收货"
            previews.append(item)
        return previews

    def advance_existing_purchase(
        self,
        *,
        order_id: int | None = None,
        order_no: str | None = None,
        target_status: str,
        dry_run: bool = True,
        cancel_reason: str = DEFAULT_CANCEL_REASON,
        ship_qty: int | None = None,
    ) -> dict:
        target = parse_po_status(target_status)
        inspect = self.inspect_purchase(order_id=order_id, order_no=order_no)
        if not inspect.get("ok"):
            return inspect
        try:
            steps = remaining_steps(inspect["stage"], target)
        except AssertionError as exc:
            inspect["ok"] = False
            inspect["error"] = str(exc)
            inspect["target"] = target
            return inspect
        po_id = int(inspect["order_id"])
        order_qty = None
        if ship_qty is not None:
            ysb_qty = self.login_ysb()
            detail = self.buyer_order_detail(ysb_qty, po_id)
            products = ((detail.get("product") or {}).get("products") or detail.get("products") or [])
            if products:
                try:
                    order_qty = int(float(products[0].get("quantity") or 0))
                except (TypeError, ValueError):
                    order_qty = None
            steps = with_short_ship_step(steps, ship_qty=ship_qty, order_qty=order_qty)
        result = {
            "ok": True,
            "step": "dry_run" if dry_run else "advance",
            "target": target,
            "current": inspect["stage"],
            "steps": list(steps),
            "inspect": inspect,
            "previews": self._preview_step_payloads(inspect, steps, cancel_reason=cancel_reason),
        }
        if dry_run or not steps:
            return result
        vendor_member_id = int((inspect.get("vendor") or {}).get("memberId") or 0)
        supplier = self.login_supplier(member_id=vendor_member_id) if vendor_member_id else None
        ysb = self.login_ysb()
        executed: list[dict] = []
        for step in steps:
            if step == "agree_delivery":
                if supplier is None:
                    body = {"code": 0, "message": "没有供应商登录态"}
                else:
                    detail = self.vendor_order_detail(supplier, po_id)
                    products = ((detail.get("product") or {}).get("products") or detail.get("products") or [])
                    line = products[0]
                    delivery = str(line.get("confirmDeliveryDate") or line.get("deliveryTime") or (date.today() + timedelta(days=7)).isoformat())
                    body = self.confirm_delivery_as_supplier(
                        supplier,
                        order_id=po_id,
                        order_product_id=int(line["orderProductId"]),
                        confirm_delivery_date=delivery[:10],
                    )
            elif step == "stock_up":
                body = self.stock_up_as_supplier(supplier, po_id)
            elif step == "ship":
                body = self.confirm_ship_as_supplier(supplier, po_id, quantity=ship_qty)
            elif step == "short_ship":
                body = self.confirm_short_shipment_as_purchaser(po_id)
            elif step == "receive":
                body = self.confirm_receive_as_buyer(ysb, po_id, quantity=ship_qty)
            elif step == "cancel":
                body = self.cancel_purchase_as_buyer(ysb, po_id, reason=cancel_reason)
                if body.get("code") != 1000 and supplier is not None:
                    vendor_cancel = self._call(
                        supplier,
                        "POST",
                        "/api/order/vendor/cancel",
                        json_body={"orderId": po_id, "reason": cancel_reason},
                        referer=VENDOR_ORDER_REFERER,
                    )
                    if vendor_cancel.get("code") == 1000:
                        body = vendor_cancel
                    else:
                        body = {
                            "code": vendor_cancel.get("code") or body.get("code") or 0,
                            "message": (
                                "供应商确认后取消失败，已停在确认后状态，未做中止。"
                                f" 买家取消：{body.get('message')}；供应商取消：{vendor_cancel.get('message')}"
                            ),
                        }
            elif step == "reduce":
                reducer = PurchaseFromSalesSeedService(ApiClient(timeout=API_TIMEOUT_SECONDS), mall=self.mall)
                body = reducer.reduce_purchase_to_zero_as_buyer(reducer.login_ysb(), po_id)
            elif step == "after_sale":
                from api.services.aftersale_seed import AftersaleSeedService

                returned = AftersaleSeedService(self.client, mall=self.mall).return_purchase(
                    order_id=po_id,
                    status="售后完成",
                    dry_run=False,
                )
                body = {
                    "code": 1000 if returned.get("ok") else 0,
                    "message": returned.get("error") or returned.get("outer") or "售后完成",
                    "data": returned,
                }
            else:
                body = {"code": 0, "message": f"未实现步骤 {step}"}
            msg = str(body.get("message") or "")
            code = body.get("code")
            try:
                code_num = int(code)
            except (TypeError, ValueError):
                code_num = 0
            if step == "receive" and (code_num == 37212 or "实际收货" in msg):
                body = {"code": 1000, "message": msg or "实际收货方收货，无需确认收货"}
            elif step == "short_ship" and code_num != 1000:
                after_short = self.inspect_purchase(order_id=po_id)
                if after_short.get("stage") in (PO_STATUS_PENDING_RECEIVE, PO_STATUS_DONE):
                    body = {"code": 1000, "message": msg or "已到待确认收货，跳过短装确认"}
            executed.append({"step": step, "code": body.get("code"), "message": body.get("message")})
            if body.get("code") != 1000:
                result["ok"] = False
                result["executed"] = executed
                result["error"] = body.get("message") or f"{step} 失败"
                if step == "after_sale":
                    result["after_sale"] = body.get("data")
                result["inspect_after"] = self.inspect_purchase(order_id=po_id)
                return result
            if step == "after_sale":
                result["after_sale"] = body.get("data")
            if step == "short_ship":
                after_short = self.inspect_purchase(order_id=po_id)
                result["inspect_after_short_ship"] = after_short
                if after_short.get("stage") == PO_STATUS_DONE:
                    result["executed"] = executed
                    result["inspect_after"] = after_short
                    return result
        result["executed"] = executed
        result["inspect_after"] = self.inspect_purchase(order_id=po_id)
        left_at = (result["inspect_after"] or {}).get("stage")
        if left_at and left_at != target:
            if advance_target_met(target, result["inspect_after"]):
                result["note"] = "实际收货方收货：买家待确认收货，供应商已完成，可售后"
            else:
                result["ok"] = False
                result["error"] = result.get("error") or f"目标 {target}，当前停在 {left_at}"
        return result

    def find_purchase_by_relation(self, ctx: AuthContext, relation_no: str) -> dict | None:
        body = self._call(
            ctx,
            "GET",
            "/api/order/buyer/page",
            params={"pageSize": 10, "current": 1, "relationNo": relation_no},
            scene="PURCHASE",
            referer="/memberCenter/orderAbility/purchaseOrder/orderList",
        )
        rows = ((body.get("data") or {}).get("data") or [])
        return rows[0] if rows else None

    def transfer_existing_sales_order(
        self,
        *,
        order_id: int,
        vendor_member_id: int | None = None,
        dry_run: bool = True,
        po_status: str | None = None,
        confirm_delivery: bool = False,
        cancel_reason: str = DEFAULT_CANCEL_REASON,
        ship_qty: int | None = None,
    ) -> dict:
        ctx = self.login_purchaser()
        detail = self.sales_order_detail(ctx, order_id)
        ctx = self.login_purchaser_for_order(detail)
        products = ((detail.get("product") or {}).get("products") or detail.get("products") or [])
        sku_id = int((products[0] or {}).get("skuId") or 0)
        uppers = self.upper_commodities(ctx, sku_id)
        if not uppers:
            return {
                "ok": False,
                "step": "upper_commodity",
                "order_id": order_id,
                "sku_id": sku_id,
                "error": "SKU 没有正式上游商品，无法新增转单",
            }
        upper, contract, upper_err = self.pick_upper_commodity(
            ctx, uppers, vendor_member_id=vendor_member_id
        )
        if upper_err or not upper:
            return {
                "ok": False,
                "step": "upper_commodity",
                "order_id": order_id,
                "sku_id": sku_id,
                **(upper_err or {"error": "SKU 没有正式上游商品，无法新增转单"}),
            }
        payload = self.build_transition_payload(detail, upper, contract)
        target = parse_po_status(po_status) if po_status else None
        if confirm_delivery and target is None:
            target = PO_STATUS_STOCK_UP
        after_submit = _STEPS_AFTER_SUBMIT.get(target) if target else ()
        result = {
            "ok": True,
            "step": "dry_run" if dry_run else "submit",
            "order_no": detail.get("orderNo"),
            "order_id": order_id,
            "sku_id": sku_id,
            "target": target,
            "after_submit": list(after_submit or ()),
            "vendor": {
                "memberId": upper.get("memberId"),
                "memberName": upper.get("memberName"),
                "supplierId": upper.get("supplierId"),
                "serviceRate": upper.get("serviceRate"),
                "contractId": (contract or {}).get("id"),
            },
            "payload": payload,
        }
        if dry_run:
            if after_submit:
                result["note"] = (
                    "预览只拼转单 payload。确认交期/发货/收货要等提交后用 --po-id 推进，"
                    "或 --submit 时带 --po-status。"
                )
            return result
        submitted = self.submit_transition(ctx, payload)
        result["submit"] = submitted
        result["ok"] = submitted.get("code") == 1000
        if not result["ok"]:
            return result
        purchase = self.find_purchase_by_relation(ctx, str(detail.get("orderNo") or ""))
        result["purchase"] = purchase
        if not after_submit or not purchase:
            return result
        advanced = self.advance_existing_purchase(
            order_id=int(purchase["orderId"]),
            order_no=str(purchase.get("orderNo") or ""),
            target_status=target,
            dry_run=False,
            cancel_reason=cancel_reason,
            ship_qty=ship_qty,
        )
        result["advance"] = advanced
        result["ok"] = bool(advanced.get("ok"))
        return result

    def seed_sales_and_transfer(self, spec: OrderSeedSpec, *, dry_run_transfer: bool = True) -> dict:
        sales = self.sales_seed.create_one(spec)
        if not sales.get("ok"):
            return {"ok": False, "step": "sales", "sales": sales}
        transferred = self.transfer_existing_sales_order(
            order_id=int(sales["order_id"]),
            dry_run=dry_run_transfer,
        )
        transferred["sales"] = sales
        return transferred
