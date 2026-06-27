from __future__ import annotations

from api.client import ApiClient
from config.settings import (
    API_TIMEOUT_SECONDS,
    AUTH_API_URL,
    AUTH_ENVIRONMENT,
    AUTH_SITE,
    AUTH_SOURCE,
)


class AuthService:
    def __init__(self, client: ApiClient | None = None):
        self.client = client or ApiClient(timeout=API_TIMEOUT_SECONDS)

    def login_with_encrypted_password(self, account: str, password_encrypted: str) -> dict:
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "environment": AUTH_ENVIRONMENT,
            "site": AUTH_SITE,
            "source": AUTH_SOURCE,
            "Origin": "https://test-auth.ysbpack.com",
            "Referer": "https://test-auth.ysbpack.com/user/login",
        }
        resp = self.client.request(
            "POST",
            AUTH_API_URL,
            json_body={"account": account, "password": password_encrypted},
            headers=headers,
        )
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", {})
        if not data.get("token"):
            raise AssertionError(f"登录接口未返回有效 token: {body}")
        return data
