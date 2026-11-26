from api.services.aftersale_seed import (
    AS_DONE,
    AS_RECEIVE,
    build_return_line,
    current_as_stage,
    parse_as_status,
)


def test_parse_as_status_aliases():
    assert parse_as_status("已确认售后完成") == AS_DONE
    assert parse_as_status("待确认退货收货") == AS_RECEIVE
    assert parse_as_status("待确认收货") == AS_RECEIVE
    assert parse_as_status("采购商退货发货") == "待发货"
    assert parse_as_status("待退货发货") == "待发货"


def test_current_as_stage_done():
    assert current_as_stage({"innerStatusName": "已确认售后完成", "outerStatusName": "售后完成"}) == AS_DONE
    assert current_as_stage({"innerStatusName": "待提交", "outerStatusName": "待确认申请单"}) == "待提交"
    assert current_as_stage({"innerStatusName": "待确认退货发货", "outerStatusName": "待退货发货"}) == "待发货"
    assert current_as_stage({"innerStatusName": "待确认退货收货", "outerStatusName": "待确认收货"}) == AS_RECEIVE


def test_build_return_line_uses_nested_product_id():
    line = build_return_line(
        {"orderNo": "DCV7ECS65", "orderId": 110195, "contractId": 0, "contractNo": ""},
        {
            "skuId": 108521,
            "productId": 112794,
            "name": "鱼竿包装盒",
            "quantity": "10",
            "maxReturnOrReplaceCount": "10",
            "price": "1.25",
            "amount": "12.50",
            "paidAmount": "12.50",
            "tax": True,
            "spec": "测试规格",
        },
        order_id=110195,
        order_no="DCV7ECS65",
        return_count=1,
    )
    assert line["skuId"] == 108521
    assert line["orderRecordId"] == 112794
    assert line["returnCount"] == 1
    assert line["productName"] == "鱼竿包装盒"
