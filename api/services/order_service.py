from __future__ import annotations

import copy
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.auth_service import LOGIN_EXPIRED_CODE, LoginExpiredError
from config.settings import (
    API_TIMEOUT_SECONDS,
    AUTH_ENVIRONMENT,
    AUTH_SITE,
    AUTH_SOURCE,
    COMMODITY_GUEST_LIST_API_URL,
    ORDER_AGENT_CREATE_API_URL,
    ORDER_BUYER_ROLE_ID,
    ORDER_BUYER_USER_ID,
    ORDER_COMBINATION_DETAIL_API_URL,
    ORDER_CONTRACT_FILE_PATH,
    ORDER_EXPECTED_INNER_STATUS,
    ORDER_EXPECTED_OUTER_STATUS,
    ORDER_EXPECTED_STATUS_NAME,
    ORDER_FILE_UPLOAD_BATCH_API_URL,
    ORDER_FREIGHT_CARRIAGE_TYPE_2_AMOUNT,
    ORDER_FUND_MODE,
    ORDER_PAY_CHANNEL,
    ORDER_PAY_CONFIRM_API_URL,
    ORDER_PAY_TYPE,
    ORDER_QUERY_MAX_RETRIES,
    ORDER_QUERY_RETRY_INTERVAL_SECONDS,
    ORDER_SHOP_ID,
    ORDER_UPLOAD_CONTRACT_API_URL,
    ORDER_VALET_PAY_API_URL,
    ORDER_VENDOR_PAGE_API_URL,
    ORDER_VOUCHER_FILE_PATH,
    PLATFORM_BASE_URL,
    RECEIVER_ADDRESS_AGENT_PAGE_API_URL,
)

ORDER_AGENT_REFERER = "/memberCenter/orderAbility/saleOrder/agentOrder"
ORDER_LIST_REFERER = "/memberCenter/orderAbility/saleOrder/orderList"
ORDER_PAY_RESULT_REFERER = "/memberCenter/orderAbility/saleOrder/readyPayResult/detail"


@dataclass(frozen=True)
class OrderLineItem:
    sku_id: int
    quantity: int
    unit_price: float | None = None


def parse_order_line_items(text: str) -> list[OrderLineItem]:
    """解析商品行，格式：skuId:quantity 或 skuId:quantity:unitPrice，多行用逗号分隔。"""
    items: list[OrderLineItem] = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split(":")
        if len(parts) not in (2, 3):
            raise ValueError(
                f"商品行格式错误: {chunk!r}，应为 skuId:quantity 或 skuId:quantity:unitPrice"
            )
        sku_id = int(parts[0])
        quantity = int(parts[1])
        unit_price = float(parts[2]) if len(parts) == 3 else None
        items.append(OrderLineItem(sku_id=sku_id, quantity=quantity, unit_price=unit_price))
    if not items:
        raise ValueError("至少需要一个商品行")
    return items


@dataclass(frozen=True)
class OrderFlowResult:
    order_id: int
    order_no: str
    inner_status: int
    inner_status_name: str
    outer_status: int
    outer_status_name: str
    steps: list[dict[str, Any]]


class OrderService:
    def __init__(self, client: ApiClient):
        self.client = client

    @staticmethod
    def build_headers(
        ctx: AuthContext,
        *,
        referer_path: str = ORDER_LIST_REFERER,
        content_type: str = "application/json",
        platform_base_url: str = PLATFORM_BASE_URL,
    ) -> dict[str, str]:
        headers = {
            "Accept": "*/*",
            "environment": AUTH_ENVIRONMENT,
            "site": AUTH_SITE,
            "source": AUTH_SOURCE,
            "Origin": platform_base_url,
            "Referer": f"{platform_base_url}{referer_path}",
            "memberId": str(ctx.member_id),
            "userId": str(ctx.user_id),
            "token": ctx.token,
            "Authorization": ctx.token,
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    @staticmethod
    def _parse_json(resp) -> dict:
        try:
            return resp.json()
        except Exception as exc:
            raise AssertionError(f"响应无法解析为 JSON: status={resp.status_code}, body={resp.text[:500]}") from exc

    @staticmethod
    def _assert_success(body: dict, action: str) -> dict:
        if body.get("code") == LOGIN_EXPIRED_CODE:
            raise LoginExpiredError(f"{action}失败: {body}")
        if body.get("code") != 1000:
            raise AssertionError(f"{action}失败: {body}")
        return body.get("data") or {}

    @staticmethod
    def _parse_unit_price(unit_price: dict | None) -> float:
        if not unit_price:
            raise AssertionError("商品缺少 unitPrice")
        if "0-0" in unit_price:
            return float(unit_price["0-0"])
        first_key = sorted(unit_price.keys())[0]
        return float(unit_price[first_key])

    @staticmethod
    def _format_price(value: float) -> str:
        return f"{value:.6f}"

    @staticmethod
    def _resolve_freight(logistics: dict | None) -> float:
        if int((logistics or {}).get("carriageType") or 0) == 2:
            return ORDER_FREIGHT_CARRIAGE_TYPE_2_AMOUNT
        return 0.0

    @staticmethod
    def _build_consignee_from_address(address: dict) -> dict:
        return {
            "countryAreaCode": address.get("countryAreaCode", "CN"),
            "provincialAddress": address.get("provincialAddress"),
            "consigneeId": address["id"],
            "consignee": address.get("receiverName"),
            "provinceCode": address.get("provinceCode"),
            "cityCode": address.get("cityCode"),
            "districtCode": address.get("districtCode"),
            "streetCode": address.get("streetCode") or "",
            "address": address.get("address"),
            "postalCode": address.get("postalCode"),
            "countryCode": address.get("areaCode", "+86"),
            "phone": address.get("phone"),
            "telephone": address.get("tel") or "",
            "defaultConsignee": bool(address.get("isDefault")),
        }

    def get_guest_commodity(
        self,
        ctx: AuthContext,
        *,
        buyer_member_id: int,
        sku_id: int,
        buyer_role_id: int = ORDER_BUYER_ROLE_ID,
        api_url: str = COMMODITY_GUEST_LIST_API_URL,
        referer_path: str = ORDER_AGENT_REFERER,
        platform_base_url: str = PLATFORM_BASE_URL,
    ) -> dict:
        resp = self.client.request(
            "POST",
            api_url,
            json_body={
                "pageSize": 10,
                "commoditySkuId": str(sku_id),
                "current": 1,
                "shopType": 1,
                "environment": int(AUTH_ENVIRONMENT),
                "sampleFlag": "0",
                "memberId": buyer_member_id,
                "roleId": buyer_role_id,
                "priceTypeList": [1, 5],
                "shopId": ORDER_SHOP_ID,
            },
            headers=self.build_headers(
                ctx,
                referer_path=referer_path,
                platform_base_url=platform_base_url,
            ),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        body = self._parse_json(resp)
        data = self._assert_success(body, "查询代客下单商品")
        rows = data.get("data") or []
        if not rows:
            raise AssertionError(
                f"未找到代客下单商品 buyerMemberId={buyer_member_id}, skuId={sku_id}: {body}"
            )
        return rows[0]

    def get_buyer_receiver_address(
        self,
        ctx: AuthContext,
        *,
        buyer_member_id: int,
        buyer_role_id: int = ORDER_BUYER_ROLE_ID,
        buyer_user_id: int | None = None,
        api_url: str = RECEIVER_ADDRESS_AGENT_PAGE_API_URL,
        referer_path: str = ORDER_AGENT_REFERER,
        platform_base_url: str = PLATFORM_BASE_URL,
    ) -> dict:
        params: dict[str, Any] = {
            "memberId": buyer_member_id,
            "roleId": buyer_role_id,
            "current": 1,
            "pageSize": 9999,
        }
        if buyer_user_id is not None:
            params["userId"] = buyer_user_id
        resp = self.client.request(
            "GET",
            api_url,
            params=params,
            headers=self.build_headers(
                ctx,
                referer_path=referer_path,
                content_type="",
                platform_base_url=platform_base_url,
            ),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        body = self._parse_json(resp)
        data = self._assert_success(body, "查询客户收货地址")
        rows = data.get("data") or []
        if not rows:
            raise AssertionError(
                f"未找到客户收货地址 memberId={buyer_member_id} "
                f"roleId={buyer_role_id} userId={buyer_user_id}: {body}"
            )
        for row in rows:
            if row.get("isDefault"):
                return row
        return rows[0]

    @staticmethod
    def _build_product_from_guest(
        guest_product: dict,
        *,
        buyer_member_id: int,
        quantity: int,
        unit_price: float,
        freight: float,
    ) -> dict:
        product = copy.deepcopy(guest_product)
        logistics = copy.deepcopy(product.get("logistics") or {})
        logistics["render"] = "物流"
        money = round(unit_price * quantity, 2)
        product.update(
            {
                "quantity": quantity,
                "purchaseCount": quantity,
                "money": money,
                "price": OrderService._format_price(unit_price),
                "newUnitPrice": unit_price,
                "buyerMemberId": buyer_member_id,
                "buyerRoleId": ORDER_BUYER_ROLE_ID,
                "orderMode": 1,
                "shopId": ORDER_SHOP_ID,
                "brand": product.get("brandName"),
                "unit": product.get("unitName"),
                "category": product.get("shopCategoryName"),
                "productId": product.get("commodityId"),
                "productName": product.get("name"),
                "skuId": product.get("id"),
                "deliverType": logistics.get("sendAddress"),
                "deliveryType": logistics.get("deliveryType"),
                "memberPrice": 1,
                "deliveryPrice": 0,
                "freightPrice": freight,
                "logo": product.get("mainPic"),
                "discount": 1,
                "tax": False,
                "vendorMemberId": product.get("memberId"),
                "vendorRoleId": product.get("memberRoleId"),
                "vendorMemberName": product.get("memberName"),
                "logistics": logistics,
                "unitPrice": product.get("unitPrice") or OrderService._format_unit_price_map(unit_price),
                "originalUnitPrice": product.get("originalUnitPrice") or product.get("unitPrice"),
                "expectDeliverDate": product.get("expectDeliverDate") or date.today().isoformat(),
            }
        )
        return product

    @staticmethod
    def _format_unit_price_map(value: float) -> dict[str, str]:
        if float(int(value)) == float(value):
            return {"0-0": f"{value:.2f}"}
        text = f"{value:.6f}".rstrip("0").rstrip(".")
        return {"0-0": text}

    def build_agent_order_payload(
        self,
        ctx: AuthContext,
        *,
        buyer_member_id: int,
        buyer_member_name: str,
        items: list[OrderLineItem] | None = None,
        sku_id: int | None = None,
        quantity: int | None = None,
        unit_price: float | None = None,
        buyer_user_id: int | None = None,
        buyer_role_id: int = ORDER_BUYER_ROLE_ID,
        buyer_user_name: str | None = None,
        commodity_api_url: str = COMMODITY_GUEST_LIST_API_URL,
        address_api_url: str = RECEIVER_ADDRESS_AGENT_PAGE_API_URL,
        referer_path: str = ORDER_AGENT_REFERER,
        platform_base_url: str = PLATFORM_BASE_URL,
    ) -> dict:
        line_items = items or [
            OrderLineItem(
                sku_id=int(sku_id),
                quantity=int(quantity),
                unit_price=unit_price,
            )
        ]
        if not line_items:
            raise AssertionError("至少需要一个商品行")

        address = self.get_buyer_receiver_address(
            ctx,
            buyer_member_id=buyer_member_id,
            buyer_role_id=buyer_role_id,
            buyer_user_id=buyer_user_id,
            api_url=address_api_url,
            referer_path=referer_path,
            platform_base_url=platform_base_url,
        )

        products: list[dict] = []
        total_product_money = 0.0
        total_freight = 0.0
        for item in line_items:
            guest_product = self.get_guest_commodity(
                ctx,
                buyer_member_id=buyer_member_id,
                sku_id=item.sku_id,
                buyer_role_id=buyer_role_id,
                api_url=commodity_api_url,
                referer_path=referer_path,
                platform_base_url=platform_base_url,
            )
            resolved_unit_price = (
                item.unit_price
                if item.unit_price is not None
                else self._parse_unit_price(guest_product.get("unitPrice"))
            )
            freight = self._resolve_freight(guest_product.get("logistics"))
            product = self._build_product_from_guest(
                guest_product,
                buyer_member_id=buyer_member_id,
                quantity=item.quantity,
                unit_price=resolved_unit_price,
                freight=freight,
            )
            products.append(product)
            total_product_money += float(product["money"])
            total_freight += freight

        total_price = round(total_product_money + total_freight, 2)

        payload = copy.deepcopy(_AGENT_ORDER_TEMPLATE)
        payload["products"] = products
        payload["buyerMemberMajorId"] = buyer_member_id
        payload["buyerMemberId"] = buyer_member_id
        payload["buyerMemberName"] = buyer_member_name
        payload["buyerRoleId"] = buyer_role_id
        resolved_buyer_user_id = buyer_user_id if buyer_user_id is not None else ORDER_BUYER_USER_ID
        if resolved_buyer_user_id is not None:
            payload["buyerUserId"] = resolved_buyer_user_id
        if buyer_user_name:
            payload["buyerUserName"] = buyer_user_name
        payload["deliveryAddresId"] = copy.deepcopy(address)
        payload["consignee"] = self._build_consignee_from_address(address)
        payload["shopId"] = ORDER_SHOP_ID
        payload["sumPrice"] = total_price
        payload["freight"] = total_freight
        payload["payments"][0]["payPrice"] = f"{total_price:.2f}"
        return payload

    def create_agent_order(
        self,
        ctx: AuthContext,
        payload: dict,
        *,
        api_url: str = ORDER_AGENT_CREATE_API_URL,
        referer_path: str = ORDER_AGENT_REFERER,
        platform_base_url: str = PLATFORM_BASE_URL,
    ) -> dict:
        resp = self.client.request(
            "POST",
            api_url,
            json_body=payload,
            headers=self.build_headers(
                ctx,
                referer_path=referer_path,
                platform_base_url=platform_base_url,
            ),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return self._parse_json(resp)

    def query_orders(
        self,
        ctx: AuthContext,
        *,
        member_name: str,
        sku_id: int,
        current: int = 1,
        page_size: int = 10,
    ) -> dict:
        resp = self.client.request(
            "GET",
            ORDER_VENDOR_PAGE_API_URL,
            params={
                "pageSize": page_size,
                "memberName": member_name,
                "current": current,
                "skuId": sku_id,
            },
            headers=self.build_headers(ctx, content_type=""),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return self._parse_json(resp)

    def get_order_by_id(
        self,
        ctx: AuthContext,
        *,
        order_id: int,
        member_name: str,
        sku_id: int,
        max_retries: int = ORDER_QUERY_MAX_RETRIES,
        interval_seconds: float = ORDER_QUERY_RETRY_INTERVAL_SECONDS,
    ) -> dict:
        last_body: dict = {}
        for attempt in range(1, max_retries + 1):
            body = self.query_orders(ctx, member_name=member_name, sku_id=sku_id, page_size=50)
            last_body = body
            data = self._assert_success(body, "查询订单")
            rows = data.get("data") or []
            for row in rows:
                if int(row.get("orderId", 0)) == order_id:
                    return row
            if attempt < max_retries:
                time.sleep(interval_seconds)
        raise AssertionError(
            f"未查询到指定订单 orderId={order_id}（memberName={member_name}, skuId={sku_id}）: {last_body}"
        )

    def wait_for_latest_order(
        self,
        ctx: AuthContext,
        *,
        member_name: str,
        sku_id: int,
        max_retries: int = ORDER_QUERY_MAX_RETRIES,
        interval_seconds: float = ORDER_QUERY_RETRY_INTERVAL_SECONDS,
    ) -> dict:
        last_body: dict = {}
        for attempt in range(1, max_retries + 1):
            body = self.query_orders(ctx, member_name=member_name, sku_id=sku_id, page_size=50)
            last_body = body
            data = self._assert_success(body, "查询订单")
            rows = data.get("data") or []
            if rows:
                return rows[0]
            if attempt < max_retries:
                time.sleep(interval_seconds)
        raise AssertionError(f"未查询到订单（memberName={member_name}, skuId={sku_id}）: {last_body}")

    def wait_for_order_status(
        self,
        ctx: AuthContext,
        *,
        order_id: int,
        member_name: str,
        sku_id: int,
        expected_inner_status: int,
        expected_outer_status: int,
        max_retries: int = ORDER_QUERY_MAX_RETRIES,
        interval_seconds: float = ORDER_QUERY_RETRY_INTERVAL_SECONDS,
    ) -> dict:
        last_row: dict = {}
        for attempt in range(1, max_retries + 1):
            row = self.get_order_by_id(
                ctx,
                order_id=order_id,
                member_name=member_name,
                sku_id=sku_id,
                max_retries=1,
                interval_seconds=0,
            )
            last_row = row
            if (
                int(row.get("innerStatus", -1)) == expected_inner_status
                and int(row.get("outerStatus", -1)) == expected_outer_status
            ):
                return row
            if attempt < max_retries:
                time.sleep(interval_seconds)
        raise AssertionError(
            "订单状态未达到预期: "
            f"expected inner={expected_inner_status}, outer={expected_outer_status}; "
            f"actual inner={last_row.get('innerStatus')}, outer={last_row.get('outerStatus')}; "
            f"orderNo={last_row.get('orderNo')}"
        )

    def upload_file(self, ctx: AuthContext, file_path: str | Path) -> dict[str, str]:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"上传文件不存在: {path}")
        headers = self.build_headers(ctx, content_type="")
        with path.open("rb") as file_obj:
            resp = self.client.request(
                "POST",
                ORDER_FILE_UPLOAD_BATCH_API_URL,
                files={"file": (path.name, file_obj, "image/jpeg")},
                headers=headers,
                timeout=API_TIMEOUT_SECONDS,
            )
        resp.raise_for_status()
        body = self._parse_json(resp)
        data = self._assert_success(body, "上传文件")
        if isinstance(data, list) and data:
            item = data[0]
        elif isinstance(data, dict):
            item = data
        else:
            raise AssertionError(f"上传文件响应格式异常: {body}")
        url = item.get("url") or item.get("fileUrl") or item.get("path")
        if not url:
            raise AssertionError(f"上传文件未返回 url: {body}")
        return {"url": str(url), "fileName": str(item.get("fileName") or path.name)}

    def upload_contract(
        self,
        ctx: AuthContext,
        *,
        order_id: int,
        file_url: str,
        file_name: str,
    ) -> dict:
        payload = {"orderId": order_id, "fileList": [{"url": file_url, "fileName": file_name}]}
        resp = self.client.request(
            "POST",
            ORDER_UPLOAD_CONTRACT_API_URL,
            json_body=payload,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return self._parse_json(resp)

    def get_order_detail(self, ctx: AuthContext, order_id: int) -> dict:
        resp = self.client.request(
            "GET",
            ORDER_COMBINATION_DETAIL_API_URL,
            params={"orderId": order_id},
            headers=self.build_headers(ctx, content_type=""),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return self._parse_json(resp)

    def valet_upload_pay_voucher(
        self,
        ctx: AuthContext,
        *,
        order_id: int,
        voucher_urls: list[str],
        batch_no: int = 1,
        pay_type: int = ORDER_PAY_TYPE,
        pay_channel: int = ORDER_PAY_CHANNEL,
        fund_mode: int = ORDER_FUND_MODE,
    ) -> dict:
        payload = {
            "orderId": order_id,
            "batchNo": batch_no,
            "payType": pay_type,
            "payChannel": pay_channel,
            "fundMode": fund_mode,
            "vouchers": voucher_urls,
        }
        resp = self.client.request(
            "POST",
            ORDER_VALET_PAY_API_URL,
            json_body=payload,
            headers=self.build_headers(ctx),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return self._parse_json(resp)

    def confirm_pay(
        self,
        ctx: AuthContext,
        *,
        order_id: int,
        batch_no: int = 1,
        agree: int = 1,
    ) -> dict:
        payload = {"agree": agree, "orderId": order_id, "batchNo": batch_no}
        resp = self.client.request(
            "POST",
            ORDER_PAY_CONFIRM_API_URL,
            json_body=payload,
            headers=self.build_headers(ctx, referer_path=ORDER_PAY_RESULT_REFERER),
            timeout=API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return self._parse_json(resp)

    def create_order_pending_stock_up(
        self,
        ctx: AuthContext,
        *,
        buyer_member_id: int,
        buyer_member_name: str,
        items: list[OrderLineItem] | None = None,
        sku_id: int | None = None,
        quantity: int | None = None,
        unit_price: float | None = None,
        buyer_user_id: int | None = None,
        contract_file_path: str | Path = ORDER_CONTRACT_FILE_PATH,
        voucher_file_path: str | Path = ORDER_VOUCHER_FILE_PATH,
        expected_inner_status: int = ORDER_EXPECTED_INNER_STATUS,
        expected_outer_status: int = ORDER_EXPECTED_OUTER_STATUS,
        expected_status_name: str = ORDER_EXPECTED_STATUS_NAME,
    ) -> OrderFlowResult:
        line_items = items or [
            OrderLineItem(
                sku_id=int(sku_id),
                quantity=int(quantity),
                unit_price=unit_price,
            )
        ]
        query_sku_id = line_items[0].sku_id
        steps: list[dict[str, Any]] = []

        order_payload = self.build_agent_order_payload(
            ctx,
            buyer_member_id=buyer_member_id,
            buyer_member_name=buyer_member_name,
            items=line_items,
            buyer_user_id=buyer_user_id,
        )
        create_body = self.create_agent_order(ctx, order_payload)
        self._assert_success(create_body, "代客下单")
        steps.append({"step": "create_agent_order", "request": order_payload, "response": create_body})

        order_row = self.wait_for_latest_order(
            ctx,
            member_name=buyer_member_name,
            sku_id=query_sku_id,
        )
        order_id = int(order_row["orderId"])
        order_no = str(order_row["orderNo"])
        steps.append({"step": "query_order", "order_id": order_id, "order_no": order_no, "row": order_row})

        contract_file = self.upload_file(ctx, contract_file_path)
        steps.append({"step": "upload_contract_file", "file": contract_file})

        contract_body = self.upload_contract(
            ctx,
            order_id=order_id,
            file_url=contract_file["url"],
            file_name=contract_file["fileName"],
        )
        self._assert_success(contract_body, "上传合同")
        steps.append({"step": "bind_contract", "response": contract_body})

        detail_body = self.get_order_detail(ctx, order_id)
        detail_data = self._assert_success(detail_body, "获取订单详情")
        steps.append({"step": "order_detail", "response": detail_data})

        voucher_file = self.upload_file(ctx, voucher_file_path)
        steps.append({"step": "upload_voucher_file", "file": voucher_file})

        valet_body = self.valet_upload_pay_voucher(
            ctx,
            order_id=order_id,
            voucher_urls=[voucher_file["url"]],
        )
        self._assert_success(valet_body, "代客上传支付凭证")
        steps.append({"step": "valet_pay", "response": valet_body})

        confirm_body = self.confirm_pay(ctx, order_id=order_id)
        self._assert_success(confirm_body, "确认支付结果")
        steps.append({"step": "confirm_pay", "response": confirm_body})

        final_row = self.wait_for_order_status(
            ctx,
            order_id=order_id,
            member_name=buyer_member_name,
            sku_id=query_sku_id,
            expected_inner_status=expected_inner_status,
            expected_outer_status=expected_outer_status,
        )
        inner_status = int(final_row.get("innerStatus", -1))
        outer_status = int(final_row.get("outerStatus", -1))
        inner_status_name = str(final_row.get("innerStatusName", ""))
        outer_status_name = str(final_row.get("outerStatusName", ""))
        steps.append({"step": "final_status", "row": final_row})

        return OrderFlowResult(
            order_id=order_id,
            order_no=order_no,
            inner_status=inner_status,
            inner_status_name=inner_status_name,
            outer_status=outer_status,
            outer_status_name=outer_status_name,
            steps=steps,
        )


_AGENT_ORDER_TEMPLATE: dict[str, Any] = {
    "shopId": 1,
    "contract": None,
    "hasInvoice": False,
    "vendorMemberName": "江苏易食包数字科技有限公司",
    "vendorMemberId": 6,
    "vendorRoleId": 13,
    "logistics2": {"isExpress": "0", "hasDelivery": "0", "company": ""},
    "orderMode": 1,
    "type": "标准订单",
    "products": [
        {
            "id": 107721,
            "upperCommoditySkuId": None,
            "commodityId": 101329,
            "goodsId": None,
            "goodsName": None,
            "goodsCode": None,
            "code": "P003969",
            "name": "牛皮纸杯",
            "realName": None,
            "attribute": "淋膜牛皮纸_上口90*下口75*高59",
            "mainPic": "https://zhaliyunoss.esbao.com/咖啡杯（白色-19b636853c653440f9f8527ae4c4cdd52.png",
            "shopCategoryId": 103653,
            "shopCategoryName": "牛皮纸杯",
            "shopFullCategoryName": "选包材>纸质包装>牛皮纸包装>牛皮纸杯",
            "brandName": "阿林专属测试5432",
            "minOrder": "1.00",
            "unitName": "个",
            "priceType": 1,
            "priceTypeStr": "普通商品",
            "cashPriceType": 1,
            "isMemberPrice": False,
            "min": "25",
            "max": "25",
            "minSidePrice": None,
            "maxSidePrice": None,
            "taxRate": "0",
            "status": 5,
            "applyTime": None,
            "memberId": 6,
            "memberName": "江苏易食包数字科技有限公司",
            "memberRoleId": 13,
            "memberRoleName": "易食包商家",
            "unitPrice": {"0-0": "25.00"},
            "sidePrice": None,
            "isUnitPriceStrategy": False,
            "stockCount": -4000,
            "logistics": {
                "deliveryType": 1,
                "carriageType": 1,
                "weight": 1,
                "useTemplate": False,
                "templateId": None,
                "sendAddress": 13,
                "company": None,
                "render": "物流",
            },
            "type": 1,
            "source": 1,
            "upperMemberId": None,
            "upperMemberName": None,
            "upperMemberRoleId": None,
            "upperMemberRoleName": None,
            "isChannelCommodity": False,
            "isAllArea": True,
            "commodityAreaList": None,
            "isCrossBorder": False,
            "currencyVO": {
                "id": 1,
                "currencyName": "RMB",
                "name": "人民币",
                "symbol": "￥",
                "fullName": "RMB-人民币",
            },
            "sourceShopType": 1,
            "relationId": 1,
            "relationName": "食品包装商城",
            "productCategoryType": None,
            "boxProductWeight": 0.02,
            "cartonId": 15,
            "boxWeight": 0.02,
            "boxNum": 1000,
            "commoditySkuAttributeList": None,
            "sampleFlag": 0,
            "querySampleFlag": 0,
            "samplePrice": "0.000000",
            "boxSpecificationAttribute": {
                "boxId": 15,
                "boxName": "90装托110*110*90",
                "boxNum": 1000,
                "boxVolume": 1.089,
                "boxWeight": 20,
                "boxProductWeight": 0.02,
                "templateId": 4,
                "templateName": "设备安徽天加发货",
            },
            "model": "SE53",
            "spec": "淋膜牛皮纸_上口90*下口75*高59",
            "attributeSpeName": "材质:淋膜牛皮纸;规格尺寸mm:上口90*下口75*高59",
            "originalUnitPrice": {"0-0": "25.00"},
            "inventoryCheckFlag": 0,
            "expectDeliverDate": "2026-07-13",
            "layeringType": "三层",
            "ahTjXclErpCode": None,
            "szTjBzErpCode": None,
            "szTjXclErpCode": None,
            "ysbSzErpCode": None,
            "erpCode": None,
            "reason": None,
            "commodityPushErpStatus": None,
            "erpFailReason": None,
            "productName": "牛皮纸杯",
            "pricingStrategy": None,
            "orderMode": 1,
            "shopId": 1,
            "buyerMemberId": 104440,
            "buyerRoleId": 21,
            "brand": "阿林专属测试5432",
            "unit": "个",
            "deliverType": 13,
            "deliveryType": 1,
            "memberPrice": 1,
            "deliveryPrice": 0,
            "freightPrice": 0,
            "isGift": 0,
            "giftQuantity": 0,
            "purchaseCount": 100,
            "money": 2500,
            "price": "25.000000",
            "newUnitPrice": 25,
            "productId": 101329,
            "category": "牛皮纸杯",
            "addressId": 102931,
            "address": "上海上海市黄浦区南京东路街道测试1221",
            "receiver": "测试1221",
            "phone": "13211212212",
            "skuId": 107721,
            "logo": "https://zhaliyunoss.esbao.com/咖啡杯（白色-19b636853c653440f9f8527ae4c4cdd52.png",
            "quantity": 100,
            "logisticsTemplateId": None,
            "weight": 1,
            "stock": -4000,
            "discount": 1,
            "tax": False,
            "vendorMemberId": 6,
            "vendorRoleId": 13,
            "vendorMemberName": "江苏易食包数字科技有限公司",
            "supplyMemberId": None,
            "supplyRoleId": None,
            "supplyMemberName": None,
            "crossBorder": False,
            "interestPrice": None,
            "originalPrice": None,
        }
    ],
    "payments": [
        {
            "interestRate": None,
            "payTypeName": "线下支付",
            "payType": 2,
            "payChannels": [
                {
                    "payChannel": 5,
                    "payChannelName": "线下支付线上确认",
                    "isDefault": 0,
                    "interestRate": None,
                    "settlementDay": None,
                    "canUseQuota": None,
                    "orderNode": None,
                    "notSelectable": None,
                    "payNodes": [{"batchNo": 1, "payNode": "首付", "outerStatusName": "待支付", "payRate": "100"}],
                    "accountPeriod": None,
                }
            ],
            "batchNo": 1,
            "payNode": "首付",
            "outerStatusName": "待支付",
            "payRate": "100",
            "payChannel": 5,
            "payChannelName": "线下支付线上确认",
            "isDefault": 0,
            "settlementDay": None,
            "canUseQuota": None,
            "orderNode": None,
            "notSelectable": None,
            "payNodes": [{"batchNo": 1, "payNode": "首付", "outerStatusName": "待支付", "payRate": "100"}],
            "accountPeriod": None,
            "index": 0,
            "payType2": "线下支付",
            "payChannel2": "线下支付线上确认",
            "payPrice": "2500.00",
        }
    ],
    "buyerMemberMajorId": 104440,
    "buyerMemberId": 104440,
    "buyerRoleId": 21,
    "buyerMemberName": "衢州白马投资有限公司",
    "buyerSaleOrgType": 5,
    "buyerUserId": 104616,
    "buyerUserName": "",
    "deliveryAddresId": {
        "id": 103314,
        "receiverName": "衢州白马投资有限公司",
        "fullAddress": "上海上海市黄浦区衢州白马投资有限公司",
        "countryAreaCode": "CN",
        "provincialAddress": None,
        "provinceCode": "310000",
        "provinceName": "上海",
        "cityCode": "310100",
        "cityName": "上海市",
        "districtCode": "310101",
        "districtName": "黄浦区",
        "streetCode": None,
        "streetName": None,
        "address": "衢州白马投资有限公司",
        "postalCode": None,
        "areaCode": "+86",
        "phone": "17847839026",
        "tel": None,
        "isDefault": 1,
        "companyId": None,
        "companyName": None,
        "memberId": 104440,
        "roleId": 21,
    },
    "payTypeMessageObj": {
        "payType": {
            "payTypeName": "线下支付",
            "payType": 2,
            "payChannels": [
                {
                    "payChannel": 5,
                    "payChannelName": "线下支付线上确认",
                    "isDefault": 0,
                    "interestRate": None,
                    "settlementDay": None,
                    "canUseQuota": None,
                    "orderNode": None,
                    "notSelectable": None,
                    "payNodes": [{"batchNo": 1, "payNode": "首付", "outerStatusName": "待支付", "payRate": "100"}],
                    "accountPeriod": None,
                }
            ],
        },
        "payChannel": {
            "payChannel": 5,
            "payChannelName": "线下支付线上确认",
            "isDefault": 0,
            "interestRate": None,
            "settlementDay": None,
            "canUseQuota": None,
            "orderNode": None,
            "notSelectable": None,
            "payNodes": [{"batchNo": 1, "payNode": "首付", "outerStatusName": "待支付", "payRate": "100"}],
            "accountPeriod": None,
        },
        "interestRate": None,
    },
    "payType": 2,
    "sumPrice": 2500,
    "freight": 0,
    "payChannel": 5,
    "isDelivery": "0",
    "isExpress": "0",
    "contractSigningMethod": 2,
    "fileList": [],
    "consignee": {
        "countryAreaCode": "CN",
        "provincialAddress": None,
        "consigneeId": 103314,
        "consignee": "衢州白马投资有限公司",
        "provinceCode": "310000",
        "cityCode": "310100",
        "districtCode": "310101",
        "streetCode": "",
        "address": "衢州白马投资有限公司",
        "postalCode": None,
        "countryCode": "+86",
        "phone": "17847839026",
        "telephone": "",
        "defaultConsignee": True,
    },
    "requirement": {},
    "currencyId": 1,
    "shopType": 1,
    "shopEnvironment": 1,
    "shopName": "食品包装商城-web",
    "shopClassify": 1,
}
