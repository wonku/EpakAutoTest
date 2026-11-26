"""中文/英文商城：销售单 / 转采购 / 销售退货 / 采购退货。默认真正造数，生产会拒绝。

新建销售单到指定状态（客户经理写在订单上，默认不改客户档案）:
  python scripts/seed_mall_flow.py sale --status 订单备货中 --sales 国内一组在职 --sku-id 108521 --quantity 10

新建销售单并转采购到指定状态:
  python scripts/seed_mall_flow.py sale-po --po-status 已完成 --sales 国内一组在职

把已有销售单转到采购单指定状态:
  python scripts/seed_mall_flow.py transfer --order-no Dxxxx --po-status 备货中

对销售单做代客退货到指定状态:
  python scripts/seed_mall_flow.py sale-return --order-no Dxxxx --status 售后完成

对采购单做采购退货到指定状态:
  python scripts/seed_mall_flow.py po-return --po-no Dxxxx --status 售后完成

从新建销售单一路到采购售后完成:
  python scripts/seed_mall_flow.py full --sales 国内一组在职

新造销售单转采购：多发 / 少发 / 供应商确认后取消（不改已有单）:
  python scripts/seed_mall_flow.py po-diff --kind 多发 --sales 国内一组在职
  python scripts/seed_mall_flow.py po-diff --kind 取消 --sales 国内一组在职
  python scripts/seed_mall_flow.py po-diff --kind all --pay 账期 --sales 国内一组在职

不转单销售单手工发货多发/少发（填数量+勾选全部发货完成；少发自动出关联售后）:
  python scripts/seed_mall_flow.py sale-diff --kind 多发 --sales 国内一组在职
  python scripts/seed_mall_flow.py sale-diff --kind 少发 --sales 国内一组在职

正常确认/正常确认/超发/少发/取消/采购售后，账期和线下各一套（不改已有单）:
  python scripts/seed_mall_flow.py suite --pay both --sales 国内一组在职
  python scripts/seed_mall_flow.py --env uat --mall both suite --pay both --sales 国内一组在职
确认后取消：易食包商家把数量调减到 0，采购单变为已取消。不改已有单。

英文商城造一套（新建海外客户、无销售退货）:
  python scripts/seed_mall_flow.py --env test --mall en board --new-en-customer --sales 国内一组在职

只预览不写:
  python scripts/seed_mall_flow.py transfer --order-id 110132 --po-status 已完成 --dry-run
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
from api.services.mall_flow import DEFAULT_QUANTITY, DEFAULT_SALES, MallFlowService
from config.settings import API_TIMEOUT_SECONDS


def _add_mall(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mall", default=argparse.SUPPRESS, help="cn / en")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="中文/英文商城销售/采购/售后造数")
    parser.add_argument("--env", choices=["test", "uat", "prod"], default=None)
    parser.add_argument("--mall", default="cn", help="cn / en")
    sub = parser.add_subparsers(dest="action", required=True)

    sale = sub.add_parser("sale", help="新建销售单到指定状态")
    _add_sale_args(sale)
    sale.add_argument("--status", required=True, help="销售目标状态，如 订单备货中 / 待确认发货")

    sale_po = sub.add_parser("sale-po", help="新建销售单并转采购到指定状态")
    _add_sale_args(sale_po)
    sale_po.add_argument("--po-status", required=True, help="采购目标状态，如 备货中 / 已完成")
    sale_po.add_argument("--vendor-member-id", type=int, default=0)
    sale_po.add_argument("--ship-qty", type=int, default=0, help="发货/收货数量，不传则按确认数量")
    sale_po.add_argument("--dry-run", action="store_true")

    transfer = sub.add_parser("transfer", help="已有销售单转采购到指定状态")
    _add_mall(transfer)
    transfer.add_argument("--order-id", type=int, default=0)
    transfer.add_argument("--order-no", default="")
    transfer.add_argument("--po-status", required=True)
    transfer.add_argument("--vendor-member-id", type=int, default=0)
    transfer.add_argument("--dry-run", action="store_true")

    sale_return = sub.add_parser("sale-return", help="对销售单代客退货到指定状态")
    _add_mall(sale_return)
    sale_return.add_argument("--order-id", type=int, default=0)
    sale_return.add_argument("--order-no", default="")
    sale_return.add_argument("--status", default="售后完成")
    sale_return.add_argument("--return-count", type=int, default=1)
    sale_return.add_argument("--dry-run", action="store_true")

    po_return = sub.add_parser("po-return", help="对采购单退货到指定状态")
    _add_mall(po_return)
    po_return.add_argument("--po-id", type=int, default=0)
    po_return.add_argument("--po-no", default="")
    po_return.add_argument("--status", default="售后完成")
    po_return.add_argument("--return-count", type=int, default=1)
    po_return.add_argument("--dry-run", action="store_true")

    full = sub.add_parser("full", help="新建销售单+转采购已完成+采购退货到指定售后状态")
    _add_sale_args(full)
    full.add_argument("--vendor-member-id", type=int, default=0)
    full.add_argument("--return-count", type=int, default=1)
    full.add_argument("--status", default="售后完成", help="采购售后目标状态，如 待退货发货 / 售后完成")
    full.add_argument("--dry-run", action="store_true")

    po_diff = sub.add_parser("po-diff", help="新造销售单转采购：多发/少发/确认后取消")
    _add_sale_args(po_diff)
    po_diff.add_argument("--kind", required=True, help="正常确认 / 多发 / 少发 / 取消 / all")
    po_diff.add_argument("--vendor-member-id", type=int, default=0)
    po_diff.add_argument("--over-qty", type=int, default=12, help="多发完成数量，默认确认10发12")
    po_diff.add_argument("--under-qty", type=int, default=7, help="少发完成数量，默认确认10发7")
    po_diff.add_argument("--dry-run", action="store_true")

    sale_diff = sub.add_parser("sale-diff", help="不转单销售单手工发货：多发/少发")
    _add_sale_args(sale_diff)
    sale_diff.add_argument("--kind", required=True, help="多发 / 少发")
    sale_diff.add_argument("--over-qty", type=int, default=12, help="多发实发数量")
    sale_diff.add_argument("--under-qty", type=int, default=7, help="少发实发数量")

    pack = sub.add_parser("pack", help="新造一套：销售单/销售退货/采购退货/多发/少发/取消")
    _add_sale_args(pack)
    pack.add_argument("--vendor-member-id", type=int, default=0)

    board = sub.add_parser("board", help="新造：销售单/转单确认/转单完成/多发退货/少发退货/取消，无销售退货")
    _add_sale_args(board)
    board.add_argument("--vendor-member-id", type=int, default=0)
    board.add_argument("--new-en-customer", action="store_true", help="先新建英文海外客户再造单")

    suite = sub.add_parser("suite", help="新造正常确认/超发/少发/取消/采购售后；--pay both；--mall both")
    _add_sale_args(suite)
    suite.set_defaults(quantity=0, sku_id=0)
    suite.add_argument("--vendor-member-id", type=int, default=0)
    suite.add_argument("--status", default="售后完成", help="采购售后目标状态")
    return parser.parse_args()


def _add_sale_args(parser: argparse.ArgumentParser) -> None:
    _add_mall(parser)
    parser.add_argument("--customer", default="")
    parser.add_argument("--sales", default=DEFAULT_SALES)
    parser.add_argument("--sku-id", type=int, default=0)
    parser.add_argument("--quantity", type=int, default=DEFAULT_QUANTITY)
    parser.add_argument("--member-id", type=int, default=0)
    parser.add_argument(
        "--assign-sales",
        action="store_true",
        help="同时改商城客户档案上的客户经理；默认只写到订单",
    )
    parser.add_argument("--pay", default="", help="销售单支付：线下支付 / 账期（月结）")


def main() -> int:
    args = parse_args()
    if is_prod_env(_ACTIVE_ENV):
        print(json.dumps({"success": False, "error": "生产环境禁止造数"}, ensure_ascii=False))
        return 1
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    svc = MallFlowService(ApiClient(timeout=API_TIMEOUT_SECONDS), mall=getattr(args, "mall", "cn"))
    try:
        result = _dispatch(svc, args)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2, default=str))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("ok") or result.get("success") else 1


def _dispatch(svc: MallFlowService, args: argparse.Namespace) -> dict:
    member_id = args.member_id or None if hasattr(args, "member_id") else None
    assign_sales = bool(getattr(args, "assign_sales", False))
    pay = getattr(args, "pay", "") or ""
    if args.action == "sale":
        return svc.seed_sale(
            status=args.status,
            customer=args.customer,
            sales=args.sales,
            sku_id=args.sku_id,
            quantity=args.quantity,
            member_id=member_id,
            assign_sales=assign_sales,
            pay=pay,
        )
    if args.action == "sale-po":
        return svc.seed_sale_and_po(
            po_status=args.po_status,
            customer=args.customer,
            sales=args.sales,
            sku_id=args.sku_id,
            quantity=args.quantity,
            member_id=member_id,
            vendor_member_id=args.vendor_member_id,
            assign_sales=assign_sales,
            dry_run=args.dry_run,
            ship_qty=args.ship_qty or None,
            pay=pay,
        )
    if args.action == "transfer":
        return svc.transfer_sale(
            order_id=args.order_id or None,
            order_no=args.order_no or None,
            po_status=args.po_status,
            vendor_member_id=args.vendor_member_id,
            dry_run=args.dry_run,
        )
    if args.action == "sale-return":
        return svc.return_sale(
            order_id=args.order_id or None,
            order_no=args.order_no or None,
            status=args.status,
            return_count=args.return_count,
            dry_run=args.dry_run,
        )
    if args.action == "po-return":
        return svc.return_purchase(
            order_id=args.po_id or None,
            order_no=args.po_no or None,
            status=args.status,
            return_count=args.return_count,
            dry_run=args.dry_run,
        )
    if args.action == "full":
        return svc.seed_full(
            customer=args.customer,
            sales=args.sales,
            sku_id=args.sku_id,
            quantity=args.quantity,
            member_id=member_id,
            vendor_member_id=args.vendor_member_id,
            assign_sales=assign_sales,
            return_count=args.return_count,
            as_status=args.status,
            dry_run=args.dry_run,
            pay=pay,
        )
    if args.action == "suite":
        kwargs = {
            "customer": args.customer,
            "sales": args.sales,
            "sku_id": args.sku_id,
            "quantity": args.quantity,
            "member_id": member_id,
            "vendor_member_id": args.vendor_member_id or None,
            "assign_sales": assign_sales,
            "as_status": args.status,
        }
        mall_raw = str(getattr(args, "mall", "cn") or "cn").strip().lower()
        if mall_raw in ("both", "all", "全部", "cn,en", "en,cn"):
            return MallFlowService(ApiClient(timeout=API_TIMEOUT_SECONDS), mall="cn").seed_suite_malls(
                malls=("cn", "en"), **kwargs
            )
        if (pay or "both").strip().lower() in ("", "both", "all", "全部"):
            return svc.seed_suite_both(**kwargs)
        return svc.seed_suite(pay=pay, **kwargs)
    if args.action == "po-diff":
        kwargs = {
            "customer": args.customer,
            "sales": args.sales,
            "sku_id": args.sku_id,
            "quantity": args.quantity,
            "member_id": member_id,
            "vendor_member_id": args.vendor_member_id,
            "assign_sales": assign_sales,
            "dry_run": args.dry_run,
            "over_qty": args.over_qty,
            "under_qty": args.under_qty,
            "pay": pay,
        }
        if args.kind.strip().lower() in ("all", "全部"):
            return svc.seed_po_diff_all(**kwargs)
        return svc.seed_po_diff_scenario(kind=args.kind, **kwargs)
    if args.action == "sale-diff":
        return svc.seed_sale_manual_diff(
            kind=args.kind,
            customer=args.customer,
            sales=args.sales,
            sku_id=args.sku_id,
            quantity=args.quantity,
            member_id=member_id,
            assign_sales=assign_sales,
            over_qty=args.over_qty,
            under_qty=args.under_qty,
            pay=pay,
        )
    if args.action == "pack":
        return svc.seed_pack(
            customer=args.customer or None,
            sales=args.sales,
            sku_id=args.sku_id or None,
            quantity=args.quantity,
            member_id=member_id,
            vendor_member_id=args.vendor_member_id or None,
            assign_sales=assign_sales,
        )
    if args.action == "board":
        created = None
        customer = args.customer or None
        board_member_id = member_id
        if getattr(args, "new_en_customer", False):
            created = svc.create_en_customer(sales=args.sales)
            if not created.get("ok"):
                return created
            customer = created["company"]
            board_member_id = created["member_id"]
        result = svc.seed_board(
            customer=customer,
            sales=args.sales,
            sku_id=args.sku_id or None,
            quantity=args.quantity,
            member_id=board_member_id,
            vendor_member_id=args.vendor_member_id or None,
            assign_sales=assign_sales,
        )
        if created:
            result["customer_created"] = created
        return result
    return {"ok": False, "error": f"未知动作 {args.action}"}


if __name__ == "__main__":
    raise SystemExit(main())
