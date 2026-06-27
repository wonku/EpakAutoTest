import allure
import json


@allure.feature("CRM 接口造数")
@allure.story("销售线索")
@allure.title("调用接口创建销售线索")
def test_create_sales_lead_by_api(auth_login_data, crm_lead_service):
    payload = crm_lead_service.build_random_lead_payload(
        member_id=auth_login_data["memberId"],
        user_id=auth_login_data["userId"],
        token=auth_login_data["token"],
    )
    body = crm_lead_service.create_lead(
        member_id=auth_login_data["memberId"],
        user_id=auth_login_data["userId"],
        token=auth_login_data["token"],
        payload=payload,
    )
    allure.attach(
        json.dumps({"request": payload, "response": body}, ensure_ascii=False, indent=2),
        name="create_lead_api_detail",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"创建线索失败: {body}"


@allure.feature("CRM 接口造数")
@allure.story("销售线索")
@allure.title("调用接口创建德国销售线索")
def test_create_sales_lead_germany_by_api(auth_login_data, crm_lead_service):
    payload = crm_lead_service.build_random_lead_payload(
        member_id=auth_login_data["memberId"],
        user_id=auth_login_data["userId"],
        token=auth_login_data["token"],
        country="德国",
    )
    body = crm_lead_service.create_lead(
        member_id=auth_login_data["memberId"],
        user_id=auth_login_data["userId"],
        token=auth_login_data["token"],
        payload=payload,
    )
    relation_id = crm_lead_service.resolve_relation_id_from_created_lead(
        create_response=body,
        create_payload=payload,
        member_id=auth_login_data["memberId"],
        user_id=auth_login_data["userId"],
        token=auth_login_data["token"],
    )
    allure.attach(
        json.dumps(
            {"request": payload, "response": body, "relation_id": relation_id},
            ensure_ascii=False,
            indent=2,
        ),
        name="create_germany_lead_api_detail",
        attachment_type=allure.attachment_type.JSON,
    )
    assert body.get("code") == 1000, f"创建德国线索失败: {body}"
