"""订单造数脚本：代客下单 -> 合同 -> 支付 -> 订单备货中。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.auth_service import AuthService, LoginExpiredError, is_login_expired
from api.services.order_service import OrderLineItem, OrderService, parse_order_line_items
from config.settings import (
    API_TIMEOUT_SECONDS,
    LOGIN_PASSWORD_ENCRYPTED,
    LOGIN_PHONE,
    ORDER_BUYER_MEMBER_ID,
    ORDER_BUYER_MEMBER_NAME,
    ORDER_BUYER_USER_ID,
    ORDER_EXPECTED_INNER_STATUS,
    ORDER_EXPECTED_OUTER_STATUS,
    ORDER_EXPECTED_STATUS_NAME,
    ORDER_QUANTITY,
    ORDER_SKU_ID,
)

LOGIN_RETRY_ATTEMPTS = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="创建订单备货中状态的测试订单")
    parser.add_argument("--buyer-member-id", type=int, default=ORDER_BUYER_MEMBER_ID)
    parser.add_argument("--buyer-member-name", default=ORDER_BUYER_MEMBER_NAME)
    parser.add_argument("--buyer-user-id", type=int, default=ORDER_BUYER_USER_ID)
    parser.add_argument("--sku-id", type=int, default=ORDER_SKU_ID, help="单商品时使用")
    parser.add_argument("--quantity", type=int, default=ORDER_QUANTITY, help="单商品时使用")
    parser.add_argument(
        "--items",
        default="",
        help='多商品时使用，格式 skuId:quantity 或 skuId:quantity:unitPrice，逗号分隔，如 "107721:50,108453:20"',
    )
    parser.add_argument("--unit-price", type=float, default=None, help="单商品时使用；不传则使用商品接口返回价格")
    parser.add_argument("--step", choices=["all", "create-query"], default="all")
    return parser.parse_args()


def resolve_line_items(args: argparse.Namespace) -> list[OrderLineItem]:
    if args.items:
        return parse_order_line_items(args.items)
    return [
        OrderLineItem(
            sku_id=args.sku_id,
            quantity=args.quantity,
            unit_price=args.unit_price,
        )
    ]


def _login_session() -> tuple[AuthContext, OrderService]:
    auth = AuthService(ApiClient(timeout=API_TIMEOUT_SECONDS))
    login = auth.login_with_encrypted_password(LOGIN_PHONE, LOGIN_PASSWORD_ENCRYPTED)
    ctx = AuthContext.from_login_data(login)
    client = ApiClient(
        timeout=API_TIMEOUT_SECONDS,
        default_headers={"Authorization": ctx.token, "token": ctx.token},
    )
    return ctx, OrderService(client)


def _run_create_query(
    args: argparse.Namespace,
    ctx: AuthContext,
    svc: OrderService,
    line_items: list[OrderLineItem],
) -> dict:
    payload = svc.build_agent_order_payload(
        ctx,
        buyer_member_id=args.buyer_member_id,
        buyer_member_name=args.buyer_member_name,
        items=line_items,
        buyer_user_id=args.buyer_user_id,
    )
    create_body = svc.create_agent_order(ctx, payload)
    if is_login_expired(create_body):
        raise LoginExpiredError(f"代客下单失败: {create_body}")
    if create_body.get("code") != 1000:
        return {"ok": False, "payload": {"step": "create_agent_order", "response": create_body}}
    order_row = svc.wait_for_latest_order(
        ctx,
        member_name=args.buyer_member_name,
        sku_id=line_items[0].sku_id,
    )
    return {
        "ok": True,
        "payload": {
            "step": "create-query",
            "items": [
                {"sku_id": item.sku_id, "quantity": item.quantity, "unit_price": item.unit_price}
                for item in line_items
            ],
            "create_response": create_body,
            "order_id": order_row.get("orderId"),
            "order_no": order_row.get("orderNo"),
            "inner_status": order_row.get("innerStatus"),
            "outer_status": order_row.get("outerStatus"),
            "row": order_row,
        },
    }


def _run_full_flow(
    args: argparse.Namespace,
    ctx: AuthContext,
    svc: OrderService,
    line_items: list[OrderLineItem],
) -> dict:
    result = svc.create_order_pending_stock_up(
        ctx,
        buyer_member_id=args.buyer_member_id,
        buyer_member_name=args.buyer_member_name,
        items=line_items,
        buyer_user_id=args.buyer_user_id,
        expected_inner_status=ORDER_EXPECTED_INNER_STATUS,
        expected_outer_status=ORDER_EXPECTED_OUTER_STATUS,
        expected_status_name=ORDER_EXPECTED_STATUS_NAME,
    )
    return {
        "ok": True,
        "payload": {
            "success": True,
            "items": [
                {"sku_id": item.sku_id, "quantity": item.quantity, "unit_price": item.unit_price}
                for item in line_items
            ],
            "order_id": result.order_id,
            "order_no": result.order_no,
            "inner_status": result.inner_status,
            "inner_status_name": result.inner_status_name,
            "outer_status": result.outer_status,
            "outer_status_name": result.outer_status_name,
            "steps": result.steps,
        },
    }


def main() -> int:
    args = parse_args()
    try:
        line_items = resolve_line_items(args)
    except ValueError as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    last_error: Exception | None = None

    for attempt in range(1, LOGIN_RETRY_ATTEMPTS + 1):
        try:
            ctx, svc = _login_session()
            if args.step == "create-query":
                outcome = _run_create_query(args, ctx, svc, line_items)
            else:
                outcome = _run_full_flow(args, ctx, svc, line_items)

            if not outcome["ok"]:
                print(json.dumps(outcome["payload"], ensure_ascii=False, indent=2))
                return 1

            print(json.dumps(outcome["payload"], ensure_ascii=False, indent=2, default=str))
            return 0
        except LoginExpiredError as exc:
            last_error = exc
            if attempt >= LOGIN_RETRY_ATTEMPTS:
                break
            print(
                json.dumps(
                    {
                        "warning": "登录已过期，重新登录后重试",
                        "attempt": attempt,
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
        except Exception as exc:
            print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False, indent=2))
            return 1

    print(
        json.dumps(
            {
                "success": False,
                "error": str(last_error) if last_error else "登录过期且重试失败",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
