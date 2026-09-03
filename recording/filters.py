from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

STATIC_EXT = (
    ".js",
    ".css",
    ".map",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp4",
    ".webm",
    ".webp",
)

NOISE_PATH_KEYWORDS = (
    "sentry",
    "hotjar",
    "google-analytics",
    "googletagmanager",
    "umeng",
    "sensors",
    "tracking",
    "collect",
    "beacon",
    "sockjs",
    "websocket",
    "/static/",
    "/assets/",
    "/favicon",
)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

BUSINESS_PATH_HINTS = (
    "/api/crm/",
    "/api/member/",
    "/api/order/",
    "/api/product/",
    "/api/logistics/",
    "/api/platform/",
)


@dataclass(frozen=True)
class ScoredApiCall:
    method: str
    url: str
    path: str
    status: int | None
    score: int
    count: int
    sample: dict[str, Any]


def _normalize_path(path: str) -> str:
    parts = []
    for segment in path.split("/"):
        if not segment:
            parts.append(segment)
            continue
        if segment.isdigit():
            parts.append("{id}")
        elif re.fullmatch(r"[0-9a-fA-F-]{8,}", segment):
            parts.append("{id}")
        else:
            parts.append(segment)
    normalized = "/".join(parts)
    return normalized or "/"


def is_static_or_noise(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if any(path.endswith(ext) for ext in STATIC_EXT):
        return True
    lowered = url.lower()
    return any(keyword in lowered for keyword in NOISE_PATH_KEYWORDS)


def is_allowed_host(url: str, allowed_hosts: set[str]) -> bool:
    if not allowed_hosts:
        return True
    host = urlparse(url).netloc.lower()
    return any(host == item or host.endswith(f".{item}") for item in allowed_hosts)


def score_api_call(method: str, url: str, status: int | None) -> int:
    method_u = method.upper()
    path = urlparse(url).path
    score = 0
    if "/api/" in path:
        score += 20
    if any(hint in path for hint in BUSINESS_PATH_HINTS):
        score += 30
    if method_u in WRITE_METHODS:
        score += 40
    elif method_u == "GET":
        score += 5
    if status is not None and 200 <= status < 300:
        score += 10
    if status is not None and status >= 400:
        score -= 5
    # Prefer mutating CRM endpoints even more
    if method_u in WRITE_METHODS and "/api/crm/" in path:
        score += 15
    return score


def select_main_apis(
    calls: list[dict[str, Any]],
    *,
    allowed_hosts: set[str],
    min_score: int = 30,
    max_items: int = 30,
) -> list[ScoredApiCall]:
    """Deduplicate by method+normalized path and keep high-value business APIs."""
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for call in calls:
        url = str(call.get("url") or "")
        method = str(call.get("method") or "GET").upper()
        if not url or is_static_or_noise(url):
            continue
        if not is_allowed_host(url, allowed_hosts):
            continue
        path = urlparse(url).path
        if "/api/" not in path and not any(hint in path for hint in BUSINESS_PATH_HINTS):
            continue
        key = (method, _normalize_path(path))
        buckets[key].append(call)

    scored: list[ScoredApiCall] = []
    for (method, norm_path), items in buckets.items():
        sample = items[-1]
        status = sample.get("status")
        try:
            status_i = int(status) if status is not None else None
        except (TypeError, ValueError):
            status_i = None
        url = str(sample.get("url") or "")
        points = score_api_call(method, url, status_i)
        if points < min_score:
            continue
        scored.append(
            ScoredApiCall(
                method=method,
                url=url,
                path=norm_path,
                status=status_i,
                score=points,
                count=len(items),
                sample=sample,
            )
        )

    scored.sort(key=lambda item: (-item.score, -item.count, item.path))
    return scored[:max_items]
