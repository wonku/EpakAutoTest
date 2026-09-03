from __future__ import annotations

import time
from typing import Any

import requests
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import SSLError, Timeout

from config.settings import (
    API_REQUEST_RETRIES,
    API_RETRY_BACKOFF_SECONDS,
    API_SSL_VERIFY,
)


class ApiClient:
    def __init__(
        self,
        base_url: str = "",
        default_headers: dict[str, str] | None = None,
        timeout: int = 30,
        *,
        verify: bool | None = None,
        retries: int | None = None,
        retry_backoff_seconds: float | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify = API_SSL_VERIFY if verify is None else verify
        self.retries = API_REQUEST_RETRIES if retries is None else retries
        self.retry_backoff_seconds = (
            API_RETRY_BACKOFF_SECONDS if retry_backoff_seconds is None else retry_backoff_seconds
        )
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
        files: Any = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> requests.Response:
        url = path_or_url
        if self.base_url and not path_or_url.startswith("http"):
            url = f"{self.base_url}/{path_or_url.lstrip('/')}"

        attempts = max(self.retries, 1)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return self.session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    json=json_body,
                    data=data,
                    files=files,
                    headers=headers,
                    timeout=timeout or self.timeout,
                    verify=self.verify,
                )
            except (SSLError, RequestsConnectionError, Timeout) as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                time.sleep(self.retry_backoff_seconds * attempt)

        assert last_error is not None
        raise last_error
