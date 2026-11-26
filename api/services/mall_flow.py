"""中文商城销售/转采购/售后造数编排。生产禁止写入。"""
from __future__ import annotations

from api.client import ApiClient
from api.services.aftersale_seed import AftersaleSeedService
from api.services.order_seed import (
    OrderSeedService,
    OrderSeedSpec,
    PAY_ACCOUNT_PERIOD,
    PAY_OFFLINE,
    parse_mall,
    parse_pay,
    parse_status,
)
from api.services.purchase_seed import (
    EN_PO_VENDOR_MEMBER_ID,
    PurchaseFromSalesSeedService,
    parse_po_status,
)
from config.env_loader import resolve_epak_env
from config.settings import (
    API_TIMEOUT_SECONDS,
    CN_PO_SUPPLIER_BYTEDANCE_MEMBER_ID,
    CRM_INQUIRY_BUYER_MEMBER_ID,
    CRM_INQUIRY_BUYER_MEMBER_NAME,
    CRM_INQUIRY_EN_BUYER_MEMBER_ID,
    CRM_INQUIRY_EN_BUYER_MEMBER_NAME,
    CRM_INQUIRY_EN_RELATION_SKU_IDS,
    ORDER_BUYER_MEMBER_ID,
    ORDER_BUYER_MEMBER_NAME,
    ORDER_SKU_ID,
)

DEFAULT_SALES = "国内一组在职"
DEFAULT_CUSTOMER = ORDER_BUYER_MEMBER_NAME
TRANSFER_SKU_ID = 108521
MANUAL_SKU_ID = 108560  # 自营不转单手工发货；107721 商家备货常 37385，采购员可备货
DEFAULT_QUANTITY = 10
ACCOUNT_PERIOD_CUSTOMER = "河南农大迅捷测试技术有限公司"
ACCOUNT_PERIOD_MEMBER_ID = 105124
EN_DEFAULT_CUSTOMER = "AutoOverseas1102115133"
EN_DEFAULT_MEMBER_ID = 774
EN_TRANSFER_SKU_ID = 105283

# UAT 主数据与测试环境不同：客户/SKU/上游都要按环境切。
# CN 统一苏州大满通：8251 对江苏省食品集团运费校验失败(37249)；大满通可线下+账期
UAT_CN_OFFLINE_CUSTOMER = "苏州大满通贸易有限公司"
UAT_CN_OFFLINE_MEMBER_ID = 646
UAT_CN_OFFLINE_BUYER_USER_ID = 678
UAT_CN_ACCOUNT_CUSTOMER = "苏州大满通贸易有限公司"
UAT_CN_ACCOUNT_MEMBER_ID = 646
UAT_CN_ACCOUNT_BUYER_USER_ID = 678
UAT_CN_TRANSFER_SKU_ID = 8251  # PA/PE共挤真空袋，Ethan 有有效合同
UAT_CN_VENDOR_MEMBER_ID = 3441  # Ethan Allen
UAT_CN_QUANTITY = 100
# 英文测试客户(309) 代客单 isStockTransfer=1 无法转单；Rita Limited 可转但 UAT 常 37481(创单最低成本)
UAT_EN_CUSTOMER = "Rita Limited"
UAT_EN_MEMBER_ID = 491
UAT_EN_TRANSFER_SKU_ID = 105261  # Cursor自动化104012，隆基上游价 1.0
UAT_EN_VENDOR_MEMBER_ID = 512  # 隆基绿能
UAT_EN_QUANTITY = 10000


def active_env() -> str:
    try:
        return resolve_epak_env()
    except Exception:
        return "test"


def resolve_seed_customer(
    *,
    mall: str = "cn",
    customer: str = "",
    member_id: int | None = None,
    pay: str = PAY_OFFLINE,
    buyer_user_id: int | None = None,
) -> tuple[str, int | None, int | None]:
    """未指定客户时按环境/支付方式选默认买家。返回 (名称, memberId, buyerUserId)。"""
    pay_kind = parse_pay(pay)
    name = (customer or "").strip()
    env = active_env()
    if mall == "en":
        cn_names = {
            DEFAULT_CUSTOMER,
            ACCOUNT_PERIOD_CUSTOMER,
            UAT_CN_OFFLINE_CUSTOMER,
            UAT_CN_ACCOUNT_CUSTOMER,
            CRM_INQUIRY_BUYER_MEMBER_NAME or "",
            "江苏省食品集团有限公司",
            "衢州白马投资有限公司",
        }
        if not name or name in cn_names:
            if env == "uat":
                return UAT_EN_CUSTOMER, member_id or UAT_EN_MEMBER_ID, buyer_user_id
            return EN_DEFAULT_CUSTOMER, member_id or EN_DEFAULT_MEMBER_ID, buyer_user_id
        if env == "uat":
            return name, member_id or UAT_EN_MEMBER_ID, buyer_user_id
        return name, member_id or EN_DEFAULT_MEMBER_ID, buyer_user_id
    if env == "uat":
        if pay_kind == PAY_ACCOUNT_PERIOD and (
            not name or name in (DEFAULT_CUSTOMER, UAT_CN_OFFLINE_CUSTOMER, ACCOUNT_PERIOD_CUSTOMER)
        ):
            # 不要沿用线下客户的 buyer_user_id
            return (
                UAT_CN_ACCOUNT_CUSTOMER,
                member_id or UAT_CN_ACCOUNT_MEMBER_ID,
                UAT_CN_ACCOUNT_BUYER_USER_ID,
            )
        if not name or name in (
            DEFAULT_CUSTOMER,
            ACCOUNT_PERIOD_CUSTOMER,
            CRM_INQUIRY_BUYER_MEMBER_NAME or "",
            "江苏省食品集团有限公司",
        ):
            return (
                UAT_CN_OFFLINE_CUSTOMER,
                member_id or UAT_CN_OFFLINE_MEMBER_ID,
                buyer_user_id or UAT_CN_OFFLINE_BUYER_USER_ID,
            )
        return name, member_id, buyer_user_id
    if pay_kind == PAY_ACCOUNT_PERIOD and (not name or name == DEFAULT_CUSTOMER):
        return ACCOUNT_PERIOD_CUSTOMER, member_id or ACCOUNT_PERIOD_MEMBER_ID, buyer_user_id
    if not name or name == DEFAULT_CUSTOMER:
        return DEFAULT_CUSTOMER, member_id or ORDER_BUYER_MEMBER_ID, buyer_user_id
    return name, member_id, buyer_user_id


class MallFlowService:
    def __init__(self, client: ApiClient | None = None, mall: str = "cn"):
        self.client = client or ApiClient(timeout=API_TIMEOUT_SECONDS)
        self.mall = parse_mall(mall)
        self.sales = OrderSeedService(self.client)
        self.purchase = PurchaseFromSalesSeedService(self.client, mall=self.mall)
        self.aftersale = AftersaleSeedService(self.client, mall=self.mall)

    def _fresh(self) -> "MallFlowService":
        return MallFlowService(ApiClient(timeout=API_TIMEOUT_SECONDS), mall=self.mall)

    def _defaults(self) -> dict:
        env = active_env()
        if self.mall == "en":
            if env == "uat":
                return {
                    "customer": UAT_EN_CUSTOMER,
                    "member_id": UAT_EN_MEMBER_ID,
                    "sku_id": UAT_EN_TRANSFER_SKU_ID,
                    "vendor_member_id": UAT_EN_VENDOR_MEMBER_ID,
                    "quantity": UAT_EN_QUANTITY,
                    "buyer_user_id": None,
                    "over_qty": int(UAT_EN_QUANTITY * 1.2),
                    "under_qty": int(UAT_EN_QUANTITY * 0.7),
                }
            return {
                "customer": EN_DEFAULT_CUSTOMER,
                "member_id": EN_DEFAULT_MEMBER_ID,
                "sku_id": EN_TRANSFER_SKU_ID,
                "vendor_member_id": EN_PO_VENDOR_MEMBER_ID,
                "quantity": DEFAULT_QUANTITY,
                "buyer_user_id": None,
                "over_qty": 12,
                "under_qty": 7,
            }
        if env == "uat":
            return {
                "customer": UAT_CN_OFFLINE_CUSTOMER,
                "member_id": UAT_CN_OFFLINE_MEMBER_ID,
                "sku_id": UAT_CN_TRANSFER_SKU_ID,
                "vendor_member_id": UAT_CN_VENDOR_MEMBER_ID,
                "quantity": UAT_CN_QUANTITY,
                "buyer_user_id": UAT_CN_OFFLINE_BUYER_USER_ID,
                "over_qty": int(UAT_CN_QUANTITY * 1.2),
                "under_qty": int(UAT_CN_QUANTITY * 0.7),
            }
        return {
            "customer": DEFAULT_CUSTOMER,
            "member_id": ORDER_BUYER_MEMBER_ID,
            "sku_id": TRANSFER_SKU_ID,
            "vendor_member_id": CN_PO_SUPPLIER_BYTEDANCE_MEMBER_ID,
            "quantity": DEFAULT_QUANTITY,
            "buyer_user_id": None,
            "over_qty": 12,
            "under_qty": 7,
        }

    def seed_sale(
        self,
        *,
        status: str,
        customer: str = DEFAULT_CUSTOMER,
        sales: str = DEFAULT_SALES,
        sku_id: int = TRANSFER_SKU_ID,
        quantity: int = DEFAULT_QUANTITY,
        member_id: int | None = None,
        buyer_user_id: int | None = None,
        assign_sales: bool = False,
        pay: str = PAY_OFFLINE,
    ) -> dict:
        defaults = self._defaults()
        customer, member_id, buyer_user_id = resolve_seed_customer(
            mall=self.mall,
            customer=customer,
            member_id=member_id,
            pay=pay,
            buyer_user_id=buyer_user_id or defaults.get("buyer_user_id"),
        )
        spec = OrderSeedSpec(
            mall=self.mall,
            customer=customer,
            sales=sales,
            status=parse_status(status),
            sku_id=sku_id or defaults["sku_id"],
            quantity=quantity or defaults.get("quantity") or DEFAULT_QUANTITY,
            member_id=member_id,
            buyer_user_id=buyer_user_id,
            pay=parse_pay(pay),
        )
        created = self.sales.create_one(spec, assign_sales=assign_sales)
        created["action"] = "sale"
        return created

    def transfer_sale(
        self,
        *,
        order_id: int | None = None,
        order_no: str | None = None,
        po_status: str,
        vendor_member_id: int | None = None,
        dry_run: bool = False,
        ship_qty: int | None = None,
    ) -> dict:
        if not order_id:
            if not order_no:
                return {"ok": False, "error": "转单需要 --order-id 或 --order-no"}
            ysb = self.purchase.login_ysb()
            row = self.purchase.find_vendor_order(ysb, order_no) or {}
            if not row.get("orderId"):
                return {"ok": False, "error": f"找不到销售单 {order_no}"}
            order_id = int(row["orderId"])
        return self.purchase.transfer_existing_sales_order(
            order_id=int(order_id),
            vendor_member_id=vendor_member_id or self._defaults()["vendor_member_id"],
            dry_run=dry_run,
            po_status=parse_po_status(po_status),
            ship_qty=ship_qty,
        )

    def seed_sale_and_po(
        self,
        *,
        po_status: str,
        customer: str = DEFAULT_CUSTOMER,
        sales: str = DEFAULT_SALES,
        sku_id: int = 0,
        quantity: int = 0,
        member_id: int | None = None,
        vendor_member_id: int | None = None,
        assign_sales: bool = False,
        dry_run: bool = False,
        ship_qty: int | None = None,
        pay: str = PAY_OFFLINE,
        buyer_user_id: int | None = None,
    ) -> dict:
        defaults = self._defaults()
        sale = self.seed_sale(
            status="订单备货中",
            customer=customer,
            sales=sales,
            sku_id=sku_id or defaults["sku_id"],
            quantity=quantity or defaults.get("quantity") or DEFAULT_QUANTITY,
            member_id=member_id,
            assign_sales=assign_sales,
            pay=pay,
            buyer_user_id=buyer_user_id or defaults.get("buyer_user_id"),
        )
        if not sale.get("ok"):
            return {"ok": False, "step": "sale", "sale": sale}
        transferred = self._fresh().transfer_sale(
            order_id=int(sale["order_id"]),
            po_status=po_status,
            vendor_member_id=vendor_member_id or defaults["vendor_member_id"],
            dry_run=dry_run,
            ship_qty=ship_qty,
        )
        transferred["sale"] = sale
        transferred["action"] = "sale-po"
        return transferred

    def return_sale(self, **kwargs) -> dict:
        result = self.aftersale.return_sale(**kwargs)
        result["action"] = "sale-return"
        return result

    def return_purchase(self, **kwargs) -> dict:
        result = self.aftersale.return_purchase(**kwargs)
        result["action"] = "po-return"
        return result

    def seed_sale_manual_diff(
        self,
        *,
        kind: str,
        customer: str = "",
        sales: str = DEFAULT_SALES,
        sku_id: int = 0,
        quantity: int = 0,
        member_id: int | None = None,
        buyer_user_id: int | None = None,
        assign_sales: bool = False,
        over_qty: int = 0,
        under_qty: int = 0,
        pay: str = PAY_OFFLINE,
    ) -> dict:
        """不转单销售单：手工发货多发/少发（填发货数量 + 勾选全部发货完成）。

        少发会自动生成关联售后单。用自营 SKU，默认 ORDER_SKU_ID。
        """
        qty = quantity or DEFAULT_QUANTITY
        sku = sku_id or MANUAL_SKU_ID
        over = over_qty or max(int(qty * 1.2), qty + 1)
        under = under_qty or max(int(qty * 0.7), 1)
        label = (kind or "").strip()
        if label in ("多发", "超发", "over"):
            ship_qty = over
            kind_name = "多发"
        elif label in ("少发", "under"):
            ship_qty = under
            kind_name = "少发"
        else:
            return {"ok": False, "error": f"无法识别手工发货场景 {kind!r}，可用：多发 / 少发"}

        # 自营单备货完成须采购员操作；商家账号常报 37385
        sale = self.seed_sale(
            status="订单备货中",
            customer=customer,
            sales=sales,
            sku_id=sku,
            quantity=qty,
            member_id=member_id,
            buyer_user_id=buyer_user_id,
            assign_sales=assign_sales,
            pay=pay,
        )
        if not sale.get("ok"):
            return {"ok": False, "action": "sale-diff", "kind": kind_name, "step": "sale", "sale": sale}

        order_id = int(sale["order_id"])
        order_no = str(sale.get("order_no") or "")
        purchaser = self.purchase.login_purchaser()
        from api.services.order_seed import stock_up_products

        detail = self.purchase.vendor_order_detail(purchaser, order_id)
        stock_body = self.purchase._call(
            purchaser,
            "POST",
            "/api/order/vendor/order/stock/up",
            json_body={"orderId": order_id, "products": stock_up_products(detail)},
            referer="/memberCenter/orderAbility/saleOrder/orderList",
        )
        if stock_body.get("code") != 1000:
            return {
                "ok": False,
                "action": "sale-diff",
                "kind": kind_name,
                "step": "stock_up",
                "sale": sale,
                "stock_up": stock_body,
                "error": stock_body.get("message"),
            }

        shipped = self.purchase.confirm_sale_manual_ship(
            purchaser, order_id, ship_qty=ship_qty, all_shipments=True
        )
        ok = shipped.get("code") == 1000
        ysb = self.purchase.login_ysb()
        row = self.purchase.find_vendor_order(ysb, order_no) or {}
        related_as = None
        if kind_name == "少发" and ok:
            related_as = self._find_auto_aftersale(ysb, order_id=order_id, order_no=order_no)
        return {
            "ok": ok,
            "action": "sale-diff",
            "kind": kind_name,
            "path": "手工发货",
            "confirm_qty": qty,
            "ship_qty": ship_qty,
            "sale": sale,
            "order_id": order_id,
            "order_no": order_no,
            "inner": row.get("innerStatusName"),
            "outer": row.get("outerStatusName"),
            "stock_up": stock_body,
            "ship": shipped,
            "after_sale": related_as,
            "error": None if ok else shipped.get("message"),
        }

    def _find_auto_aftersale(self, ctx, *, order_id: int, order_no: str) -> dict | None:
        """少发/多发后系统可能生成关联单：多发常见「原单号-A」；少发看售后页或详情 afterSaleNo。"""
        import time

        for _ in range(6):
            for candidate in (f"{order_no}-A", f"{order_no}-B", order_no):
                row = self.purchase.find_vendor_order(ctx, candidate) or {}
                dig = str(row.get("digest") or "")
                if row.get("orderNo") and (
                    candidate != order_no
                    or "多发" in dig
                    or "少发" in dig
                    or row.get("afterSaleNo")
                ):
                    if str(row.get("orderNo")) == order_no and candidate == order_no and not row.get("afterSaleNo"):
                        continue
                    return {
                        "order_no": row.get("orderNo"),
                        "order_id": row.get("orderId"),
                        "digest": dig,
                        "inner": row.get("innerStatusName"),
                        "outer": row.get("outerStatusName"),
                        "from": "vendor_page",
                    }
            try:
                detail = self.purchase.vendor_order_detail(ctx, order_id)
            except Exception:
                detail = {}
            nested = detail.get("afterSale") if isinstance(detail.get("afterSale"), dict) else {}
            as_no = detail.get("afterSaleNo") or detail.get("asOrderNo") or nested.get("orderNo")
            if as_no:
                return {"order_no": as_no, "from": "detail"}
            time.sleep(1)
        return None

    def seed_full(
        self,
        *,
        customer: str = DEFAULT_CUSTOMER,
        sales: str = DEFAULT_SALES,
        sku_id: int = 0,
        quantity: int = 0,
        member_id: int | None = None,
        vendor_member_id: int | None = None,
        assign_sales: bool = False,
        return_count: int = 1,
        as_status: str = "售后完成",
        dry_run: bool = False,
        pay: str = PAY_OFFLINE,
        buyer_user_id: int | None = None,
    ) -> dict:
        defaults = self._defaults()
        created = self.seed_sale_and_po(
            po_status="已完成",
            customer=customer,
            sales=sales,
            sku_id=sku_id or defaults["sku_id"],
            quantity=quantity or defaults.get("quantity") or DEFAULT_QUANTITY,
            member_id=member_id,
            vendor_member_id=vendor_member_id or defaults["vendor_member_id"],
            assign_sales=assign_sales,
            dry_run=dry_run,
            pay=pay,
            buyer_user_id=buyer_user_id,
        )
        inspect = created.get("inspect_after") or (created.get("advance") or {}).get("inspect_after") or {}
        purchase = created.get("purchase") or {}
        po_id = int(purchase.get("orderId") or (created.get("advance") or {}).get("order_id") or inspect.get("order_id") or 0)
        po_no = str(purchase.get("orderNo") or inspect.get("order_no") or "")
        if not po_id:
            inspect = self.purchase.find_purchase_by_relation(
                self.purchase.login_ysb(), str(created.get("sale", {}).get("order_no") or "")
            ) or {}
            po_id = int(inspect.get("orderId") or 0)
            po_no = str(inspect.get("orderNo") or po_no)
        after_sale_ready = str(inspect.get("stage") or "") in ("待确认收货", "已完成")
        if dry_run or (not created.get("ok") and not after_sale_ready) or not po_id:
            created["action"] = "full"
            return created
        returned = self.return_purchase(
            order_id=po_id or None,
            order_no=po_no or None,
            status=as_status,
            return_count=return_count,
            dry_run=False,
        )
        return {
            "ok": bool(returned.get("ok") and (created.get("ok") or after_sale_ready)),
            "action": "full",
            "sale": created.get("sale"),
            "purchase": {
                "order_id": po_id,
                "order_no": po_no,
                "transfer": created,
            },
            "after_sale": returned,
        }

    def seed_po_diff_scenario(
        self,
        *,
        kind: str,
        customer: str = DEFAULT_CUSTOMER,
        sales: str = DEFAULT_SALES,
        sku_id: int = 0,
        quantity: int = 0,
        member_id: int | None = None,
        vendor_member_id: int | None = None,
        assign_sales: bool = False,
        dry_run: bool = False,
        over_qty: int = 0,
        under_qty: int = 0,
        pay: str = PAY_OFFLINE,
        buyer_user_id: int | None = None,
    ) -> dict:
        """新造销售单转采购：正常确认 / 多发 / 少发 / 供应商确认后取消。不改已有单据。"""
        defaults = self._defaults()
        sku_id = sku_id or defaults["sku_id"]
        quantity = quantity or defaults.get("quantity") or DEFAULT_QUANTITY
        vendor_member_id = vendor_member_id or defaults["vendor_member_id"]
        over_qty = over_qty or defaults.get("over_qty") or max(int(quantity * 1.2), quantity + 1)
        under_qty = under_qty or defaults.get("under_qty") or max(int(quantity * 0.7), 1)
        label = (kind or "").strip()
        if label in ("正常", "正常确认", "normal"):
            created = self.seed_sale_and_po(
                po_status="已完成",
                customer=customer,
                sales=sales,
                sku_id=sku_id,
                quantity=quantity,
                member_id=member_id,
                vendor_member_id=vendor_member_id,
                assign_sales=assign_sales,
                dry_run=dry_run,
                ship_qty=quantity,
                pay=pay,
                buyer_user_id=buyer_user_id,
            )
            created["action"] = "po-diff"
            created["kind"] = "正常确认"
            created["confirm_qty"] = quantity
            created["complete_qty"] = quantity
            return created
        if label in ("多发", "超发", "over"):
            created = self.seed_sale_and_po(
                po_status="已完成",
                customer=customer,
                sales=sales,
                sku_id=sku_id,
                quantity=quantity,
                member_id=member_id,
                vendor_member_id=vendor_member_id,
                assign_sales=assign_sales,
                dry_run=dry_run,
                ship_qty=over_qty,
                pay=pay,
                buyer_user_id=buyer_user_id,
            )
            created["action"] = "po-diff"
            created["kind"] = "多发"
            created["confirm_qty"] = quantity
            created["complete_qty"] = over_qty
            return created
        if label in ("少发", "under"):
            created = self.seed_sale_and_po(
                po_status="已完成",
                customer=customer,
                sales=sales,
                sku_id=sku_id,
                quantity=quantity,
                member_id=member_id,
                vendor_member_id=vendor_member_id,
                assign_sales=assign_sales,
                dry_run=dry_run,
                ship_qty=under_qty,
                pay=pay,
                buyer_user_id=buyer_user_id,
            )
            created["action"] = "po-diff"
            created["kind"] = "少发"
            created["confirm_qty"] = quantity
            created["complete_qty"] = under_qty
            return created
        if label in ("取消", "cancel"):
            created = self.seed_sale_and_po(
                po_status="备货中",
                customer=customer,
                sales=sales,
                sku_id=sku_id,
                quantity=quantity,
                member_id=member_id,
                vendor_member_id=vendor_member_id,
                assign_sales=assign_sales,
                dry_run=dry_run,
                pay=pay,
                buyer_user_id=buyer_user_id,
            )
            created["action"] = "po-diff"
            created["kind"] = "取消"
            created["confirm_qty"] = quantity
            if dry_run or not created.get("ok"):
                return created
            purchase = created.get("purchase") or {}
            po_id = int(purchase.get("orderId") or (created.get("advance") or {}).get("order_id") or 0)
            po_no = str(purchase.get("orderNo") or "")
            if not po_id:
                inspect = self.purchase.find_purchase_by_relation(
                    self.purchase.login_ysb(), str(created.get("sale", {}).get("order_no") or "")
                ) or {}
                po_id = int(inspect.get("orderId") or 0)
                po_no = str(inspect.get("orderNo") or po_no)
            cancelled = self._fresh().purchase.advance_existing_purchase(
                order_id=po_id or None,
                order_no=po_no or None,
                target_status="已取消",
                dry_run=False,
            )
            inspect_after = (cancelled.get("inspect_after") or cancelled.get("inspect") or {})
            left_at = inspect_after.get("stage") or "备货中"
            done = bool(cancelled.get("ok")) and left_at == "已取消"
            return {
                "ok": done,
                "action": "po-diff",
                "kind": "取消",
                "confirm_qty": quantity,
                "cancelled": done,
                "left_at": left_at,
                "sale": created.get("sale"),
                "purchase": created.get("purchase") or {
                    "orderId": po_id,
                    "orderNo": po_no,
                },
                "advance": created.get("advance"),
                "cancel": cancelled,
                "error": None if done else cancelled.get("error"),
                "note": None if done else "供应商确认后调减到 0 未成功，新单未中止、未改历史单",
            }
        return {"ok": False, "error": f"无法识别差额场景 {kind!r}，可用：正常确认 / 多发 / 少发 / 取消"}

    def create_en_customer(self, *, sales: str = DEFAULT_SALES) -> dict:
        """测试环境新建英文海外客户并开通商城账号。不改已有客户。"""
        from datetime import datetime

        from api.auth_context import AuthContext
        from api.services.auth_service import AuthService
        from api.services.crm_customer_service import CrmCustomerService
        from api.services.crm_inquiry_service import CrmInquiryService
        from api.services.order_seed import mall_profile
        from config.settings import (
            CRM_DEFAULT_FOLLOW_USER_ID,
            CRM_DEFAULT_FOLLOW_USER_NAME,
            LOGIN_PASSWORD_ENCRYPTED,
            LOGIN_PHONE,
            PLATFORM_BASE_URL,
        )
        from scripts.seed_gross_margin_new_old import (
            assert_en_opened,
            ensure_address,
            wait_en_unregistered,
        )

        if self.mall != "en":
            return {"ok": False, "error": "create_en_customer 只用于英文商城"}
        stamp = datetime.now().strftime("%m%d%H%M%S")
        company = f"AutoOverseas{stamp}"
        phone = f"199{stamp[-8:]}"[:11]
        contact_phone = f"198{stamp[-8:]}"[:11]
        email = f"os{stamp}@example.com"
        client = ApiClient(timeout=API_TIMEOUT_SECONDS)
        crm = CrmCustomerService(client)
        crm_ctx = AuthContext.from_login_data(
            AuthService(client).login_with_encrypted_password(
                LOGIN_PHONE, LOGIN_PASSWORD_ENCRYPTED, endpoint="cn"
            )
        )
        follow_id = int(CRM_DEFAULT_FOLLOW_USER_ID)
        follow_name = CRM_DEFAULT_FOLLOW_USER_NAME
        users = CrmInquiryService(client).query_member_users(
            crm_ctx, platform_base_url=PLATFORM_BASE_URL, name=sales, page_size=20
        )
        exact = [
            row
            for row in users
            if str(row.get("name") or "").strip() == sales and int(row.get("status") or 0) == 1
        ]
        if exact:
            follow_id = int(exact[0].get("userId") or follow_id)
            follow_name = str(exact[0].get("name") or sales)
        payload = {
            "mainProduct": "Packaging materials",
            "mainBusiness": "Food packaging",
            "targetSalesMarketCodes": ["840"],
            "targetSalesMarketNames": ["美国"],
            "customerBusinessCardUrls": [],
            "customerBusinessCardNames": [],
            "overseasDetailAddress": "123 Main St, New York, NY 10001",
            "remark": "英文商城订单造数，非协同客户",
            "purchasePreferenceCode": 3,
            "importRecordCode": 2,
            "importCountryCodes": [],
            "importCountryNames": [],
            "customsOrderCode": 2,
            "customsRecordAttachmentUrls": [],
            "customsRecordAttachmentNames": [],
            "customerTypeCode": 2,
            "customerGradeCode": 0,
            "companyName": company,
            "followUserAssignType": 2,
            "businessTypeCode": 1,
            "businessSubTypeCode": 101,
            "annualTurnover": "1000",
            "companyPeopleNum": "100",
            "email": email,
            "countryCode": "840",
            "country": "美国",
            "followUserId": follow_id,
            "followUserName": follow_name,
            "contactPersonSaveOrUpdateReq": {
                "name": f"{company}联系人",
                "phone": contact_phone,
                "email": email,
                "countryCode": "840",
                "country": "美国",
            },
        }
        save_body = crm.save_customer(crm_ctx, payload)
        crm.assert_ok(save_body, action=f"en_customer_save:{company}")
        customer_id = crm.extract_saved_customer_id(save_body) or crm.find_id_by_company_name(crm_ctx, company)
        if not customer_id:
            return {"ok": False, "error": f"未解析到 CRM id: {save_body}", "company": company}
        seed = OrderSeedService(ApiClient(timeout=API_TIMEOUT_SECONDS))
        pending = wait_en_unregistered(seed, company)
        member_id = int(pending["memberId"])
        crm.refresh_customer_before_open(crm_ctx, customer_id=int(customer_id), company_name=company)
        opened = crm.open_account(
            crm_ctx,
            customer_id=int(customer_id),
            phone=phone,
            email=email,
            source_mall_type=2,
        )
        crm.assert_ok(opened, action=f"en_open:{company}")
        assert_en_opened(seed, company, member_id)
        record = {"company": company, "member_id": member_id}
        ensure_address(seed, seed.login(mall_profile("en")), {"mall": "en", "phone": phone}, record)
        return {
            "ok": True,
            "company": company,
            "customer_id": int(customer_id),
            "member_id": member_id,
            "buyer_user_id": record.get("buyer_user_id"),
            "phone": phone,
            "email": email,
            "follow": {"id": follow_id, "name": follow_name},
        }

    def seed_board(self, **kwargs) -> dict:
        """新造：销售单、转单供应商确认、转单完成、采购退货/多发/少发/取消。无销售退货。不改已有单。"""
        common = {
            "customer": kwargs.get("customer") or self._defaults()["customer"],
            "sales": kwargs.get("sales") or DEFAULT_SALES,
            "sku_id": kwargs.get("sku_id") or self._defaults()["sku_id"],
            "quantity": kwargs.get("quantity") or DEFAULT_QUANTITY,
            "member_id": kwargs.get("member_id"),
            "vendor_member_id": kwargs.get("vendor_member_id") or self._defaults()["vendor_member_id"],
            "assign_sales": bool(kwargs.get("assign_sales")),
        }
        sale_kwargs = {k: v for k, v in common.items() if k != "vendor_member_id"}
        rows: list[dict] = []

        def _run(kind: str, runner):
            try:
                item = runner()
            except Exception as exc:
                item = {"ok": False, "error": str(exc), "kind": kind}
            rows.append({"kind": kind, "item": item})
            return item

        _run("销售单", lambda: self._fresh().seed_sale(status="订单备货中", **sale_kwargs))
        _run("供应商确认", lambda: self._fresh().seed_sale_and_po(po_status="备货中", **common))
        _run("采购完成", lambda: self._fresh().seed_sale_and_po(po_status="已完成", **common))
        for kind in ("多发", "少发"):
            item = _run(kind, lambda k=kind: self._fresh().seed_po_diff_scenario(kind=k, **common))
            purchase = item.get("purchase") if isinstance(item.get("purchase"), dict) else {}
            inspect = item.get("inspect_after") or (item.get("advance") or {}).get("inspect_after") or {}
            po_id = int(purchase.get("orderId") or purchase.get("order_id") or inspect.get("order_id") or 0)
            po_no = str(purchase.get("orderNo") or purchase.get("order_no") or inspect.get("order_no") or "")
            if po_id or po_no:
                returned = self._fresh().return_purchase(
                    order_id=po_id or None,
                    order_no=po_no or None,
                    status="售后完成",
                    return_count=1,
                    dry_run=False,
                )
                item["after_sale"] = returned
                item["ok"] = bool(item.get("ok") and returned.get("ok"))
                if not returned.get("ok"):
                    item["error"] = item.get("error") or returned.get("error")
        _run("取消", lambda: self._fresh().seed_po_diff_scenario(kind="取消", **common))
        return {
            "ok": all(bool((row.get("item") or {}).get("ok")) for row in rows),
            "action": "board",
            "mall": self.mall,
            "customer": common["customer"],
            "orders": rows,
        }

    def seed_pack(self, **kwargs) -> dict:
        """新造一套：销售单、销售退货、采购完成+采购退货、多发、少发、取消。不改已有单。"""
        common = {
            "customer": kwargs.get("customer") or self._defaults()["customer"],
            "sales": kwargs.get("sales") or DEFAULT_SALES,
            "sku_id": kwargs.get("sku_id") or self._defaults()["sku_id"],
            "quantity": kwargs.get("quantity") or DEFAULT_QUANTITY,
            "member_id": kwargs.get("member_id"),
            "vendor_member_id": kwargs.get("vendor_member_id") or self._defaults()["vendor_member_id"],
            "assign_sales": bool(kwargs.get("assign_sales")),
        }
        sale_kwargs = {k: v for k, v in common.items() if k != "vendor_member_id"}
        rows: list[dict] = []
        sale = self._fresh().seed_sale(status="订单备货中", **sale_kwargs)
        rows.append({"kind": "销售单", "item": sale})
        try:
            sale_src = self._fresh().seed_sale(status="订单备货中", **sale_kwargs)
        except Exception as exc:
            sale_src = {"ok": False, "error": str(exc)}
        sale_return = {"ok": False, "error": sale_src.get("error") or "销售单未建成"}
        if sale_src.get("ok"):
            sale_return = self._fresh().return_sale(
                order_id=int(sale_src["order_id"]),
                status="售后完成",
                return_count=1,
                dry_run=False,
            )
            sale_return["sale"] = sale_src
        rows.append({"kind": "销售退货", "item": sale_return})
        try:
            rows.append({"kind": "采购退货", "item": self._fresh().seed_full(**common)})
        except Exception as exc:
            rows.append({"kind": "采购退货", "item": {"ok": False, "error": str(exc)}})
        for kind in ("多发", "少发", "取消"):
            try:
                rows.append({"kind": kind, "item": self._fresh().seed_po_diff_scenario(kind=kind, **common)})
            except Exception as exc:
                rows.append({"kind": kind, "item": {"ok": False, "error": str(exc), "kind": kind}})
        return {
            "ok": all(bool((row.get("item") or {}).get("ok")) for row in rows),
            "action": "pack",
            "mall": self.mall,
            "orders": rows,
        }

    def seed_po_diff_all(self, **kwargs) -> dict:
        rows = []
        ok = True
        for kind in ("多发", "少发", "取消"):
            item = self._fresh().seed_po_diff_scenario(kind=kind, **kwargs)
            rows.append(item)
            if not item.get("ok"):
                ok = False
        return {"ok": ok, "action": "po-diff-all", "orders": rows}

    def seed_suite(
        self,
        *,
        pay: str,
        customer: str = "",
        sales: str = DEFAULT_SALES,
        sku_id: int = 0,
        quantity: int = 0,
        member_id: int | None = None,
        vendor_member_id: int | None = None,
        assign_sales: bool = False,
        as_status: str = "售后完成",
        buyer_user_id: int | None = None,
        over_qty: int = 0,
        under_qty: int = 0,
    ) -> dict:
        """新造正常确认/超发/少发/取消/采购售后。不改已有单。"""
        defaults = self._defaults()
        qty = quantity or defaults.get("quantity") or DEFAULT_QUANTITY
        common = {
            "customer": customer,
            "sales": sales,
            "sku_id": sku_id or defaults["sku_id"],
            "quantity": qty,
            "member_id": member_id,
            "vendor_member_id": vendor_member_id or defaults["vendor_member_id"],
            "assign_sales": bool(assign_sales),
            "pay": pay,
            # buyer_user_id 交给 resolve_seed_customer 按支付方式选，避免线下账号串到账期客户
            "buyer_user_id": buyer_user_id,
        }
        over = over_qty or defaults.get("over_qty") or max(int(qty * 1.2), qty + 1)
        under = under_qty or defaults.get("under_qty") or max(int(qty * 0.7), 1)
        rows = []
        for kind in ("正常确认", "多发", "少发", "取消"):
            try:
                item = self._fresh().seed_po_diff_scenario(
                    kind=kind, **common, over_qty=over, under_qty=under
                )
            except Exception as exc:
                item = {"ok": False, "kind": kind, "error": str(exc)}
            rows.append(item)
        try:
            after_sale = self._fresh().seed_full(
                **{k: v for k, v in common.items() if k != "pay"},
                pay=pay,
                as_status=as_status,
            )
        except Exception as exc:
            after_sale = {"ok": False, "error": str(exc)}
        after_sale["kind"] = "采购售后"
        rows.append(after_sale)
        summary = [scenario_brief(item) for item in rows]
        return {
            "ok": all(bool(row.get("ok")) for row in rows),
            "action": "suite",
            "mall": self.mall,
            "env": active_env(),
            "pay": parse_pay(pay),
            "sales": sales,
            "summary": summary,
            "orders": rows,
        }

    def seed_suite_both(self, **kwargs) -> dict:
        sets = []
        for pay in (PAY_OFFLINE, PAY_ACCOUNT_PERIOD):
            try:
                sets.append(self._fresh().seed_suite(pay=pay, **kwargs))
            except Exception as exc:
                sets.append({
                    "ok": False,
                    "action": "suite",
                    "mall": self.mall,
                    "env": active_env(),
                    "pay": parse_pay(pay),
                    "error": str(exc),
                    "summary": [],
                })
        return {
            "ok": all(bool(item.get("ok")) for item in sets),
            "action": "suite-both",
            "mall": self.mall,
            "env": active_env(),
            "summary": [
                {
                    "mall": self.mall,
                    "pay": item.get("pay"),
                    "ok": item.get("ok"),
                    "rows": item.get("summary"),
                    "error": item.get("error"),
                }
                for item in sets
            ],
            "sets": sets,
        }

    def seed_suite_malls(self, *, malls: list[str] | tuple[str, ...] = ("cn", "en"), **kwargs) -> dict:
        """中文/英文各跑账期+线下一套。不改已有单。"""
        sets = []
        for mall in malls:
            svc = MallFlowService(ApiClient(timeout=API_TIMEOUT_SECONDS), mall=mall)
            try:
                sets.append(svc.seed_suite_both(**kwargs))
            except Exception as exc:
                sets.append({
                    "ok": False,
                    "action": "suite-both",
                    "mall": mall,
                    "env": active_env(),
                    "error": str(exc),
                    "summary": [],
                })
        return {
            "ok": all(bool(item.get("ok")) for item in sets),
            "action": "suite-malls",
            "env": active_env(),
            "summary": [
                {
                    "mall": item.get("mall"),
                    "ok": item.get("ok"),
                    "pays": item.get("summary"),
                    "error": item.get("error"),
                }
                for item in sets
            ],
            "sets": sets,
        }


def scenario_brief(item: dict | None) -> dict:
    item = item or {}
    sale = item.get("sale") or {}
    purchase = item.get("purchase") if isinstance(item.get("purchase"), dict) else {}
    after = item.get("after_sale") or {}
    inspect = (
        item.get("inspect_after")
        or (item.get("advance") or {}).get("inspect_after")
        or (purchase.get("transfer") or {}).get("inspect_after")
        or ((purchase.get("transfer") or {}).get("advance") or {}).get("inspect_after")
        or {}
    )
    cancel = item.get("cancel") or {}
    cancel_inspect = (cancel.get("inspect_after") or {}) if isinstance(cancel, dict) else {}
    return {
        "ok": item.get("ok"),
        "kind": item.get("kind") or item.get("action"),
        "sale_no": sale.get("order_no") or sale.get("orderNo"),
        "sale_id": sale.get("order_id") or sale.get("orderId"),
        "po_no": (
            purchase.get("orderNo")
            or purchase.get("order_no")
            or inspect.get("order_no")
            or cancel_inspect.get("order_no")
        ),
        "po_id": (
            purchase.get("orderId")
            or purchase.get("order_id")
            or inspect.get("order_id")
            or cancel_inspect.get("order_id")
        ),
        "pay": sale.get("pay"),
        "payment_type_name": sale.get("payment_type_name"),
        "manager": sale.get("order_customer_manager") or sale.get("sales"),
        "customer": sale.get("customer"),
        "stage": inspect.get("stage") or cancel_inspect.get("stage") or after.get("stage") or after.get("inner"),
        "apply_no": after.get("apply_no"),
        "error": (
            item.get("error")
            or after.get("error")
            or (item.get("submit") or {}).get("message")
            or (item.get("advance") or {}).get("error")
            or ((purchase.get("transfer") or {}).get("submit") or {}).get("message")
            or ((purchase.get("transfer") or {}).get("error"))
        ),
    }
