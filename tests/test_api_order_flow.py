import json

import allure
import pytest

from config.settings import (
    ORDER_BUYER_MEMBER_ID,
    ORDER_BUYER_MEMBER_NAME,
    ORDER_EXPECTED_INNER_STATUS,
    ORDER_EXPECTED_OUTER_STATUS,
    ORDER_EXPECTED_STATUS_NAME,
    ORDER_QUANTITY,
    ORDER_SKU_ID,
)

pytestmark = [pytest.mark.api, pytest.mark.order]


@allure.feature("订单接口造数")
@allure.story("代客下单全流程")
@allure.title("创建订单备货中状态的测试订单")
def test_create_order_pending_stock_up(crm_auth, order_service):
    result = order_service.create_order_pending_stock_up(
        crm_auth,
        buyer_member_id=ORDER_BUYER_MEMBER_ID,
        buyer_member_name=ORDER_BUYER_MEMBER_NAME,
        sku_id=ORDER_SKU_ID,
        quantity=ORDER_QUANTITY,
        expected_inner_status=ORDER_EXPECTED_INNER_STATUS,
        expected_outer_status=ORDER_EXPECTED_OUTER_STATUS,
        expected_status_name=ORDER_EXPECTED_STATUS_NAME,
    )
    allure.attach(
        json.dumps(
            {
                "order_id": result.order_id,
                "order_no": result.order_no,
                "inner_status": result.inner_status,
                "inner_status_name": result.inner_status_name,
                "outer_status": result.outer_status,
                "outer_status_name": result.outer_status_name,
                "steps": result.steps,
            },
            ensure_ascii=False,
            indent=2,
        ),
        name="order_flow_detail",
        attachment_type=allure.attachment_type.JSON,
    )
    assert result.inner_status == ORDER_EXPECTED_INNER_STATUS
    assert result.outer_status == ORDER_EXPECTED_OUTER_STATUS
    assert result.inner_status_name == ORDER_EXPECTED_STATUS_NAME
    assert result.outer_status_name == ORDER_EXPECTED_STATUS_NAME
