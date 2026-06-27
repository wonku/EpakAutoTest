from __future__ import annotations

from typing import Any

import requests


class ApiClient:
    def __init__(
        self,
        base_url: str = "",
        default_headers: dict[str, str] | None = None,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        if default_headers:
            self.session.headers.update(default_headers)

    def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> requests.Response:
        url = path_or_url
        if self.base_url and not path_or_url.startswith("http"):
            url = f"{self.base_url}/{path_or_url.lstrip('/')}"
        resp = self.session.request(
            method=method.upper(),
            url=url,
            params=params,
            json=json_body,
            data=data,
            headers=headers,
            timeout=timeout or self.timeout,
        )
        return resp
