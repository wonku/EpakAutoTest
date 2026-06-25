from __future__ import annotations

import json

import allure
import pytest

from api.client import ApiClient
from config.settings import (
    ACTIVITY_RECORD_TYPE_CODE,
    ACTIVITY_TYPE_CODE,
    API_TIMEOUT_SECONDS,
    AUTH_API_URL,
    AUTH_ENVIRONMENT,
    AUTH_SITE,
    AUTH_SOURCE,
    COUNTRY_LIST_API_URL,
    CRM_ACTIVITY_SAVE_API_URL,
    CRM_LEAD_ASSIGN_API_URL,
    CRM_LEAD_CLAIM_API_URL,
    CRM_LEAD_MOVE_PUBLIC_SEA_API_URL,
    CRM_LEAD_PAGE_API_URL,
    CRM_LEAD_SAVE_API_URL,
    LOGIN_PASSWORD_ENCRYPTED,
    LOGIN_PHONE,
    MEMBER_USER_EFFECTIVE_LIST_API_URL,
    MOVE_PUBLIC_SEA_REASON_CODE,
    MOVE_PUBLIC_SEA_REMARK,
    PLATFORM_BASE_URL,
)

pytestmark = pytest.mark.api_negative


def _parse_json(resp) -> dict:
    try:
        return resp.json()
    except Exception:
        return {}


def _attach_api_detail(name: str, request: dict, response: dict, status_code: int) -> None:
    allure.attach(
        json.dumps(
            {"request": request, "response": response, "status_code": status_code},
            ensure_ascii=False,
            indent=2,
        ),
        name=name,
        attachment_type=allure.attachment_type.JSON,
    )


def _assert_rejected(body: dict, status_code: int, *, context: str) -> None:
    if status_code >= 400:
        return
    assert body.get("code") != 1000, f"{context} 预期失败但返回 code=1000: {body}"


def _auth_headers() -> dict[str, str]:
    return {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "environment": AUTH_ENVIRONMENT,
        "site": AUTH_SITE,
        "source": AUTH_SOURCE,
        "Origin": "https://test-auth.ysbpack.com",
        "Referer": "https://test-auth.ysbpack.com/user/login",
    }


def _crm_headers(*, member_id: int, user_id: int, token: str) -> dict[str, str]:
    return {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "environment": AUTH_ENVIRONMENT,
        "site": AUTH_SITE,
        "source": AUTH_SOURCE,
        "Origin": PLATFORM_BASE_URL,
        "Referer": f"{PLATFORM_BASE_URL}/memberCenter/crm2Ability/salesClue",
        "memberId": str(member_id),
        "userId": str(user_id),
        "token": token,
        "Authorization": token,
    }


@pytest.fixture(scope="module")
def api_raw_client() -> ApiClient:
    return ApiClient(timeout=API_TIMEOUT_SECONDS)


@allure.feature("CRM 接口异常")
@allure.story("登录")
@allure.title("错误密码登录应失败")
def test_login_wrong_password(api_raw_client):
    resp = api_raw_client.request(
        "POST",
        AUTH_API_URL,
        json_body={"account": LOGIN_PHONE, "password": "invalid-password-base64=="},
        headers=_auth_headers(),
    )
    body = _parse_json(resp)
    _attach_api_detail("login_wrong_password", {"account": LOGIN_PHONE}, body, resp.status_code)
    _assert_rejected(body, resp.status_code, context="错误密码登录")
    assert not (body.get("data") or {}).get("token"), f"错误密码不应返回 token: {body}"


@allure.feature("CRM 接口异常")
@allure.story("登录")
@allure.title("空账号登录应失败")
def test_login_empty_account(api_raw_client):
    resp = api_raw_client.request(
        "POST",
        AUTH_API_URL,
        json_body={"account": "", "password": LOGIN_PASSWORD_ENCRYPTED},
        headers=_auth_headers(),
    )
    body = _parse_json(resp)
    _attach_api_detail("login_empty_account", {"account": ""}, body, resp.status_code)
    _assert_rejected(body, resp.status_code, context="空账号登录")
    assert not (body.get("data") or {}).get("token"), f"空账号不应返回 token: {body}"


@allure.feature("CRM 接口异常")
@allure.story("销售线索")
@allure.title("无 token 创建线索应失败")
def test_create_lead_without_token(api_raw_client):
    payload = {
        "name": "negative-no-token",
        "phone": "13900000001",
        "email": "negative@qq.com",
        "leadSourceCode": 4,
        "countryCode": "86",
        "country": "中国",
    }
    resp = api_raw_client.request(
        "POST",
        CRM_LEAD_SAVE_API_URL,
        json_body=payload,
        headers={
            "Accept": "*/*",
            "Content-Type": "application/json",
            "environment": AUTH_ENVIRONMENT,
            "site": AUTH_SITE,
            "source": AUTH_SOURCE,
        },
    )
    body = _parse_json(resp)
    _attach_api_detail("create_lead_without_token", payload, body, resp.status_code)
    _assert_rejected(body, resp.status_code, context="无 token 创建线索")


@allure.feature("CRM 接口异常")
@allure.story("销售线索")
@allure.title("缺少 name 创建线索应失败")
def test_create_lead_missing_name(api_raw_client, auth_login_data):
    payload = {
        "phone": "13900000002",
        "email": "missing-name@qq.com",
        "leadSourceCode": 4,
        "countryCode": "86",
        "country": "中国",
        "followUserId": auth_login_data.get("userId"),
    }
    resp = api_raw_client.request(
        "POST",
        CRM_LEAD_SAVE_API_URL,
        json_body=payload,
        headers=_crm_headers(
            member_id=auth_login_data["memberId"],
            user_id=auth_login_data["userId"],
            token=auth_login_data["token"],
        ),
    )
    body = _parse_json(resp)
    _attach_api_detail("create_lead_missing_name", payload, body, resp.status_code)
    _assert_rejected(body, resp.status_code, context="缺少 name 创建线索")


@allure.feature("CRM 接口异常")
@allure.story("销售线索")
@allure.title("非法分页参数查询线索应被拒绝或返回空结果")
def test_query_lead_invalid_page(api_raw_client, auth_login_data):
    payload = {"pageNum": 0, "pageSize": 20}
    resp = api_raw_client.request(
        "POST",
        CRM_LEAD_PAGE_API_URL,
        json_body=payload,
        headers=_crm_headers(
            member_id=auth_login_data["memberId"],
            user_id=auth_login_data["userId"],
            token=auth_login_data["token"],
        ),
    )
    body = _parse_json(resp)
    _attach_api_detail("query_lead_invalid_page", payload, body, resp.status_code)
    assert resp.status_code < 500, f"非法分页导致服务异常: {body}"
    if body.get("code") == 1000:
        rows = body.get("data", {}).get("data", [])
        assert isinstance(rows, list), f"成功响应 data 应为列表: {body}"
    else:
        _assert_rejected(body, resp.status_code, context="非法分页查询线索")


@allure.feature("CRM 接口异常")
@allure.story("销售线索认领")
@allure.title("空 leadIds 认领应失败")
def test_claim_lead_empty_ids(api_raw_client, auth_login_data):
    payload = {"leadIds": []}
    resp = api_raw_client.request(
        "POST",
        CRM_LEAD_CLAIM_API_URL,
        json_body=payload,
        headers=_crm_headers(
            member_id=auth_login_data["memberId"],
            user_id=auth_login_data["userId"],
            token=auth_login_data["token"],
        ),
    )
    body = _parse_json(resp)
    _attach_api_detail("claim_lead_empty_ids", payload, body, resp.status_code)
    _assert_rejected(body, resp.status_code, context="空 leadIds 认领")


@allure.feature("CRM 接口异常")
@allure.story("销售线索分配")
@allure.title("无效跟进人分配线索应失败")
def test_assign_lead_invalid_user(api_raw_client, auth_login_data):
    payload = {
        "leadIds": [1],
        "newFollowUserId": 999999999,
        "newFollowUserName": "invalid_follow_user_negative_test",
    }
    resp = api_raw_client.request(
        "POST",
        CRM_LEAD_ASSIGN_API_URL,
        json_body=payload,
        headers=_crm_headers(
            member_id=auth_login_data["memberId"],
            user_id=auth_login_data["userId"],
            token=auth_login_data["token"],
        ),
    )
    body = _parse_json(resp)
    _attach_api_detail("assign_lead_invalid_user", payload, body, resp.status_code)
    _assert_rejected(body, resp.status_code, context="无效跟进人分配线索")


@allure.feature("CRM 接口异常")
@allure.story("销售线索公海")
@allure.title("不存在 leadId 移入公海应失败")
def test_move_public_sea_invalid_id(api_raw_client, auth_login_data):
    payload = {
        "leadIds": [999999999],
        "publicSeaReasonCode": MOVE_PUBLIC_SEA_REASON_CODE,
        "remark": MOVE_PUBLIC_SEA_REMARK,
    }
    resp = api_raw_client.request(
        "POST",
        CRM_LEAD_MOVE_PUBLIC_SEA_API_URL,
        json_body=payload,
        headers=_crm_headers(
            member_id=auth_login_data["memberId"],
            user_id=auth_login_data["userId"],
            token=auth_login_data["token"],
        ),
    )
    body = _parse_json(resp)
    _attach_api_detail("move_public_sea_invalid_id", payload, body, resp.status_code)
    _assert_rejected(body, resp.status_code, context="不存在 leadId 移入公海")


@allure.feature("CRM 接口异常")
@allure.story("活动记录")
@allure.title("无效 relationId 创建活动记录应失败")
def test_activity_invalid_relation_id(api_raw_client, auth_login_data):
    payload = {
        "activityTypeCode": ACTIVITY_TYPE_CODE,
        "activityContent": "negative test",
        "activityRecordTypeCode": ACTIVITY_RECORD_TYPE_CODE,
        "relationId": -1,
    }
    resp = api_raw_client.request(
        "POST",
        CRM_ACTIVITY_SAVE_API_URL,
        json_body=payload,
        headers=_crm_headers(
            member_id=auth_login_data["memberId"],
            user_id=auth_login_data["userId"],
            token=auth_login_data["token"],
        ),
    )
    body = _parse_json(resp)
    _attach_api_detail("activity_invalid_relation_id", payload, body, resp.status_code)
    _assert_rejected(body, resp.status_code, context="无效 relationId 创建活动记录")


@allure.feature("CRM 接口异常")
@allure.story("公共数据")
@allure.title("无 token 查询有效用户列表应失败")
def test_effective_user_list_without_auth(api_raw_client):
    resp = api_raw_client.request(
        "GET",
        MEMBER_USER_EFFECTIVE_LIST_API_URL,
        headers={
            "Accept": "*/*",
            "environment": AUTH_ENVIRONMENT,
            "site": AUTH_SITE,
            "source": AUTH_SOURCE,
        },
    )
    body = _parse_json(resp)
    _attach_api_detail("effective_user_list_without_auth", {}, body, resp.status_code)
    _assert_rejected(body, resp.status_code, context="无 token 查询有效用户列表")


@allure.feature("CRM 接口异常")
@allure.story("公共数据")
@allure.title("国家列表接口无需 token（公开数据，记录现状）")
def test_country_list_is_public_without_auth(api_raw_client):
    resp = api_raw_client.request(
        "GET",
        COUNTRY_LIST_API_URL,
        params={"pageNum": 1, "pageSize": 10},
        headers={
            "Accept": "*/*",
            "environment": AUTH_ENVIRONMENT,
            "site": AUTH_SITE,
            "source": AUTH_SOURCE,
        },
    )
    body = _parse_json(resp)
    _attach_api_detail(
        "country_list_public_access",
        {"pageNum": 1, "pageSize": 10},
        body,
        resp.status_code,
    )
    assert resp.status_code == 200, f"国家列表请求异常: {body}"
    assert body.get("code") == 1000, f"国家列表为公开接口，当前应可匿名访问: {body}"
    assert body.get("data", {}).get("data"), "国家列表应返回数据"
