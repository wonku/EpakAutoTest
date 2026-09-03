from __future__ import annotations

from api.client import ApiClient
from config.settings import (
    API_TIMEOUT_SECONDS,
    AUTH_API_URL,
    AUTH_ENVIRONMENT,
    AUTH_SITE,
    AUTH_SOURCE,
    BASE_URL,
    CRM_INQUIRY_SUPPLIER_AUTH_API_URL,
    CRM_INQUIRY_SUPPLIER_AUTH_ORIGIN,
    EPAK_LOGIN_PASSWORD_ENCRYPTED,
    EPAK_LOGIN_PHONE,
    EPAK_PLATFORM_ACCEPT_LANGUAGE,
    EPAK_PLATFORM_AUTH_API_URL,
    EPAK_PLATFORM_AUTH_ORIGIN,
    EPAK_PLATFORM_AUTH_REFERER,
    EPAK_PLATFORM_LANG_COOKIE,
)

LOGIN_EXPIRED_CODE = 1101
LOGIN_SUCCESS_CODE = 1000

_CN_AUTH_ORIGIN = (
    BASE_URL.rstrip("/") if BASE_URL.startswith("http") else "https://test-auth.ysbpack.com"
)


class LoginExpiredError(AssertionError):
    """业务接口返回登录过期（code=1101）。"""


def is_login_expired(body_or_exc: object) -> bool:
    if isinstance(body_or_exc, LoginExpiredError):
        return True
    if isinstance(body_or_exc, dict):
        return body_or_exc.get("code") == LOGIN_EXPIRED_CODE
    text = str(body_or_exc)
    return f"'code': {LOGIN_EXPIRED_CODE}" in text or f'"code": {LOGIN_EXPIRED_CODE}' in text


class AuthService:
    def __init__(self, client: ApiClient | None = None):
        self.client = client or ApiClient(timeout=API_TIMEOUT_SECONDS)

    @staticmethod
    def normalize_login_endpoint(endpoint: str | None = None) -> str:
        text = str(endpoint or "cn").strip().lower()
        if text in {"en", "epak", "epak_cn", "english"}:
            return "en"
        if text in {"supplier", "cn_supplier", "supplier_cn"}:
            return "supplier"
        return "cn"

    @classmethod
    def resolve_login_endpoint(cls, endpoint: str | None = None) -> dict[str, str]:
        kind = cls.normalize_login_endpoint(endpoint)
        if kind == "en":
            return {
                "endpoint": "en",
                "api_url": EPAK_PLATFORM_AUTH_API_URL,
                "origin": EPAK_PLATFORM_AUTH_ORIGIN,
                "referer": EPAK_PLATFORM_AUTH_REFERER,
                "accept_language": EPAK_PLATFORM_ACCEPT_LANGUAGE,
                "cookie": EPAK_PLATFORM_LANG_COOKIE,
            }
        if kind == "supplier":
            origin = CRM_INQUIRY_SUPPLIER_AUTH_ORIGIN.rstrip("/")
            return {
                "endpoint": "supplier",
                "api_url": CRM_INQUIRY_SUPPLIER_AUTH_API_URL,
                "origin": origin,
                "referer": f"{origin}/user/login",
                "accept_language": "",
                "cookie": "",
            }
        return {
            "endpoint": "cn",
            "api_url": AUTH_API_URL,
            "origin": _CN_AUTH_ORIGIN,
            "referer": f"{_CN_AUTH_ORIGIN}/user/login",
            "accept_language": "",
            "cookie": "",
        }

    @classmethod
    def build_login_headers(cls, endpoint: str | None = None) -> dict[str, str]:
        spec = cls.resolve_login_endpoint(endpoint)
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "environment": AUTH_ENVIRONMENT,
            "site": AUTH_SITE,
            "source": AUTH_SOURCE,
            "Origin": spec["origin"],
            "Referer": spec["referer"],
        }
        if spec.get("accept_language"):
            headers["Accept-Language"] = spec["accept_language"]
        if spec.get("cookie"):
            headers["Cookie"] = spec["cookie"]
        return headers

    def login_with_encrypted_password(
        self,
        account: str,
        password_encrypted: str,
        *,
        endpoint: str | None = None,
        extra_body: dict | None = None,
    ) -> dict:
        spec = self.resolve_login_endpoint(endpoint)
        json_body = {"account": account, "password": password_encrypted}
        if extra_body:
            json_body.update(extra_body)
        resp = self.client.request(
            "POST",
            spec["api_url"],
            json_body=json_body,
            headers=self.build_login_headers(spec["endpoint"]),
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != LOGIN_SUCCESS_CODE:
            raise AssertionError(f"登录失败: {body}")
        data = body.get("data") or {}
        if not data.get("token"):
            raise AssertionError(f"登录接口未返回有效 token: {body}")
        return data

    def login_epak_platform(
        self,
        account: str | None = None,
        password_encrypted: str | None = None,
    ) -> dict:
        return self.login_with_encrypted_password(
            account or EPAK_LOGIN_PHONE,
            password_encrypted or EPAK_LOGIN_PASSWORD_ENCRYPTED,
            endpoint="en",
        )
