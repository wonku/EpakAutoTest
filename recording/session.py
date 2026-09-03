from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Browser, BrowserContext, Page, Request, Response, sync_playwright

from config.settings import (
    APP_HOME_URL,
    BASE_URL,
    BROWSER_EXECUTABLE_PATH,
    HEADLESS,
    LOGIN_PATH,
    PLATFORM_BASE_URL,
    RECORDING_ALLOWED_HOSTS,
    RECORDING_DIR,
    RECORDING_MAX_MAIN_APIS,
    RECORDING_MIN_SCORE,
    SLOW_MO,
)
from recording.draft_generator import generate_api_draft, generate_summary, generate_ui_draft
from recording.filters import select_main_apis

# 页面内队列名：点击时只 push，不走同步 binding，避免卡住 window.open 新页签
ACTION_QUEUE = "__pyautotestActionQueue"

INIT_SCRIPT = f"""
(() => {{
  if (window.__pyautotestRecorderInstalled) return;
  window.__pyautotestRecorderInstalled = true;
  window.__pyautotestRecordingEnabled = false;
  window.{ACTION_QUEUE} = window.{ACTION_QUEUE} || [];

  const cssEscape = (value) => {{
    if (window.CSS && CSS.escape) return CSS.escape(value);
    return String(value).replace(/[^a-zA-Z0-9_-]/g, "\\\\$&");
  }};

  const visibleText = (el) => {{
    const text = (el.innerText || el.textContent || "").trim().replace(/\\s+/g, " ");
    return text.slice(0, 60);
  }};

  const buildSelector = (el) => {{
    if (!el || el.nodeType !== 1) return "";
    if (el.id) return "#" + cssEscape(el.id);
    const testId = el.getAttribute("data-testid") || el.getAttribute("data-test");
    if (testId) return `[data-testid="${{testId}}"]`;
    const nameAttr = el.getAttribute("name");
    if (nameAttr) return `${{el.tagName.toLowerCase()}}[name="${{nameAttr}}"]`;
    const placeholder = el.getAttribute("placeholder");
    if (placeholder) return `${{el.tagName.toLowerCase()}}[placeholder="${{placeholder}}"]`;
    if (el.classList && el.classList.length) {{
      const cls = Array.from(el.classList).slice(0, 2).map(cssEscape).join(".");
      if (cls) return `${{el.tagName.toLowerCase()}}.${{cls}}`;
    }}
    return el.tagName.toLowerCase();
  }};

  const emit = (payload) => {{
    if (!window.__pyautotestRecordingEnabled) return;
    try {{
      window.{ACTION_QUEUE}.push(payload);
    }} catch (err) {{
      // ignore
    }}
  }};

  document.addEventListener("click", (event) => {{
    const el = event.target && event.target.closest
      ? event.target.closest("a,button,[role='button'],input,textarea,select,.el-button,.ant-btn")
      : event.target;
    if (!el) return;
    emit({{
      type: "click",
      ts: Date.now(),
      selector: buildSelector(el),
      tag: (el.tagName || "").toLowerCase(),
      role: el.getAttribute("role") || (el.tagName === "BUTTON" ? "button" : ""),
      name: visibleText(el) || el.getAttribute("aria-label") || "",
      text: visibleText(el),
      placeholder: el.getAttribute("placeholder") || "",
      href: el.getAttribute("href") || "",
      url: location.href,
    }});
  }}, true);

  const emitFill = (el) => {{
    if (!el) return;
    const tag = (el.tagName || "").toLowerCase();
    if (!["input", "textarea", "select"].includes(tag)) return;
    const inputType = (el.getAttribute("type") || "").toLowerCase();
    let value = el.value;
    if (inputType === "password") value = "***";
    emit({{
      type: "fill",
      ts: Date.now(),
      selector: buildSelector(el),
      tag,
      role: el.getAttribute("role") || "",
      name: el.getAttribute("name") || "",
      placeholder: el.getAttribute("placeholder") || "",
      value,
      url: location.href,
    }});
  }};

  document.addEventListener("change", (event) => emitFill(event.target), true);
  let inputTimer = null;
  document.addEventListener("input", (event) => {{
    const el = event.target;
    if (inputTimer) clearTimeout(inputTimer);
    inputTimer = setTimeout(() => emitFill(el), 300);
  }}, true);
}})();
"""


SENSITIVE_HEADER_KEYS = {
    "authorization",
    "token",
    "cookie",
    "set-cookie",
    "x-token",
    "x-auth-token",
}
SENSITIVE_BODY_KEYS = {
    "password",
    "passwd",
    "pwd",
    "token",
    "authorization",
    "accessToken",
    "refreshToken",
}


def _redact_headers(headers: dict[str, str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in (headers or {}).items():
        if key.lower() in SENSITIVE_HEADER_KEYS:
            result[key] = "***"
        else:
            result[key] = value
    return result


def _redact_obj(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key).lower() in {k.lower() for k in SENSITIVE_BODY_KEYS}:
                out[key] = "***"
            else:
                out[key] = _redact_obj(item)
        return out
    if isinstance(value, list):
        return [_redact_obj(item) for item in value]
    return value


def _parse_body(text: str | None) -> Any:
    if text is None:
        return None
    stripped = text.strip()
    if not stripped:
        return None
    if len(stripped) > 200_000:
        return {"_truncated": True, "preview": stripped[:2000]}
    try:
        return _redact_obj(json.loads(stripped))
    except json.JSONDecodeError:
        return stripped[:5000]


def _allowed_hosts() -> set[str]:
    hosts = set(RECORDING_ALLOWED_HOSTS)
    for url in (PLATFORM_BASE_URL, BASE_URL, APP_HOME_URL):
        host = urlparse(url).netloc.lower()
        if host:
            hosts.add(host)
    return hosts


class RegressionSessionRecorder:
    def __init__(
        self,
        *,
        title: str = "crm_session",
        start_url: str | None = None,
        headless: bool | None = None,
    ):
        self.title = title
        self.start_url = start_url or f"{BASE_URL.rstrip('/')}{LOGIN_PATH}"
        self.headless = HEADLESS if headless is None else headless
        self.session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.session_dir = Path(RECORDING_DIR) / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._recording = False
        self._actions: list[dict[str, Any]] = []
        self._calls: list[dict[str, Any]] = []
        self._pending_requests: dict[str, dict[str, Any]] = {}
        self._attached_pages: set[int] = set()

        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def recording(self) -> bool:
        return self._recording

    def _request_key(self, request: Request) -> str:
        return f"{id(request)}"

    def _on_request(self, request: Request) -> None:
        if not self._recording:
            return
        if request.resource_type in {"image", "media", "font", "stylesheet"}:
            return
        entry = {
            "method": request.method,
            "url": request.url,
            "resource_type": request.resource_type,
            "request_headers": _redact_headers(request.headers),
            "request_body": None,
            "started_at": time.time(),
        }
        try:
            post = request.post_data
            entry["request_body"] = _parse_body(post)
        except Exception:
            entry["request_body"] = None
        with self._lock:
            self._pending_requests[self._request_key(request)] = entry

    def _on_response(self, response: Response) -> None:
        if not self._recording:
            return
        request = response.request
        if request.resource_type in {"image", "media", "font", "stylesheet"}:
            return
        key = self._request_key(request)
        with self._lock:
            entry = self._pending_requests.pop(key, None)
        if entry is None:
            entry = {
                "method": request.method,
                "url": request.url,
                "resource_type": request.resource_type,
                "request_headers": _redact_headers(request.headers),
                "request_body": None,
                "started_at": time.time(),
            }
            try:
                entry["request_body"] = _parse_body(request.post_data)
            except Exception:
                entry["request_body"] = None
        entry.update(
            {
                "status": response.status,
                "response_headers": _redact_headers(response.headers),
                "finished_at": time.time(),
            }
        )
        # 响应体放到 pump 阶段轻量采集，避免在事件回调里 response.text() 拖垮页面
        entry["response_body"] = None
        content_type = (response.headers.get("content-type") or "").lower()
        entry["_capture_body"] = ("json" in content_type) or ("/api/" in request.url)
        with self._lock:
            self._calls.append(entry)

    def _on_navigated(self, frame) -> None:
        if not self._recording:
            return
        if frame.parent_frame is not None:
            return
        url = frame.url
        if not url or url == "about:blank":
            return
        with self._lock:
            self._actions.append(
                {
                    "type": "navigate",
                    "ts": int(time.time() * 1000),
                    "url": url,
                }
            )

    def _set_recording_flag(self, enabled: bool) -> None:
        if not self._context:
            return
        js = f"window.__pyautotestRecordingEnabled = {'true' if enabled else 'false'};"
        for page in list(self._context.pages):
            try:
                page.evaluate(js)
            except Exception:
                pass

    def _drain_action_queues(self) -> None:
        if not self._context:
            return
        drain_js = f"""
() => {{
  const q = window.{ACTION_QUEUE} || [];
  window.{ACTION_QUEUE} = [];
  return q;
}}
"""
        for page in list(self._context.pages):
            try:
                batch = page.evaluate(drain_js)
            except Exception:
                continue
            if not batch:
                continue
            with self._lock:
                for item in batch:
                    if isinstance(item, dict):
                        self._actions.append(item)

    def _attach_page(self, page: Page) -> None:
        page_id = id(page)
        if page_id in self._attached_pages:
            return
        self._attached_pages.add(page_id)
        # 仅用 init script + 页面内队列，避免 sync expose_binding 卡住新页签
        page.add_init_script(INIT_SCRIPT)
        page.on("framenavigated", self._on_navigated)
        page.on("request", self._on_request)
        page.on("response", self._on_response)

        def _on_close(_page: Page) -> None:
            self._attached_pages.discard(id(_page))

        page.on("close", _on_close)

        # 新页签：切到前台，并等待离开 about:blank（首个空白页留给后续 goto，不在这里死等）
        try:
            page.bring_to_front()
        except Exception:
            pass

        is_popup = bool(self._context and len(self._context.pages) > 1)
        if is_popup:
            try:
                if page.url in {"", "about:blank"}:
                    page.wait_for_url(
                        lambda url: bool(url) and url != "about:blank",
                        timeout=15000,
                    )
            except Exception:
                pass
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass

        try:
            page.evaluate(INIT_SCRIPT)
            if self._recording:
                page.evaluate("window.__pyautotestRecordingEnabled = true")
        except Exception:
            pass

        self._page = page

    def open_browser(self) -> Page:
        self._playwright = sync_playwright().start()
        launch_kwargs: dict[str, Any] = {
            "headless": self.headless,
            # 录制会话不需要放慢操作，slow_mo 反而容易干扰人工点击开新页
            "slow_mo": 0 if not self.headless else SLOW_MO,
            "args": [
                "--disable-popup-blocking",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        }
        if BROWSER_EXECUTABLE_PATH:
            launch_kwargs["executable_path"] = BROWSER_EXECUTABLE_PATH
        self._browser = self._playwright.chromium.launch(**launch_kwargs)
        har_path = self.session_dir / "network.har"
        self._context = self._browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_har_path=str(har_path),
            record_har_content="embed",
            accept_downloads=True,
        )
        self._context.on("page", self._attach_page)
        self._page = self._context.new_page()
        self._attach_page(self._page)
        self._page.goto(self.start_url, wait_until="domcontentloaded")
        try:
            self._page.evaluate(INIT_SCRIPT)
        except Exception:
            pass
        return self._page

    def pump(self, timeout_ms: int = 200) -> None:
        """推进 Playwright 事件循环，并抽取页面内 UI 操作队列。"""
        self._drain_action_queues()
        page = self._page
        if page is None and self._context and self._context.pages:
            page = self._context.pages[-1]
            self._page = page
        if page is None:
            time.sleep(timeout_ms / 1000)
            return
        try:
            page.wait_for_timeout(timeout_ms)
        except Exception:
            time.sleep(timeout_ms / 1000)
        self._drain_action_queues()

    def wait_until_enter(self, prompt: str) -> None:
        """边等 Enter 边 pump，保证新页签导航与 Network 事件不被 stdin 阻塞。"""
        done = threading.Event()

        def _wait() -> None:
            try:
                input(prompt)
            except EOFError:
                print("\n[录制] 收到 EOF，继续执行下一步")
            finally:
                done.set()

        thread = threading.Thread(target=_wait, daemon=True)
        thread.start()
        while not done.is_set():
            self.pump(200)
        thread.join(timeout=1)
        self.pump(100)

    def start_recording(self) -> None:
        if self._recording:
            return
        self._recording = True
        self._set_recording_flag(True)
        with self._lock:
            self._actions.append(
                {
                    "type": "session_start",
                    "ts": int(time.time() * 1000),
                    "url": self._page.url if self._page else self.start_url,
                }
            )

    def stop_recording(self) -> None:
        if not self._recording:
            return
        self._drain_action_queues()
        self._recording = False
        self._set_recording_flag(False)
        with self._lock:
            self._actions.append(
                {
                    "type": "session_stop",
                    "ts": int(time.time() * 1000),
                    "url": self._page.url if self._page else "",
                }
            )

    def save_and_generate(self) -> dict[str, Any]:
        with self._lock:
            actions = list(self._actions)
            calls = list(self._calls)
            for item in calls:
                item.pop("_capture_body", None)

        actions_path = self.session_dir / "ui_actions.json"
        calls_path = self.session_dir / "network_calls.json"
        actions_path.write_text(
            json.dumps(actions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        calls_path.write_text(
            json.dumps(calls, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        main_apis = select_main_apis(
            calls,
            allowed_hosts=_allowed_hosts(),
            min_score=RECORDING_MIN_SCORE,
            max_items=RECORDING_MAX_MAIN_APIS,
        )
        main_path = self.session_dir / "main_apis.json"
        main_path.write_text(
            json.dumps(
                [
                    {
                        "method": item.method,
                        "path": item.path,
                        "url": item.url,
                        "status": item.status,
                        "score": item.score,
                        "count": item.count,
                        "sample": item.sample,
                    }
                    for item in main_apis
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        ui_draft = generate_ui_draft(
            session_dir=self.session_dir,
            actions=actions,
            title=self.title,
        )
        api_draft = generate_api_draft(
            session_dir=self.session_dir,
            main_apis=main_apis,
            title=self.title,
        )
        summary = generate_summary(
            session_dir=self.session_dir,
            title=self.title,
            actions=actions,
            all_calls=calls,
            main_apis=main_apis,
            ui_draft=ui_draft,
            api_draft=api_draft,
        )
        meta = {
            "title": self.title,
            "session_id": self.session_id,
            "session_dir": str(self.session_dir),
            "start_url": self.start_url,
            "action_count": len(actions),
            "call_count": len(calls),
            "main_api_count": len(main_apis),
            "ui_draft": str(ui_draft),
            "api_draft": str(api_draft),
            "summary": str(summary),
        }
        (self.session_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return meta

    def close(self) -> None:
        try:
            if self._context:
                self._context.close()
        finally:
            self._context = None
            try:
                if self._browser:
                    self._browser.close()
            finally:
                self._browser = None
                if self._playwright:
                    self._playwright.stop()
                    self._playwright = None
