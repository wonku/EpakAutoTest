from api.services.mall_flow import (
    ACCOUNT_PERIOD_CUSTOMER,
    ACCOUNT_PERIOD_MEMBER_ID,
    DEFAULT_CUSTOMER,
    resolve_seed_customer,
    scenario_brief,
)
from api.services.order_seed import PAY_ACCOUNT_PERIOD, PAY_OFFLINE
from config.settings import ORDER_BUYER_MEMBER_ID


def test_resolve_seed_customer_picks_account_period_customer():
    name, member_id, _buyer = resolve_seed_customer(pay="账期")
    assert name == ACCOUNT_PERIOD_CUSTOMER
    assert member_id == ACCOUNT_PERIOD_MEMBER_ID
    name, member_id, _buyer = resolve_seed_customer(pay="月结", customer=DEFAULT_CUSTOMER)
    assert name == ACCOUNT_PERIOD_CUSTOMER


def test_resolve_seed_customer_offline_keeps_default():
    name, member_id, _buyer = resolve_seed_customer(pay="线下支付")
    assert name == DEFAULT_CUSTOMER
    assert member_id == ORDER_BUYER_MEMBER_ID
    assert PAY_OFFLINE == "线下支付"


def test_scenario_brief_reads_nested_after_sale():
    row = scenario_brief(
        {
            "ok": True,
            "kind": "采购售后",
            "sale": {
                "order_no": "D1",
                "order_id": 1,
                "pay": PAY_ACCOUNT_PERIOD,
                "order_customer_manager": "国内一组在职",
                "customer": ACCOUNT_PERIOD_CUSTOMER,
            },
            "purchase": {"order_id": 2, "order_no": "P1"},
            "after_sale": {"apply_no": "TH1", "stage": "售后完成", "inner": "已确认售后完成"},
        }
    )
    assert row["sale_no"] == "D1"
    assert row["po_no"] == "P1"
    assert row["apply_no"] == "TH1"
    assert row["manager"] == "国内一组在职"
