"""销售代客退货 / 采购退货（测试/UAT）。

采购：易食包 POST /api/as/returnGoods/save，上游 submitVerify + confirmVerify，
采购商 returnDeliveryGoods，上游 confirmReturnReceiveGoods，必要时退款。
销售代客：易食包 POST /api/as/returnGoods/agent/save，易食包作为卖方提交/确认/发货/收货。

生产禁止写入。不要沿用聊天里的 token。
"""
from __future__ import annotations

from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.order_service import OrderService
from api.services.purchase_seed import PurchaseFromSalesSeedService
from config.settings import API_TIMEOUT_SECONDS, ORDER_SHOP_ID, ORDER_VOUCHER_FILE_PATH

AS_SAVED = "待提交"
AS_CONFIRM_APPLY = "待确认申请单"
AS_DELIVER = "待发货"
AS_RECEIVE = "待收货"
AS_REFUND = "待退款"
AS_DONE = "售后完成"

_AS_ALIASES = {
    "待提交": AS_SAVED,
    "待提交审核": AS_SAVED,
    "待确认申请单": AS_CONFIRM_APPLY,
    "待确认": AS_CONFIRM_APPLY,
    "待发货": AS_DELIVER,
    "待退货发货": AS_DELIVER,
    "采购商退货发货": AS_DELIVER,
    "待收货": AS_RECEIVE,
    "待确认收货": AS_RECEIVE,
    "待确认退货收货": AS_RECEIVE,
    "待退款": AS_REFUND,
    "售后完成": AS_DONE,
    "已确认售后完成": AS_DONE,
    "完成": AS_DONE,
}

_AS_STEPS = {
    AS_SAVED: ("save",),
    AS_CONFIRM_APPLY: ("save", "submit"),
    AS_DELIVER: ("save", "submit", "confirm"),
    AS_RECEIVE: ("save", "submit", "confirm", "deliver"),
    AS_REFUND: ("save", "submit", "confirm", "deliver", "receive"),
    AS_DONE: ("save", "submit", "confirm", "deliver", "receive", "refund"),
}

YSB_SUPPLIER_MEMBER_ID = 6
YSB_SUPPLIER_ROLE_ID = 13
YSB_SUPPLIER_NAME = "江苏易食包数字科技有限公司"
PURCHASE_ADD_REF = "/memberCenter/afterServiceAbility/returnApplication/returnPrSubmit/add"
SALE_ADD_REF = "/memberCenter/afterServiceAbility/returnApplication/returnSubmit/add"
SALE_VALET_REF = "/memberCenter/afterServiceAbility/returnManage/returnValetApply/index"


def parse_as_status(value: str) -> str:
    raw = (value or "").strip()
    found = _AS_ALIASES.get(raw)
    if not found:
        raise ValueError(
            f"无法识别售后目标状态 {value!r}，可用："
            f"{sorted(set(_AS_ALIASES.values()))}"
        )
    return found


def first_list(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "records", "list", "rows"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
    return []


def pick_after_sale_order(rows: list, order_no: str) -> dict | None:
    for item in rows:
        if str(item.get("orderNo") or "") == order_no:
            return item
        blob = str(item.get("orderNo") or "") + str(item.get("digest") or "")
        if order_no in blob:
            return item
    return rows[0] if rows else None


def build_return_line(order: dict, product: dict, *, order_id: int, order_no: str, return_count: int) -> dict:
    sku = int(product.get("skuId") or product.get("goodsId") or 0)
    record_id = int(
        product.get("orderRecordId")
        or product.get("orderProductId")
        or product.get("productId")
        or 0
    )
    qty = float(product.get("quantity") or product.get("purchaseCount") or 0)
    max_ret = float(product.get("maxReturnOrReplaceCount") or qty or 0)
    ret = min(int(return_count), int(max_ret) if max_ret >= 1 else int(return_count))
    if ret < 1:
        ret = 1
    price = str(product.get("price") or "1.00")
    amount = str(product.get("amount") or "")
    paid = str(product.get("paidAmount") or amount)
    spec = product.get("spec") or product.get("type") or ""
    name = product.get("name") or product.get("productName") or ""
    tax_flag = 1 if product.get("tax") in (True, 1, "1") else 0
    return {
        "productId": str(sku),
        "goodsId": sku,
        "skuId": sku,
        "processKey": None,
        "productNo": str(sku),
        "name": name,
        "category": product.get("category") or "",
        "spec": spec,
        "quantity": qty,
        "isGift": int(product.get("isGift") or 0),
        "giftQuantity": str(product.get("giftQuantity") or "0"),
        "delivered": str(product.get("delivered") or qty),
        "giftDelivered": str(product.get("giftDelivered") or "0"),
        "couponZeroQuantity": str(product.get("couponZeroQuantity") or "0"),
        "price": price,
        "amount": amount,
        "totalIntegral": str(product.get("totalIntegral") or "0.00"),
        "paidAmount": paid,
        "paidIntegral": str(product.get("paidIntegral") or "0.00"),
        "tax": tax_flag,
        "taxRate": product.get("taxRate") or 0,
        "priceType": product.get("priceType") or 1,
        "exchangeCount": str(product.get("exchangeCount") or "0"),
        "giftExchangeCount": str(product.get("giftExchangeCount") or "0"),
        "giftReturnCount": str(product.get("giftReturnCount") or "0"),
        "maintainCount": str(product.get("maintainCount") or "0"),
        "returnAmount": str(product.get("returnAmount") or "0.00"),
        "returnIntegral": str(product.get("returnIntegral") or "0.00"),
        "quotedProductNo": "",
        "quotedName": "",
        "quotedSpec": "",
        "quotedCategory": "",
        "quotedBrand": "",
        "currencyVO": {"id": None, "currencyName": None, "symbol": None, "name": None, "fullName": None},
        "currencyId": None,
        "organizeName": None,
        "buyerOrganizeName": None,
        "userName": None,
        "projectCode": None,
        "projectName": None,
        "welfareAmount": None,
        "detailVirtualList": None,
        "model": product.get("model") or "",
        "discountAveragePrice": str(product.get("discountAveragePrice") or "0.00"),
        "actualReturnDiscountAmount": str(product.get("actualReturnDiscountAmount") or "0.00"),
        "maxReturnOrReplaceCount": str(product.get("maxReturnOrReplaceCount") or qty),
        "purchasePrice": price,
        "orderNo": order_no,
        "orderId": order_id,
        "orderType": 3,
        "contractId": order.get("contractId") or 0,
        "contractNo": order.get("contractNo") or "",
        "skuPic": product.get("logo") or product.get("skuPic") or "",
        "productName": name,
        "purchaseCount": qty,
        "purchaseAmount": float(product.get("amount") or 0),
        "payAmount": paid,
        "type": spec,
        "isHasTax": tax_flag,
        "brand": product.get("brand") or "",
        "unit": product.get("unit") or "",
        "orderRecordId": record_id,
        "returnCount": ret,
        "purchaseSinglePoint": 0,
        "spotPriceType": None,
        "payList": [],
    }


def current_as_stage(detail: dict | None) -> str:
    data = detail or {}
    inner = str(data.get("innerStatusName") or "")
    outer = str(data.get("outerStatusName") or "")
    names = inner + outer
    if "售后完成" in names or "已确认售后完成" in inner:
        return AS_DONE
    if "待退款" in names or "未退款" in names:
        return AS_REFUND
    if "收货" in names:
        return AS_RECEIVE
    if "发货" in names:
        return AS_DELIVER
    if "待提交" in inner:
        return AS_SAVED
    if "待确认" in names:
        return AS_CONFIRM_APPLY
    return AS_SAVED if not names else names


class AftersaleSeedService:
    def __init__(self, client: ApiClient | None = None, mall: str = "cn"):
        self.client = client or ApiClient(timeout=API_TIMEOUT_SECONDS)
        self.purchase = PurchaseFromSalesSeedService(self.client, mall=mall)
        self.orders = OrderService(self.client)

    def _call(self, ctx, method, path, **kwargs):
        return self.purchase._call(ctx, method, path, **kwargs)

    def after_sale_page(
        self,
        ctx: AuthContext,
        *,
        order_no: str,
        vendor_member_id: int | None = None,
        vendor_role_id: int | None = None,
        scene: str | None = None,
        referer: str = PURCHASE_ADD_REF,
    ) -> dict:
        params = {
            "current": 1,
            "pageSize": 16,
            "orderNo": order_no,
            "orderType": 3,
            "afterSalesType": 3,
        }
        if vendor_member_id:
            params["vendorMemberId"] = vendor_member_id
        if vendor_role_id:
            params["vendorRoleId"] = vendor_role_id
        return self._call(
            ctx,
            "GET",
            "/api/order/common/after/sale/page",
            params=params,
            scene=scene,
            referer=referer,
        )

    def agent_after_sale_page(
        self,
        ctx: AuthContext,
        *,
        buyer_member_id: int,
        buyer_role_id: int = 21,
        order_no: str = "",
        order_type: int = 0,
        after_sales_type: int = 3,
        referer: str = SALE_VALET_REF,
    ) -> dict:
        """代客销售售后：先选采购会员，再拉可退货商品。

        对应页面 returnValetApply；销售单至少到待确认收货。
        """
        params: dict = {
            "current": 1,
            "pageSize": 16,
            "buyerMemberId": int(buyer_member_id),
            "buyerRoleId": int(buyer_role_id),
            "orderType": int(order_type),
            "afterSalesType": int(after_sales_type),
        }
        if order_no:
            params["orderNo"] = order_no
        return self._call(
            ctx,
            "GET",
            "/api/order/common/agent/after/sale/page",
            params=params,
            referer=referer,
        )

    def find_agent_member(
        self,
        ctx: AuthContext,
        *,
        name: str,
        site_id: int = 1,
        referer: str = SALE_VALET_REF,
    ) -> dict | None:
        body = self._call(
            ctx,
            "GET",
            "/api/member/manage/order/agent/members",
            params={"name": name, "siteId": site_id},
            referer=referer,
        )
        rows = body.get("data") or []
        if isinstance(rows, dict):
            rows = rows.get("data") or rows.get("records") or []
        if not isinstance(rows, list):
            return None
        exact = [r for r in rows if str(r.get("name") or r.get("memberName") or "").strip() == name]
        return (exact or rows or [None])[0]

    def pick_goods(self, page_body: dict, order_no: str) -> tuple[dict | None, dict | None]:
        rows = first_list(page_body.get("data"))
        if not rows and isinstance(page_body.get("data"), dict):
            rows = page_body["data"].get("data") or page_body["data"].get("records") or []
        order = pick_after_sale_order(rows if isinstance(rows, list) else [], order_no)
        products = (order or {}).get("products") if isinstance(order, dict) else None
        product = products[0] if isinstance(products, list) and products else None
        return order, product

    def list_receiver(self, ctx: AuthContext, referer: str) -> dict:
        body = self._call(
            ctx,
            "GET",
            "/api/logistics/select/listReceiverAddress",
            referer=referer,
        )
        rows = body.get("data") or []
        if isinstance(rows, dict):
            rows = rows.get("data") or rows.get("records") or []
        return rows[0] if isinstance(rows, list) and rows else {}

    def get_supplier_detail(self, ctx: AuthContext, apply_id: int, referer: str) -> dict:
        body = self._call(
            ctx,
            "GET",
            "/api/as/returnGoods/getDetailBySupplier",
            params={"returnId": apply_id},
            referer=referer,
        )
        return body.get("data") or {}

    def get_agent_detail(self, ctx: AuthContext, apply_id: int, referer: str) -> dict:
        for path in (
            "/api/as/returnGoods/agent/getDetail",
            "/api/as/returnGoods/getDetail",
            "/api/as/returnGoods/getDetailBySupplier",
        ):
            body = self._call(
                ctx,
                "GET",
                path,
                params={"returnId": apply_id},
                referer=referer,
            )
            if body.get("code") == 1000:
                return body.get("data") or {}
        return {}

    def _save_payload(
        self,
        *,
        order: dict,
        product: dict,
        order_id: int,
        order_no: str,
        return_count: int,
        supplier_member_id: int,
        supplier_role_id: int,
        supplier_name: str,
        buyer_member_id: int | None = None,
        buyer_role_id: int | None = None,
        buyer_name: str | None = None,
        agent: bool = False,
    ) -> dict:
        line = build_return_line(
            order, product, order_id=order_id, order_no=order_no, return_count=return_count
        )
        payload = {
            "currencyVO": {"id": None, "currencyName": None, "symbol": None, "name": None, "fullName": None},
            "applyAbstract": f"{order_no}{'代客退货' if agent else '采购单退货'}",
            "orderType": 3,
            "returnGoodsType": 1,
            "returnReason": f"{order_no}售后测试",
            "returnId": 0,
            "supplierMemberId": supplier_member_id,
            "supplierRoleId": supplier_role_id,
            "supplierMemberName": supplier_name,
            "returnGoodsAddress": {
                "deliveryType": 3,
                "sendAddress": "",
                "sendUserName": "",
                "sendUserTel": "",
                "sendId": "",
            },
            "proofFileList": [],
            "returnGoodsList": [line],
            "taskTypeKey": None,
            "shopId": ORDER_SHOP_ID or 1,
            "shopLogo": "",
            "shopName": supplier_name,
        }
        if agent:
            payload["memberId"] = buyer_member_id
            payload["memberRoleId"] = buyer_role_id
            payload["company"] = buyer_name
        return payload

    def _extract_apply_id(self, saved: dict) -> int:
        apply_id = saved.get("data")
        if isinstance(apply_id, dict):
            apply_id = apply_id.get("id") or apply_id.get("returnId") or apply_id.get("applyId")
        return int(apply_id)

    def _submit_and_confirm(
        self,
        seller: AuthContext,
        apply_id: int,
        *,
        agent: bool,
        steps: tuple[str, ...],
    ) -> list[dict]:
        executed = []
        submit_ref = (
            f"/memberCenter/afterServiceAbility/returnManage/returnPrSubmit/verify?id={apply_id}"
        )
        if "submit" in steps:
            recv = self.list_receiver(seller, submit_ref)
            submitted = self._call(
                seller,
                "POST",
                "/api/as/returnGoods/submitVerify",
                json_body={
                    "applyId": str(apply_id),
                    "isPass": 1,
                    "receiveId": recv.get("id") or recv.get("addressId"),
                    "receiveAddress": recv.get("fullAddress") or recv.get("address") or "",
                    "receiveUserName": recv.get("receiverName") or recv.get("userName") or recv.get("name") or "",
                    "receiveUserTel": recv.get("phone") or recv.get("tel") or recv.get("userTel") or "",
                },
                referer=submit_ref,
            )
            executed.append({"step": "submit", "code": submitted.get("code"), "message": submitted.get("message")})
            if submitted.get("code") != 1000:
                return executed
        if "confirm" in steps:
            confirm_ref = (
                f"/memberCenter/afterServiceAbility/returnManage/returnPrConfirm/verify?id={apply_id}"
            )
            before = self.get_supplier_detail(seller, apply_id, confirm_ref)
            if current_as_stage(before) in (AS_DELIVER, AS_RECEIVE, AS_REFUND, AS_DONE):
                executed.append({
                    "step": "confirm",
                    "code": 1000,
                    "message": f"当前 {before.get('innerStatusName') or current_as_stage(before)}，跳过审核确认",
                })
            else:
                confirmed = self._call(
                    seller,
                    "POST",
                    "/api/as/returnGoods/confirmVerify",
                    json_body={"applyId": str(apply_id), "isPass": 1},
                    referer=confirm_ref,
                )
                if confirmed.get("code") != 1000:
                    after = self.get_supplier_detail(seller, apply_id, confirm_ref)
                    if current_as_stage(after) in (AS_DELIVER, AS_RECEIVE, AS_REFUND, AS_DONE):
                        executed.append({
                            "step": "confirm",
                            "code": 1000,
                            "message": confirmed.get("message") or "退货申请无需二次审核",
                        })
                    else:
                        executed.append({
                            "step": "confirm",
                            "code": confirmed.get("code"),
                            "message": confirmed.get("message"),
                        })
                else:
                    executed.append({
                        "step": "confirm",
                        "code": confirmed.get("code"),
                        "message": confirmed.get("message"),
                    })
        return executed

    def _deliver_and_receive(
        self,
        ysb: AuthContext,
        seller: AuthContext,
        apply_id: int,
        *,
        agent: bool,
        steps: tuple[str, ...],
        scene: str | None,
    ) -> list[dict]:
        executed = []
        if "deliver" in steps:
            path = "/api/as/returnGoods/agent/returnDeliveryGoods" if agent else "/api/as/returnGoods/returnDeliveryGoods"
            delivered = self._call(
                ysb,
                "GET",
                path,
                params={"dataId": apply_id},
                scene=scene,
                referer=f"/memberCenter/afterServiceAbility/returnApplication/returnPrPurchaserDeliver/verify?id={apply_id}",
            )
            if delivered.get("code") != 1000:
                alt = "/api/as/returnGoods/returnDeliveryGoods" if agent else "/api/as/returnGoods/agent/returnDeliveryGoods"
                delivered = self._call(
                    ysb,
                    "GET",
                    alt,
                    params={"dataId": apply_id},
                    scene=scene,
                    referer=f"/memberCenter/afterServiceAbility/returnApplication/returnPrPurchaserDeliver/verify?id={apply_id}",
                )
            executed.append({"step": "deliver", "code": delivered.get("code"), "message": delivered.get("message")})
            if delivered.get("code") != 1000:
                return executed
        if "receive" not in steps and "refund" not in steps:
            return executed
        detail = (
            self.get_agent_detail(ysb, apply_id, f"/memberCenter/afterServiceAbility/returnManage/returnPrReceived/verify?id={apply_id}")
            if agent
            else self.get_supplier_detail(seller, apply_id, f"/memberCenter/afterServiceAbility/returnManage/returnPrReceived/verify?id={apply_id}")
        )
        if "receive" in steps:
            deliveries = detail.get("returnDeliveryGoodsList") or []
            delivery_id = None
            if deliveries:
                delivery_id = deliveries[0].get("deliveryId") or deliveries[0].get("deliveryNoId")
            if delivery_id:
                received = self._call(
                    seller if not agent else ysb,
                    "POST",
                    "/api/as/returnGoods/confirmReturnReceiveGoods",
                    json_body={"dataId": int(delivery_id)},
                    referer=f"/memberCenter/afterServiceAbility/returnManage/returnPrReceived/verify?id={apply_id}",
                )
                executed.append({"step": "receive", "code": received.get("code"), "message": received.get("message")})
                if received.get("code") != 1000:
                    return executed
            else:
                executed.append({"step": "receive", "code": 0, "message": "没有退货发货单"})
                return executed
        if "refund" in steps:
            executed.extend(self._refund(ysb, seller, apply_id, agent=agent, scene=scene))
        return executed

    def _refund(
        self,
        ysb: AuthContext,
        seller: AuthContext,
        apply_id: int,
        *,
        agent: bool,
        scene: str | None,
    ) -> list[dict]:
        executed = []
        referer = f"/memberCenter/afterServiceAbility/returnManage/returnPrReturn/verify?id={apply_id}"
        detail = (
            self.get_agent_detail(ysb, apply_id, referer)
            if agent
            else self.get_supplier_detail(seller, apply_id, referer)
        )
        stage = current_as_stage(detail)
        if stage == AS_DONE:
            executed.append({"step": "refund", "code": 1000, "message": "已售后完成，跳过退款"})
            return executed
        refund_id = None
        for item in detail.get("refundList") or []:
            details = item.get("detailList") or []
            if details:
                refund_id = details[0].get("refundId")
                break
        if not refund_id:
            executed.append({"step": "refund", "code": 1000, "message": "没有待退款行"})
            return executed
        uploaded = self.orders.upload_file(seller, ORDER_VOUCHER_FILE_PATH)
        refunded = self._call(
            seller,
            "POST",
            "/api/as/returnGoods/refund",
            json_body={
                "dataId": int(refund_id),
                "returnBalance": 0,
                "payProve": {
                    "name": detail.get("consumerName") or YSB_SUPPLIER_NAME,
                    "bankAccount": "67342568327950820589",
                    "bankDeposit": "招商银行",
                    "remark": None,
                    "returnBalance": 0,
                    "fileList": [{"name": uploaded["fileName"], "proveUrl": uploaded["url"]}],
                },
            },
            referer=referer,
        )
        executed.append({"step": "refund", "code": refunded.get("code"), "message": refunded.get("message")})
        if refunded.get("code") not in (1000, 51061):
            return executed
        if refunded.get("code") == 51061:
            return executed
        path = "/api/as/returnGoods/agent/confirmRefund" if agent else "/api/as/returnGoods/confirmRefund"
        confirm_refund = self._call(
            ysb,
            "POST",
            path,
            json_body={"refundId": int(refund_id), "isReceipt": 1},
            scene=scene,
            referer=f"/memberCenter/afterServiceAbility/returnApplication/returnPrConfirmRefund/verify?id={apply_id}",
        )
        if confirm_refund.get("code") != 1000 and agent:
            confirm_refund = self._call(
                ysb,
                "POST",
                "/api/as/returnGoods/confirmRefund",
                json_body={"refundId": int(refund_id), "isReceipt": 1},
                scene=scene,
                referer=f"/memberCenter/afterServiceAbility/returnApplication/returnPrConfirmRefund/verify?id={apply_id}",
            )
        executed.append({"step": "confirmRefund", "code": confirm_refund.get("code"), "message": confirm_refund.get("message")})
        return executed

    def return_purchase(
        self,
        *,
        order_id: int | None = None,
        order_no: str | None = None,
        status: str = AS_DONE,
        return_count: int = 1,
        dry_run: bool = False,
    ) -> dict:
        target = parse_as_status(status)
        ysb = self.purchase.login_ysb()
        inspect = self.purchase.inspect_purchase(order_id=order_id, order_no=order_no)
        if not inspect.get("ok"):
            return inspect
        po_id = int(inspect["order_id"])
        po_no = str(inspect.get("order_no") or "")
        vendor_member_id = int((inspect.get("vendor") or {}).get("memberId") or 0)
        vendor_name = str((inspect.get("vendor") or {}).get("memberName") or "")
        page = self.after_sale_page(
            ysb,
            order_no=po_no,
            vendor_member_id=vendor_member_id or None,
            vendor_role_id=25,
            scene="PURCHASE",
            referer=PURCHASE_ADD_REF,
        )
        order, product = self.pick_goods(page, po_no)
        result = {
            "ok": True,
            "kind": "purchase",
            "order_id": po_id,
            "order_no": po_no,
            "target": target,
            "vendor": inspect.get("vendor"),
            "product": None if not product else {
                "name": product.get("name"),
                "skuId": product.get("skuId"),
                "maxReturn": product.get("maxReturnOrReplaceCount"),
            },
        }
        if not order or not product:
            result["ok"] = False
            result["error"] = "售后商品列表没有可退货行"
            result["page"] = {"code": page.get("code"), "message": page.get("message")}
            return result
        payload = self._save_payload(
            order=order,
            product=product,
            order_id=po_id,
            order_no=po_no,
            return_count=return_count,
            supplier_member_id=vendor_member_id,
            supplier_role_id=25,
            supplier_name=vendor_name,
        )
        if dry_run:
            result["step"] = "dry_run"
            result["payload"] = payload
            return result
        saved = self._call(
            ysb,
            "POST",
            "/api/as/returnGoods/save",
            json_body=payload,
            scene="PURCHASE",
            referer=PURCHASE_ADD_REF,
        )
        executed = [{"step": "save", "code": saved.get("code"), "message": saved.get("message"), "data": saved.get("data")}]
        if saved.get("code") != 1000:
            result["ok"] = False
            result["executed"] = executed
            result["error"] = saved.get("message")
            return result
        apply_id = self._extract_apply_id(saved)
        seller = self.purchase.login_supplier(member_id=vendor_member_id)
        wanted = _AS_STEPS[target]
        rest = tuple(step for step in wanted if step != "save")
        executed.extend(self._submit_and_confirm(seller, apply_id, agent=False, steps=rest))
        failed = [item for item in executed if item.get("step") in rest and item.get("code") != 1000]
        if failed:
            result["ok"] = False
            result["executed"] = executed
            result["apply_id"] = apply_id
            result["error"] = failed[0].get("message")
            return result
        executed.extend(
            self._deliver_and_receive(
                ysb, seller, apply_id, agent=False, steps=rest, scene="PURCHASE"
            )
        )
        detail = self.get_supplier_detail(
            seller,
            apply_id,
            f"/memberCenter/afterServiceAbility/returnManage/returnPrConfirm/verify?id={apply_id}",
        )
        result["executed"] = executed
        result["apply_id"] = apply_id
        result["apply_no"] = detail.get("applyNo")
        result["inner"] = detail.get("innerStatusName")
        result["outer"] = detail.get("outerStatusName")
        result["stage"] = current_as_stage(detail)
        if any(item.get("code") not in (1000, 51061) for item in executed if item.get("step") != "save"):
            late = [item for item in executed if item.get("code") not in (1000, 51061) and item.get("step") != "save"]
            if late:
                result["ok"] = False
                result["error"] = late[-1].get("message")
                return result
        if target == AS_DONE and result["stage"] != AS_DONE:
            result["ok"] = False
            result["error"] = f"售后未到完成，当前 {result.get('inner')}/{result.get('outer')}"
        return result

    def return_sale(
        self,
        *,
        order_id: int | None = None,
        order_no: str | None = None,
        status: str = AS_DONE,
        return_count: int = 1,
        dry_run: bool = False,
    ) -> dict:
        target = parse_as_status(status)
        ysb = self.purchase.login_ysb()
        if not order_no and not order_id:
            return {"ok": False, "error": "请传销售单号或 orderId"}
        if not order_no:
            detail = self.purchase.sales_order_detail(ysb, int(order_id))
            order_no = str(detail.get("orderNo") or "")
            order_id = int(detail.get("orderId") or order_id)
        else:
            row = self.purchase.find_vendor_order(ysb, order_no) or {}
            order_id = int(order_id or row.get("orderId") or 0)
            if not order_id:
                return {"ok": False, "error": f"找不到销售单 {order_no}，可传 order_id"}
            detail = self.purchase.sales_order_detail(ysb, order_id)
        # 代客售后：先取采购会员，再按 buyerMemberId 拉可退货商品（不是 vendor 售后页）
        buyer_member_id = int(detail.get("buyerMemberId") or detail.get("memberId") or 0)
        buyer_role_id = int(detail.get("buyerRoleId") or 21)
        buyer_name = str(
            detail.get("buyerMemberName") or detail.get("memberName") or detail.get("companyName") or ""
        )
        if not buyer_member_id and buyer_name:
            member = self.find_agent_member(ysb, name=buyer_name) or {}
            buyer_member_id = int(member.get("memberId") or member.get("id") or 0)
            buyer_role_id = int(member.get("memberRoleId") or member.get("roleId") or buyer_role_id)
            buyer_name = str(member.get("name") or member.get("memberName") or buyer_name)
        if not buyer_member_id:
            return {"ok": False, "error": "代客售后需要采购会员 buyerMemberId，订单详情未解析到"}
        page = self.agent_after_sale_page(
            ysb,
            buyer_member_id=buyer_member_id,
            buyer_role_id=buyer_role_id,
            order_no=order_no,
        )
        order, product = self.pick_goods(page, order_no)
        result = {
            "ok": True,
            "kind": "sale",
            "order_id": order_id,
            "order_no": order_no,
            "target": target,
            "buyer": {"memberId": buyer_member_id, "roleId": buyer_role_id, "name": buyer_name},
            "product": None if not product else {
                "name": product.get("name"),
                "skuId": product.get("skuId"),
                "maxReturn": product.get("maxReturnOrReplaceCount"),
            },
        }
        if not order or not product:
            result["ok"] = False
            result["error"] = "售后商品列表没有可退货行（代客售后需销售单至少到待确认收货，并先选采购会员）"
            result["page"] = {"code": page.get("code"), "message": page.get("message"), "total": (page.get("data") or {}).get("totalCount") if isinstance(page.get("data"), dict) else None}
            return result
        payload = self._save_payload(
            order=order,
            product=product,
            order_id=order_id,
            order_no=order_no,
            return_count=return_count,
            supplier_member_id=YSB_SUPPLIER_MEMBER_ID,
            supplier_role_id=YSB_SUPPLIER_ROLE_ID,
            supplier_name=YSB_SUPPLIER_NAME,
            buyer_member_id=buyer_member_id,
            buyer_role_id=buyer_role_id,
            buyer_name=buyer_name,
            agent=True,
        )
        if dry_run:
            result["step"] = "dry_run"
            result["payload"] = payload
            return result
        saved = self._call(
            ysb,
            "POST",
            "/api/as/returnGoods/agent/save",
            json_body=payload,
            referer=SALE_VALET_REF,
        )
        executed = [{"step": "save", "code": saved.get("code"), "message": saved.get("message"), "data": saved.get("data")}]
        if saved.get("code") != 1000:
            result["ok"] = False
            result["executed"] = executed
            result["error"] = saved.get("message")
            return result
        apply_id = self._extract_apply_id(saved)
        wanted = _AS_STEPS[target]
        rest = tuple(step for step in wanted if step != "save")
        executed.extend(self._submit_and_confirm(ysb, apply_id, agent=True, steps=rest))
        executed.extend(
            self._deliver_and_receive(ysb, ysb, apply_id, agent=True, steps=rest, scene=None)
        )
        detail_as = self.get_agent_detail(
            ysb,
            apply_id,
            f"/memberCenter/afterServiceAbility/returnManage/returnPrConfirm/verify?id={apply_id}",
        )
        result["executed"] = executed
        result["apply_id"] = apply_id
        result["apply_no"] = detail_as.get("applyNo")
        result["inner"] = detail_as.get("innerStatusName")
        result["outer"] = detail_as.get("outerStatusName")
        result["stage"] = current_as_stage(detail_as)
        bad = [item for item in executed if item.get("code") not in (1000, 51061)]
        if bad:
            result["ok"] = False
            result["error"] = bad[-1].get("message")
        elif target == AS_DONE and result["stage"] != AS_DONE:
            result["ok"] = False
            result["error"] = f"售后未到完成，当前 {result.get('inner')}/{result.get('outer')}"
        return result
