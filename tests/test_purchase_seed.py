"""销售转采购：状态解析和发货 payload，不打接口。"""
import pytest

from api.services.purchase_seed import (
    PO_STATUS_CANCELLED,
    PO_STATUS_CONFIRMING,
    PO_STATUS_DONE,
    PO_STATUS_PENDING_RECEIVE,
    PO_STATUS_PENDING_SHIP,
    PO_STATUS_STOCK_UP,
    advance_target_met,
    build_ship_payload,
    configured_supplier_member_id,
    current_po_stage,
    parse_po_status,
    remaining_steps,
    supplier_login_account,
    vendor_member_id_of,
    with_short_ship_step,
)


def test_parse_po_status_aliases():
    assert parse_po_status("订单确认中") == PO_STATUS_CONFIRMING
    assert parse_po_status("备货中") == PO_STATUS_STOCK_UP
    assert parse_po_status("完成") == PO_STATUS_DONE
    assert parse_po_status("采购退货") == "退货"
    with pytest.raises(ValueError):
        parse_po_status("挂账成功")


def test_build_ship_payload_uses_left_count():
    payload = build_ship_payload(
        110049,
        [
            {
                "orderProductId": 112645,
                "productId": 101863,
                "skuId": 108521,
                "quantity": "100",
                "leftCount": "100",
                "giftLeftCount": "0",
            }
        ],
    )
    assert payload == {
        "orderId": 110049,
        "products": [
            {
                "orderProductId": 112645,
                "productId": 101863,
                "skuId": 108521,
                "quantity": "100",
                "deliveryCount": "100",
                "giftDeliveryCount": "0",
            }
        ],
    }
    over = build_ship_payload(
        110049,
        [
            {
                "orderProductId": 112645,
                "productId": 101863,
                "skuId": 108521,
                "quantity": "100",
                "leftCount": "100",
                "giftLeftCount": "0",
            }
        ],
        quantity=120,
    )
    assert over["products"][0]["deliveryCount"] == "120"


def test_remaining_steps_from_stock_up_to_done():
    assert remaining_steps(PO_STATUS_STOCK_UP, PO_STATUS_DONE) == ("stock_up", "ship", "receive")
    assert remaining_steps(PO_STATUS_CONFIRMING, PO_STATUS_STOCK_UP) == ("agree_delivery",)
    assert remaining_steps(PO_STATUS_STOCK_UP, PO_STATUS_CANCELLED) == ("reduce",)
    assert remaining_steps(PO_STATUS_CONFIRMING, PO_STATUS_CANCELLED) == ("cancel",)
    with pytest.raises(AssertionError):
        remaining_steps(PO_STATUS_DONE, PO_STATUS_PENDING_SHIP)


def test_with_short_ship_step_only_when_under_qty():
    full = remaining_steps(PO_STATUS_STOCK_UP, PO_STATUS_DONE)
    assert with_short_ship_step(full, ship_qty=7, order_qty=10) == (
        "stock_up",
        "ship",
        "short_ship",
        "receive",
    )
    assert with_short_ship_step(full, ship_qty=12, order_qty=10) == full
    assert with_short_ship_step(full, ship_qty=None, order_qty=10) == full
    assert with_short_ship_step(("receive",), ship_qty=7, order_qty=10) == ("short_ship", "receive")


def test_vendor_member_id_falls_back_to_detail():
    assert vendor_member_id_of({"vendorMemberId": None, "vendorMemberName": "比亚迪股份有限公司"}) == 0
    assert vendor_member_id_of(
        {"vendorMemberId": None, "vendorMemberName": "比亚迪股份有限公司"},
        {"vendorMemberId": 104822, "vendorMemberName": "比亚迪股份有限公司"},
    ) == 104822
    assert vendor_member_id_of({"vendorMemberId": "104770"}) == 104770
    assert vendor_member_id_of({"vendor": {"memberId": 104822}}) == 104822
    assert configured_supplier_member_id("比亚迪股份有限公司") == 0
    assert supplier_login_account("19381795755", "比亚迪股份有限公司") == "19381795755"
    assert supplier_login_account("", "19381795755") == "19381795755"


def test_current_po_stage_from_flags():
    assert current_po_stage(
        {"innerStatusName": "订单备货中", "showConfirmReceipt": False, "showCancel": False},
        {"innerStatusName": "订单备货中", "showStockUp": True, "showDelivery": False},
    ) == PO_STATUS_STOCK_UP
    assert current_po_stage(
        {"innerStatusName": "挂账成功", "showConfirmReceipt": False},
        {"innerStatusName": "待确认发货", "showDelivery": True, "showStockUp": False},
    ) == PO_STATUS_PENDING_SHIP
    assert current_po_stage(
        {"innerStatusName": "已完成", "showAfterSales": True},
        {"innerStatusName": "已完成"},
    ) == PO_STATUS_DONE
    assert current_po_stage(
        {"innerStatusName": "待确认收货", "showAfterSales": True, "showConfirmReceipt": False},
        {"innerStatusName": "待确认收货"},
    ) == PO_STATUS_PENDING_RECEIVE
    assert current_po_stage(
        {"innerStatusName": "待确认收货", "showConfirmReceipt": False},
        {"innerStatusName": "已完成"},
    ) == PO_STATUS_PENDING_RECEIVE
    assert current_po_stage(
        {"innerStatusName": "已取消"},
        {"innerStatusName": "已取消"},
    ) == PO_STATUS_CANCELLED
    assert current_po_stage(
        {"innerStatusName": "已中止"},
        {"innerStatusName": "已中止"},
    ) == PO_STATUS_CANCELLED


def test_advance_target_met_actual_receiver():
    inspect = {
        "stage": PO_STATUS_PENDING_RECEIVE,
        "supplier_order": {"innerStatusName": "已完成", "outerStatusName": "待确认收货"},
    }
    assert advance_target_met(PO_STATUS_DONE, inspect) is True
    assert advance_target_met(PO_STATUS_PENDING_RECEIVE, inspect) is True
    assert advance_target_met(PO_STATUS_DONE, {"stage": PO_STATUS_STOCK_UP}) is False
