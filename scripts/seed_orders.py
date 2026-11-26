"""按商城、客户、销售、金额、状态批量造销售订单。

单笔:
  python scripts/seed_orders.py --mall cn --customer "衢州白马投资有限公司" --sales "甜甜" --amount 100 --status 待签署合同

多笔（JSON 数组，每笔可以不同）:
  python scripts/seed_orders.py --file testdata/order/seed_orders.example.json

只核对客户和销售、不写订单:
  python scripts/seed_orders.py --file testdata/order/seed_orders.example.json --dry-run

状态: 待签署合同、待支付、待确认支付结果、订单备货中（别名 备货中 / 有效）、待确认发货、已取消。
待确认收货、已完成还没有推进接口。
金额、采购数量、items 三选一。只写金额时，按目录单价反推整数数量；只写数量时，金额按目录价 × 数量 + 运费生成。
多商品在 JSON 里写 "items": [{"sku_id": 1, "quantity": 10}, {"sku_id": 2, "quantity": 20}]。
不能手改单价。销售会写成订单客户经理；默认同时把商城客户经理改成该销售。
中文会员包邮：加 --free-shipping，或在 JSON 里写 "free_shipping": true。
接口是 updateMemberCustomSetting，只改 isFreeShipping，配送/开票/签合同沿用客户当前值。
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.env_loader import bootstrap_env, is_prod_env, peek_cli_env

_ACTIVE_ENV = bootstrap_env(peek_cli_env())

from api.client import ApiClient
from api.services.order_seed import (
    OrderSeedService,
    OrderSeedSpec,
    load_order_specs,
    parse_amount,
    parse_mall,
    parse_status,
    supported_status_text,
)
from config.settings import API_TIMEOUT_SECONDS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按商城/客户/销售/金额/状态批量造订单")
    parser.add_argument("--env", choices=["test", "uat", "prod"], default=None)
    parser.add_argument("--mall", default="", help="cn/中文商城 或 en/英文商城")
    parser.add_argument("--customer", default="", help="商城客户名称，须完全匹配")
    parser.add_argument("--sales", default="", help="销售姓名，须完全匹配在职用户")
    parser.add_argument("--amount", default="", help="订单总金额，含运费。与 --quantity 二选一")
    parser.add_argument("--quantity", type=int, default=0, help="采购数量。传入后按目录价计算金额")
    parser.add_argument("--status", default="", help=f"订单状态：{supported_status_text()}")
    parser.add_argument("--sku-id", type=int, default=0, help="不传则用该商城默认商品")
    parser.add_argument("--member-id", type=int, default=0, help="客户重名时指定 memberId")
    parser.add_argument("--buyer-user-id", type=int, default=0, help="采购会员有多个登录用户时指定")
    parser.add_argument("--file", default="", help="多笔订单 JSON 文件")
    parser.add_argument("--orders", default="", help="多笔订单 JSON 字符串")
    parser.add_argument("--dry-run", action="store_true", help="只解析客户和销售，不创建订单")
    parser.add_argument(
        "--skip-assign-sales",
        action="store_true",
        help="不修改商城客户经理，只把销售写到订单上",
    )
    parser.add_argument(
        "--free-shipping",
        action="store_true",
        help="中文商城把该会员设为包邮后再下单",
    )
    parser.add_argument("--list-status", action="store_true", help="打印可造状态后退出")
    return parser.parse_args()


def _specs_from_args(args: argparse.Namespace) -> list[OrderSeedSpec]:
    if args.file and args.orders:
        raise ValueError("不要同时传 --file 和 --orders")
    if args.file:
        return load_order_specs(Path(args.file).read_text(encoding="utf-8"))
    if args.orders:
        return load_order_specs(args.orders)
    if not all([args.mall, args.customer, args.sales, args.status]):
        raise ValueError("单笔造数需要 --mall --customer --sales --status，以及 --amount 或 --quantity")
    if not args.amount and not args.quantity:
        raise ValueError("单笔造数需要 --amount 或 --quantity")
    raw = {
        "mall": args.mall,
        "customer": args.customer,
        "sales": args.sales,
        "status": args.status,
    }
    if args.amount:
        raw["amount"] = parse_amount(args.amount)
    if args.quantity:
        raw["quantity"] = args.quantity
    if args.sku_id:
        raw["sku_id"] = args.sku_id
    if args.member_id:
        raw["member_id"] = args.member_id
    if args.buyer_user_id:
        raw["buyer_user_id"] = args.buyer_user_id
    # 先走同一套校验
    raw["mall"] = parse_mall(args.mall)
    raw["status"] = parse_status(args.status)
    return load_order_specs(json.dumps([raw], ensure_ascii=False))


def main() -> int:
    args = parse_args()
    if args.list_status:
        print(json.dumps({"status": supported_status_text().split("、")}, ensure_ascii=False, indent=2))
        return 0
    if is_prod_env(_ACTIVE_ENV):
        print(json.dumps({"success": False, "error": "生产环境禁止造订单"}, ensure_ascii=False))
        return 1
    try:
        specs = _specs_from_args(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    if args.free_shipping:
        specs = [replace(spec, free_shipping=True) for spec in specs]
    service = OrderSeedService(ApiClient(timeout=API_TIMEOUT_SECONDS))
    try:
        if args.dry_run:
            result = service.preview(specs)
        else:
            result = service.create_many(specs, assign_sales=not args.skip_assign_sales)
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("success", result.get("dry_run")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
