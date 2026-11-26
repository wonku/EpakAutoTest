"""销售订单转采购。默认 dry-run，不提交。

只读预览（看板验证期间用这个）：
  python scripts/seed_purchase_from_sales.py --order-id 110132
  python scripts/seed_purchase_from_sales.py --order-id 110132 --vendor-member-id 104770 --po-status 备货中
  python scripts/seed_purchase_from_sales.py --po-id 110149
  python scripts/seed_purchase_from_sales.py --po-id 110149 --po-status 完成

真正提交（测试/UAT，生产会拒绝；看板还在验时不要加 --submit）：
  python scripts/seed_purchase_from_sales.py --order-id 110132 --vendor-member-id 104770 --po-status 确认中 --submit
  python scripts/seed_purchase_from_sales.py --po-id 110149 --po-status 完成 --submit

操作人是订单采购员雷翰，接口是 /api/order/transition/submit，不是 /vendor/transfer。
--vendor-member-id：104770 字节跳动 / 105022 银河电子。
--po-status：确认中、备货中、待确认发货、待确认收货、已完成、已取消、退货。
少发：--ship-qty 7 会在发货后由采购员短装确认剩余未发。
采购退货也可：python scripts/seed_mall_flow.py po-return --po-no Dxxxx --status 售后完成
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.env_loader import bootstrap_env, is_prod_env, peek_cli_env

_ACTIVE_ENV = bootstrap_env(peek_cli_env())

from api.client import ApiClient
from api.services.purchase_seed import PurchaseFromSalesSeedService, parse_po_status
from config.settings import API_TIMEOUT_SECONDS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="销售订单转采购（默认只预览）")
    parser.add_argument("--env", choices=["test", "uat", "prod"], default=None)
    parser.add_argument("--mall", default="cn", help="cn / en")
    parser.add_argument("--order-id", type=int, default=0, help="销售单 orderId，转单用")
    parser.add_argument("--po-id", type=int, default=0, help="已有采购单 orderId，只推进状态、不再转单")
    parser.add_argument("--po-no", default="", help="已有采购单号，和 --po-id 二选一")
    parser.add_argument("--vendor-member-id", type=int, default=0, help="指定上游 memberId，不传则用第一个")
    parser.add_argument(
        "--po-status",
        default="",
        help="采购目标状态：确认中 / 备货中 / 待确认发货 / 待确认收货 / 已完成 / 已取消",
    )
    parser.add_argument("--confirm-delivery", action="store_true", help="转单后供应商同意交期，等价 --po-status 备货中")
    parser.add_argument("--ship-qty", type=int, default=0, help="发货数量；小于确认数量时采购员短装确认少发")
    parser.add_argument("--cancel-reason", default="毛利看板造数取消")
    parser.add_argument("--submit", action="store_true", help="真正提交；默认只拼 payload")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if is_prod_env(_ACTIVE_ENV):
        print(json.dumps({"success": False, "error": "生产环境禁止造采购单"}, ensure_ascii=False))
        return 1
    if not args.order_id and not args.po_id and not args.po_no:
        print(json.dumps({"success": False, "error": "请传 --order-id 或 --po-id/--po-no"}, ensure_ascii=False))
        return 1
    target = ""
    if args.po_status:
        try:
            target = parse_po_status(args.po_status)
        except ValueError as exc:
            print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
            return 1
    svc = PurchaseFromSalesSeedService(ApiClient(timeout=API_TIMEOUT_SECONDS), mall=args.mall)
    if args.po_id or args.po_no:
        if target:
            result = svc.advance_existing_purchase(
                order_id=args.po_id or None,
                order_no=args.po_no or None,
                target_status=target,
                dry_run=not args.submit,
                cancel_reason=args.cancel_reason,
                ship_qty=args.ship_qty or None,
            )
        else:
            result = svc.inspect_purchase(order_id=args.po_id or None, order_no=args.po_no or None)
    else:
        result = svc.transfer_existing_sales_order(
            order_id=args.order_id,
            vendor_member_id=args.vendor_member_id or None,
            dry_run=not args.submit,
            po_status=target or None,
            confirm_delivery=args.confirm_delivery,
            cancel_reason=args.cancel_reason,
            ship_qty=args.ship_qty or None,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
