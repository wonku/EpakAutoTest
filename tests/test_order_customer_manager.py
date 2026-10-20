"""代客下单入参必须带客户经理。不打接口。"""
from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.order_service import OrderService


def test_ensure_order_customer_manager_writes_payload(monkeypatch):
    def fake_apply(self, ctx, payload, **kwargs):
        payload["customerManagerId"] = 13
        payload["customerManager"] = "邵雪芬"
        payload["customerManagerName"] = "邵雪芬"
        return payload

    monkeypatch.setattr(
        "api.services.crm_inquiry_service.CrmInquiryService.apply_customer_manager_to_order",
        fake_apply,
    )
    payload: dict = {}
    OrderService(ApiClient()).ensure_order_customer_manager(
        AuthContext(member_id=6, user_id=2, token="t"),
        payload,
        buyer_member_id=104440,
        buyer_member_name="衢州白马投资有限公司",
    )
    assert payload["customerManagerId"] == 13
    assert payload["customerManager"] == "邵雪芬"
    assert payload["customerManagerName"] == "邵雪芬"
