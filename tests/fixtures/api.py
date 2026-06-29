from __future__ import annotations

import json
import base64

import pytest

from api.auth_context import AuthContext
from api.client import ApiClient
from api.services.auth_service import AuthService
from api.services.crm_lead_service import CrmLeadService
from config.settings import (
    API_TIMEOUT_SECONDS,
    LOGIN_PASSWORD_ENCRYPTED,
    LOGIN_PHONE,
)


def _build_linkseeks_auth(login_data: dict) -> dict:
    service_type_code = login_data.get("serviceTypeCode")
    member_id = login_data.get("memberId")
    upstream = "1" if service_type_code == 2 or (service_type_code == 3 and member_id == 6) else "0"
    return {
        "userId": login_data.get("userId"),
        "memberId": member_id,
        "token": login_data.get("token"),
        "name": login_data.get("name"),
        "logo": login_data.get("logo"),
        "level": login_data.get("level"),
        "phone": login_data.get("phone") or login_data.get("account"),
        "levelTag": login_data.get("levelTag"),
        "score": login_data.get("score") or 0,
        "creditPoint": login_data.get("creditPoint") or 0,
        "memberRoleType": login_data.get("memberRoleType"),
        "memberRoleId": login_data.get("memberRoleId"),
        "memberType": login_data.get("memberType"),
        "locales": login_data.get("locales"),
        "roles": login_data.get("roles") or [],
        "validateStatus": login_data.get("validateStatus"),
        "validateStatusDesc": login_data.get("validateStatusDesc"),
        "companyList": login_data.get("multiMemberBOS"),
        "supplierId": login_data.get("supplierId"),
        "company": login_data.get("company"),
        "serviceTypeCode": service_type_code,
        "buyerRegisterStatus": login_data.get("buyerRegisterStatus"),
        "dealerRegisterStatus": login_data.get("dealerRegisterStatus"),
        "temporarilyType": login_data.get("temporarilyType"),
        "upstream": upstream,
    }


@pytest.fixture(scope="session")
def auth_service() -> AuthService:
    return AuthService(ApiClient(timeout=API_TIMEOUT_SECONDS))


@pytest.fixture(scope="session")
def auth_login_data(auth_service) -> dict:
    return auth_service.login_with_encrypted_password(LOGIN_PHONE, LOGIN_PASSWORD_ENCRYPTED)


@pytest.fixture(scope="session")
def crm_auth(auth_login_data) -> AuthContext:
    return AuthContext.from_login_data(auth_login_data)


@pytest.fixture(scope="session")
def auth_token(auth_login_data) -> str:
    return auth_login_data["token"]


@pytest.fixture(scope="session")
def api_client(auth_token) -> ApiClient:
    return ApiClient(
        timeout=API_TIMEOUT_SECONDS,
        default_headers={"Authorization": auth_token, "token": auth_token},
    )


@pytest.fixture(scope="session")
def crm_lead_service(api_client) -> CrmLeadService:
    return CrmLeadService(api_client)


@pytest.fixture(scope="function")
def authenticated_page(page, auth_token, auth_login_data):
    token_literal = json.dumps(auth_token)
    login_data_literal = json.dumps(auth_login_data, ensure_ascii=False)
    linkseeks_auth_obj = _build_linkseeks_auth(auth_login_data)
    linkseeks_auth_str = json.dumps(linkseeks_auth_obj, ensure_ascii=False, separators=(",", ":"))
    linkseeks_auth_b64 = base64.b64encode(linkseeks_auth_str.encode("utf-8")).decode("utf-8")
    linkseeks_auth_literal = json.dumps(linkseeks_auth_b64)
    page.add_init_script(
        f"""
        () => {{
          const token = {token_literal};
          const loginData = {login_data_literal};
          const linkseeksAuth = {linkseeks_auth_literal};
          const keys = ["token", "access_token", "accessToken", "Authorization", "member_token"];
          keys.forEach((k) => window.localStorage.setItem(k, token));
          window.localStorage.setItem("isLogin", "true");
          window.localStorage.setItem("loginStatus", "1");
          window.localStorage.setItem("userInfo", JSON.stringify(loginData));
          window.localStorage.setItem("memberInfo", JSON.stringify(loginData));
          window.localStorage.setItem("loginUser", JSON.stringify(loginData));
          window.localStorage.setItem("account", loginData.account || "");
          window.localStorage.setItem("Linkseeks_AUTH", linkseeksAuth);
        }}
        """,
    )
    page.context.set_extra_http_headers({"Authorization": auth_token, "token": auth_token})
    page.context.add_cookies(
        [
            {"name": "token", "value": auth_token, "domain": ".ysbpack.com", "path": "/"},
            {"name": "Authorization", "value": auth_token, "domain": ".ysbpack.com", "path": "/"},
            {"name": "member_token", "value": auth_token, "domain": ".ysbpack.com", "path": "/"},
            {
                "name": "Linkseeks_AUTH",
                "value": linkseeks_auth_b64,
                "domain": ".ysbpack.com",
                "path": "/",
            },
        ]
    )
    yield page
