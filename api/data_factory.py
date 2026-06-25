from __future__ import annotations

from typing import Any

from api.client import ApiClient


class DataFactory:
    """
    轻量数据工厂：
    - 后续把造数接口按业务封装为方法（如 create_lead/create_customer）
    - 当前先提供通用调用入口，保证可快速接入新接口
    """

    def __init__(self, client: ApiClient):
        self.client = client

    def call(
        self,
        *,
        method: str,
        path_or_url: str,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict:
        resp = self.client.request(
            method=method,
            path_or_url=path_or_url,
            json_body=json_body,
            params=params,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()
