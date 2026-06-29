from __future__ import annotations

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config import settings


def wait_for_mall_home_ready(
    page: Page,
    *,
    home_url: str,
    url_must_contain: str,
    url_must_not_contain: str = "",
    required_texts: tuple[str, ...] = (),
    timeout_ms: int | None = None,
) -> None:
    timeout = timeout_ms or settings.MALL_UI_NAV_TIMEOUT_MS
    errors: list[str] = []

    try:
        page.wait_for_function(
            """([mustContain, mustNotContain]) => {
              const href = location.href || '';
              if (mustNotContain && href.includes(mustNotContain)) return false;
              return href.includes(mustContain);
            }""",
            arg=[url_must_contain, url_must_not_contain],
            timeout=timeout,
        )
    except PlaywrightTimeoutError as exc:
        errors.append(f"url wait: {exc}")

    if required_texts:
        joined = ",".join(required_texts)
        try:
            page.wait_for_function(
                """(texts) => {
                  const body = document.body ? document.body.innerText : '';
                  return texts.some(text => body.includes(text));
                }""",
                arg=list(required_texts),
                timeout=timeout,
            )
        except PlaywrightTimeoutError as exc:
            errors.append(f"text wait: {exc}")

    if not errors:
        return

    if url_must_not_contain and url_must_not_contain in page.url:
        page.goto(home_url, wait_until=settings.MALL_UI_GOTO_WAIT_UNTIL, timeout=timeout)
        page.wait_for_function(
            """([mustContain, texts]) => {
              const href = location.href || '';
              if (!href.includes(mustContain)) return false;
              const body = document.body ? document.body.innerText : '';
              return !texts.length || texts.some(text => body.includes(text));
            }""",
            arg=[url_must_contain, list(required_texts)],
            timeout=timeout,
        )
        return

    raise AssertionError(
        f"商城首页未就绪（url={page.url}，期望包含 {url_must_contain}）: {' | '.join(errors)}"
    )
