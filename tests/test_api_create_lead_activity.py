import json

import allure

from config.settings import ACTIVITY_RECORD_TYPE_CODE, ACTIVITY_TYPE_CODE


@allure.feature("CRM 接口造数")
@allure.story("销售线索活动记录")
@allure.title("创建线索后新增活动记录")
def test_create_lead_activity_record_by_api(auth_login_data, crm_lead_service):
    lead_payload = crm_lead_service.build_random_lead_payload(
        member_id=auth_login_data["memberId"],
        user_id=auth_login_data["userId"],
        token=auth_login_data["token"],
    )
    lead_resp = crm_lead_service.create_lead(
        member_id=auth_login_data["memberId"],
        user_id=auth_login_data["userId"],
        token=auth_login_data["token"],
        payload=lead_payload,
    )
    relation_id = crm_lead_service.resolve_relation_id_from_created_lead(
        create_response=lead_resp,
        create_payload=lead_payload,
        member_id=auth_login_data["memberId"],
        user_id=auth_login_data["userId"],
        token=auth_login_data["token"],
    )
    activity_payload = crm_lead_service.build_activity_payload(
        relation_id=relation_id,
        activity_type_code=ACTIVITY_TYPE_CODE,
        activity_record_type_code=ACTIVITY_RECORD_TYPE_CODE,
    )
    activity_resp = crm_lead_service.create_activity_record(
        member_id=auth_login_data["memberId"],
        user_id=auth_login_data["userId"],
        token=auth_login_data["token"],
        payload=activity_payload,
    )
    allure.attach(
        json.dumps(
            {
                "lead_request": lead_payload,
                "lead_response": lead_resp,
                "relation_id": relation_id,
                "activity_type_code": ACTIVITY_TYPE_CODE,
                "activity_record_type_code": ACTIVITY_RECORD_TYPE_CODE,
                "activity_request": activity_payload,
                "activity_response": activity_resp,
            },
            ensure_ascii=False,
            indent=2,
        ),
        name="create_lead_activity_api_detail",
        attachment_type=allure.attachment_type.JSON,
    )
    assert activity_resp.get("code") == 1000, f"创建活动记录失败: {activity_resp}"
