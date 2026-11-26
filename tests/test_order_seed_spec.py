"""订单批量造数：清单解析与金额回填，不打接口。"""
import pytest

from api.services.order_seed import (
    EN_AGENT_TRADE_MODE,
    EN_PAY_NODE,
    PAY_ACCOUNT_PERIOD,
    PAY_OFFLINE,
    STATUS_CANCELLED,
    STATUS_PENDING_CONTRACT,
    STATUS_PENDING_PAY,
    STATUS_PENDING_PAY_CONFIRM,
    STATUS_PENDING_SHIP,
    STATUS_STOCK_UP,
    apply_account_period_pay,
    apply_en_agent_terms,
    apply_free_shipping_freight,
    stock_up_products,
    assert_quantity_allowed,
    load_order_specs,
    mall_profile,
    member_free_shipping_payload,
    minimum_order_quantity,
    parse_pay,
    parse_status,
    pick_buyer_user,
    solve_quantity,
    status_reached,
)


def test_free_shipping_keeps_other_member_switches():
    payload = member_free_shipping_payload(
        {
            "memberId": 105145,
            "isFreeShipping": False,
            "isDistribution": False,
            "isAutomaticInvoicing": True,
            "isSignContract": True,
            "saleOrgType": 5,
            "hierarchicalConfiguration": 2,
        },
        free_shipping=True,
    )
    assert payload == {
        "memberId": 105145,
        "isFreeShipping": True,
        "isDistribution": False,
        "isAutomaticInvoicing": True,
        "isSignContract": True,
        "saleOrgType": 5,
        "hierarchicalConfiguration": 2,
    }


def test_free_shipping_flag_parses_from_order_json():
    specs = load_order_specs(
        '{"mall":"cn","customer":"甲","sales":"乙","amount":1,"status":"待签署合同","free_shipping":true}'
    )
    assert specs[0].free_shipping is True


def test_load_mixed_orders():
    specs = load_order_specs(
        """
        [
          {"mall": "中文商城", "customer": "甲客户", "sales": "张三", "amount": "100.5", "status": "待签署"},
          {"mall": "en", "customer": "Beta Co", "sales": "Ann", "amount": 0, "status": "有效", "sku_id": 12}
        ]
        """
    )
    assert len(specs) == 2
    assert specs[0].mall == "cn"
    assert specs[0].amount == 100.5
    assert specs[0].status == STATUS_PENDING_CONTRACT
    assert specs[1].mall == "en"
    assert specs[1].status == STATUS_STOCK_UP
    assert specs[1].sku_id == 12


def test_status_aliases():
    assert parse_status("备货中") == STATUS_STOCK_UP
    assert parse_status("取消") == STATUS_CANCELLED
    assert parse_pay("月结") == PAY_ACCOUNT_PERIOD
    assert parse_pay("") == PAY_OFFLINE
    assert status_reached(STATUS_STOCK_UP, "挂账成功") is True


def test_account_period_pay_is_monthly_settlement():
    payload = {
        "sumPrice": 12.5,
        "payments": [{"payPrice": "12.50", "payType": 2, "payChannel": 5}],
    }
    apply_account_period_pay(payload)
    assert payload["payType"] == 5
    assert payload["payChannel"] == 8
    assert payload["payments"][0]["payChannelName"] == "月结"
    assert payload["payments"][0]["payTypeName"] == "结算支付"


def test_apply_free_shipping_freight_zeros_freight_and_sum():
    payload = {
        "freight": 35.0,
        "sumPrice": 246.2,
        "payments": [{"payPrice": "246.20"}],
        "products": [{"freightPrice": 35.0, "money": 211.2}],
    }
    apply_free_shipping_freight(payload)
    assert payload["freight"] == 0
    assert payload["sumPrice"] == 211.2
    assert payload["payments"][0]["payPrice"] == "211.20"
    assert payload["products"][0]["freightPrice"] == 0


def test_solve_quantity_uses_catalog_price_plus_freight():
    assert solve_quantity(25, 0, 100) == 4
    assert solve_quantity(25, 10, 110) == 4


def test_solve_quantity_rejects_amount_that_is_not_a_multiple():
    with pytest.raises(AssertionError):
        solve_quantity(25, 0, 80)


def test_load_currency_id_for_en_orders():
    specs = load_order_specs(
        '{"mall":"en","customer":"A","sales":"B","quantity":100,"status":"待确认支付结果","currency_id":1}'
    )
    assert specs[0].currency_id == 1


def test_load_multi_item_orders():
    specs = load_order_specs(
        """
        [
          {
            "mall": "cn",
            "customer": "甲",
            "sales": "乙",
            "status": "待确认支付结果",
            "items": [
              {"sku_id": 11, "quantity": 10},
              {"sku_id": 22, "quantity": 20}
            ]
          }
        ]
        """
    )
    assert specs[0].amount is None
    assert specs[0].items is not None
    assert [(line.sku_id, line.quantity) for line in specs[0].items] == [(11, 10), (22, 20)]


def test_quantity_can_replace_amount():
    specs = load_order_specs(
        '{"mall":"en","customer":"Beta","sales":"Ann","quantity":100000,"status":"待支付","buyer_user_id":101954}'
    )
    assert specs[0].quantity == 100000
    assert specs[0].amount is None
    assert specs[0].status == STATUS_PENDING_PAY
    assert specs[0].buyer_user_id == 101954


def test_pay_confirm_status_and_unwired_statuses():
    assert parse_status("待确认支付结果") == STATUS_PENDING_PAY_CONFIRM
    assert parse_status("待确认发货") == STATUS_PENDING_SHIP
    with pytest.raises(ValueError, match="待确认收货"):
        parse_status("待确认收货")
    with pytest.raises(ValueError, match="已完成"):
        parse_status("已完成")


def test_stock_up_products_from_order_detail():
    products = stock_up_products(
        {
            "data": {
                "product": {
                    "products": [
                        {
                            "orderProductId": 101238,
                            "productId": 100423,
                            "skuId": 105212,
                            "quantity": 100000,
                        }
                    ]
                }
            }
        }
    )
    assert products == [
        {
            "orderProductId": 101238,
            "productId": 100423,
            "skuId": 105212,
            "quantity": "100000",
        }
    ]


def test_pick_single_buyer_user_and_reject_duplicates():
    only = pick_buyer_user([{"userId": 9, "name": "买家"}])
    assert only["userId"] == 9
    picked = pick_buyer_user(
        [{"userId": 1, "name": "甲"}, {"id": 2, "userName": "乙"}],
        user_id=2,
    )
    assert picked["userName"] == "乙"
    with pytest.raises(AssertionError, match="buyer_user_id"):
        pick_buyer_user([{"userId": 1, "name": "甲"}, {"userId": 2, "name": "乙"}])


def test_minimum_order_quantity():
    assert minimum_order_quantity({"minOrder": 100000}) == 100000
    assert minimum_order_quantity({"minOrder": "1.00"}) == 1
    with pytest.raises(AssertionError, match="起订量"):
        assert_quantity_allowed({"minOrder": 100000}, 1)


def test_en_agent_terms_follow_captured_order():
    profile = mall_profile("en")
    assert profile.trade_mode == EN_AGENT_TRADE_MODE == 3
    assert profile.currency_id == 3
    assert profile.shop_classify == 2
    payload = {
        "products": [{"money": 8000}],
        "payments": [
            {
                "payPrice": "8323.00",
                "payNode": "首付",
                "payNodes": [{"payNode": "首付"}],
                "payChannels": [{"isDefault": 0, "payNodes": [{"payNode": "首付"}]}],
            }
        ],
        "payTypeMessageObj": {
            "payChannel": {"isDefault": 0, "payNodes": [{"payNode": "首付"}]},
        },
    }
    apply_en_agent_terms(payload)
    payment = payload["payments"][0]
    assert payment["payPrice"] == "8000.00"
    assert payment["payNode"] == EN_PAY_NODE
    assert payment["payChannels"][0]["payNodes"][0]["payNode"] == EN_PAY_NODE
    assert payload["payTypeMessageObj"]["payChannel"]["payNodes"][0]["payNode"] == EN_PAY_NODE
