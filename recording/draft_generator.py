from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from recording.filters import ScoredApiCall


def _slugify(text: str, fallback: str = "session") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", text.strip())
    cleaned = cleaned.strip("_").lower()
    return cleaned[:48] or fallback


def _py_str(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _safe_selector_step(action: dict[str, Any], *, indent: str = "        ") -> list[str]:
    """Generate Playwright step lines. Default indent is inside `with allure.step`."""
    lines: list[str] = []
    action_type = action.get("type")
    selector = action.get("selector") or ""
    value = action.get("value")
    name = action.get("name") or action.get("text") or ""
    placeholder = action.get("placeholder") or ""
    role = action.get("role") or ""
    tag = (action.get("tag") or "").lower()

    comment = f"{indent}# {action_type}: {selector or name or placeholder or tag}"
    lines.append(comment)

    if action_type == "navigate":
        url = action.get("url") or ""
        lines.append(
            f"{indent}_goto_resilient(page, {_py_str(url)})"
        )
        return lines

    if action_type in {"fill", "change", "input"}:
        if selector:
            lines.append(
                f"{indent}page.locator({_py_str(selector)}).fill({_py_str(value or '')})"
            )
        elif placeholder:
            lines.append(
                f"{indent}page.get_by_placeholder({_py_str(placeholder)}).fill({_py_str(value or '')})"
            )
        else:
            lines.append(f"{indent}# TODO: 补充填写定位与值")
        return lines

    if action_type == "click":
        # Prefer CSS / text that matches CRM DOM; avoid treating <a> menu as button
        if name and re.search(r"(新增线索|新建线索)", name):
            lines.append(
                f"{indent}page.get_by_role(\"button\", name=re.compile(r\"新增线索|新建线索\")).click()"
            )
            return lines
        if selector and selector not in {"a", "button", "span"}:
            lines.append(f"{indent}page.locator({_py_str(selector)}).first.click()")
            return lines
        if tag == "a" and name:
            lines.append(
                f"{indent}page.get_by_role(\"link\", name={_py_str(name)}).click()"
            )
            return lines
        if role == "button" and name:
            lines.append(
                f"{indent}page.get_by_role(\"button\", name={_py_str(name)}).click()"
            )
            return lines
        if name and tag == "button":
            lines.append(
                f"{indent}page.get_by_role(\"button\", name={_py_str(name)}).click()"
            )
            return lines
        if selector:
            lines.append(f"{indent}page.locator({_py_str(selector)}).first.click()")
            return lines
        if name:
            lines.append(
                f"{indent}page.get_by_text({_py_str(name)}, exact=False).click()"
            )
            return lines
        lines.append(f"{indent}# TODO: 补充点击定位")
        return lines

    lines.append(f"{indent}# TODO: 未识别操作 type={action_type}")
    return lines


def _collapse_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse consecutive typing/navigations so drafts stay replayable and short."""
    collapsed: list[dict[str, Any]] = []
    last_nav_url = ""
    for action in actions:
        action_type = action.get("type")
        if action_type not in {"navigate", "click", "fill", "change", "input"}:
            continue
        if action_type == "navigate":
            last_nav_url = str(action.get("url") or "")
        # Already navigated into a page: skip redundant left-menu clicks
        if action_type == "click":
            name = str(action.get("name") or action.get("text") or "")
            tag = str(action.get("tag") or "").lower()
            if tag == "a" and name and last_nav_url:
                # e.g. goto .../salesClue then click 销售线索 again
                if any(token in last_nav_url.lower() for token in ("salesclue", "lead", "crm")):
                    if any(k in name for k in ("销售线索", "线索", "CRM")):
                        continue
        if not collapsed:
            collapsed.append(action)
            continue
        prev = collapsed[-1]
        prev_type = prev.get("type")
        if action_type == "navigate" and prev_type == "navigate":
            collapsed[-1] = action
            last_nav_url = str(action.get("url") or "")
            continue
        if action_type in {"fill", "change", "input"} and prev_type in {
            "fill",
            "change",
            "input",
        }:
            same_field = (prev.get("selector") or "") == (action.get("selector") or "") and (
                prev.get("placeholder") or ""
            ) == (action.get("placeholder") or "")
            if same_field:
                collapsed[-1] = action
                continue
        # Drop click-then-immediate-fill on same selector (click is redundant)
        if (
            action_type in {"fill", "change", "input"}
            and prev_type == "click"
            and (prev.get("selector") or "")
            and (prev.get("selector") or "") == (action.get("selector") or "")
        ):
            collapsed[-1] = action
            continue
        # Drop empty combobox clicks that have no following option selection in recording
        if (
            action_type == "click"
            and (action.get("role") or "") == "combobox"
            and not (action.get("value") or "")
        ):
            # keep only if next meaningful action targets same selector with fill; decide later
            pass
        collapsed.append(action)
    return collapsed


def generate_ui_draft(
    *,
    session_dir: Path,
    actions: list[dict[str, Any]],
    title: str,
) -> Path:
    drafts_dir = session_dir / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(title)
    func_slug = re.sub(r"[^0-9a-zA-Z_]", "_", slug)
    out = drafts_dir / f"test_ui_recorded_{slug}.py"

    useful_actions = _collapse_actions(actions)
    # 去掉登录页导航；登录改由 authenticated_page + APP_HOME_URL 完成
    useful_actions = [
        a
        for a in useful_actions
        if not (
            a.get("type") == "navigate"
            and "login" in str(a.get("url") or "").lower()
        )
    ]
    steps: list[str] = []
    for action in useful_actions:
        # 跳过无法在无头回放的本地文件伪路径
        if action.get("type") in {"fill", "change", "input"}:
            value = str(action.get("value") or "")
            if "fakepath" in value.lower() or value.lower().endswith(
                (".jpg", ".jpeg", ".png", ".pdf", ".doc", ".docx")
            ):
                steps.append(
                    "        # TODO: 上传文件请改为 set_input_files 真实测试附件，已跳过: "
                    f"{_py_str(value)}"
                )
                continue
        steps.extend(_safe_selector_step(action, indent="        "))

    if not steps:
        steps = [
            "        # 本次未捕获到可回放的 UI 操作，请手工补充步骤",
            '        page.goto("https://test-platform.ysbpack.com/memberCenter/crm2Ability/salesClue", wait_until="domcontentloaded")',
        ]

    body = "\n".join(steps)
    content = f'''"""AUTO-GENERATED UI draft from CRM recording session.

请人工复核选择器与断言后，再移动到 tests/ 并补充 page object。
生成时间: {datetime.now().isoformat(timespec="seconds")}
来源目录: {session_dir.as_posix()}

运行方式（不要用 python 直接跑本文件；浏览器结束即关闭属正常，勿中途手动能登录）:
  $env:HEADLESS="false"
  $env:CRM_UI_PAUSE_ON_FAILURE="true"
  pytest "{out.as_posix()}" -v -s
"""

import re

import allure
import pytest
from playwright.sync_api import Page, expect

from config.settings import (
    APP_HOME_URL,
    CRM_GOTO_RETRIES,
    CRM_GOTO_WAIT_UNTIL,
    CRM_NAV_TIMEOUT_MS,
    CRM_UI_PAUSE_ON_FAILURE,
)


pytestmark = pytest.mark.crm_ui_draft


def _goto_resilient(page: Page, url: str) -> None:
    page.set_default_navigation_timeout(CRM_NAV_TIMEOUT_MS)
    last_error: Exception | None = None
    for attempt in range(1, max(CRM_GOTO_RETRIES, 1) + 1):
        try:
            page.goto(url, wait_until=CRM_GOTO_WAIT_UNTIL, timeout=CRM_NAV_TIMEOUT_MS)
            page.wait_for_timeout(1500)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            page.wait_for_timeout(1000 * attempt)
    assert last_error is not None
    raise last_error


@allure.feature("CRM UI 录制草稿")
@allure.story({_py_str(title)})
@allure.title({_py_str(f"[草稿] {title}")})
def test_ui_recorded_{func_slug}(authenticated_page):
    page = authenticated_page
    try:
        with allure.step("接口登录态注入后进入系统首页"):
            _goto_resilient(page, APP_HOME_URL)
            assert "login" not in page.url.lower(), f"登录态注入失败，仍在: {{page.url}}"

        with allure.step("按录制顺序回放关键操作"):
{body}

        with allure.step("校验未掉回登录页"):
            expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=10000)
    except Exception:
        if CRM_UI_PAUSE_ON_FAILURE:
            page.pause()
        raise
'''
    out.write_text(content, encoding="utf-8")
    return out


def _guess_body_var(sample: dict[str, Any]) -> str:
    body = sample.get("request_body")
    if isinstance(body, dict):
        return json.dumps(body, ensure_ascii=False, indent=4)
    if isinstance(body, str) and body.strip():
        try:
            parsed = json.loads(body)
            return json.dumps(parsed, ensure_ascii=False, indent=4)
        except json.JSONDecodeError:
            return _py_str(body)
    return "{}"


def generate_api_draft(
    *,
    session_dir: Path,
    main_apis: list[ScoredApiCall],
    title: str,
) -> Path:
    drafts_dir = session_dir / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(title)
    func_slug = re.sub(r"[^0-9a-zA-Z_]", "_", slug)
    out = drafts_dir / f"test_api_recorded_{slug}.py"

    case_blocks: list[str] = []
    for idx, api in enumerate(main_apis, start=1):
        parsed = urlparse(api.url)
        path_or_url = api.url
        body_literal = _guess_body_var(api.sample)
        referer_path = parsed.path if parsed.path.startswith("/") else "/"
        if api.method == "GET":
            call_lines = (
                "    headers = CrmLeadService.build_headers(crm_auth, "
                f"referer_path={_py_str(referer_path)})\n"
                f"    resp = api_client.request(\n"
                f"        {_py_str(api.method)},\n"
                f"        {_py_str(path_or_url)},\n"
                f"        headers=headers,\n"
                f"    )\n"
                f"    body = resp.json()\n"
            )
        else:
            call_lines = (
                f"    payload = {body_literal}\n"
                "    headers = CrmLeadService.build_headers(crm_auth, "
                f"referer_path={_py_str(referer_path)})\n"
                f"    resp = api_client.request(\n"
                f"        {_py_str(api.method)},\n"
                f"        {_py_str(path_or_url)},\n"
                f"        json_body=payload if isinstance(payload, dict) else None,\n"
                f"        data=None if isinstance(payload, dict) else payload,\n"
                f"        headers=headers,\n"
                f"    )\n"
                f"    body = resp.json()\n"
            )
        case_blocks.append(
            f'''
@allure.feature("CRM 接口录制草稿")
@allure.story({_py_str(title)})
@allure.title({_py_str(f"[草稿][{idx}] {api.method} {api.path}")})
def test_api_recorded_{func_slug}_{idx:02d}(crm_auth, api_client):
    """score={api.score} count={api.count} status={api.status} host={parsed.netloc}

    确认稳定后：加 pytest.mark.api，沉淀到 api/services，再进日回归。
    """
    # TODO: 将 payload 中的动态字段改为 settings 或 data factory
{call_lines}    allure.attach(
        json.dumps(body, ensure_ascii=False, indent=2),
        name="api_response",
        attachment_type=allure.attachment_type.JSON,
    )
    assert resp.status_code < 400, f"HTTP 失败: {{resp.status_code}} {{body}}"
    # CRM 常见成功码；若该接口不同请改断言
    if isinstance(body, dict) and "code" in body:
        assert body.get("code") == 1000, f"业务失败: {{body}}"
'''
        )

    if not case_blocks:
        case_blocks.append(
            f'''
@allure.feature("CRM 接口录制草稿")
@allure.story({_py_str(title)})
@allure.title({_py_str(f"[草稿] {title} 无主接口")})
def test_api_recorded_{func_slug}_empty(crm_auth):
    pytest.skip("录制会话未识别到主接口，请调整过滤规则后重录")
'''
        )

    content = f'''"""AUTO-GENERATED API draft from CRM recording session.

请人工复核 URL / payload / 断言后，再沉淀到 api/services 与 tests/test_api_*.py。
生成时间: {datetime.now().isoformat(timespec="seconds")}
来源目录: {session_dir.as_posix()}

使用提示:
1. fixture `crm_auth` / `api_client` 来自 tests/fixtures/api.py
2. 草稿默认不带 pytest.mark.api，确认后再挂 marker 并挪到 tests/
3. 动态 ID、token、手机号等请参数化，勿直接提交敏感真实数据
"""

import json

import allure
import pytest

from api.services.crm_lead_service import CrmLeadService


{"".join(case_blocks)}
'''
    out.write_text(content, encoding="utf-8")
    return out


def generate_summary(
    *,
    session_dir: Path,
    title: str,
    actions: list[dict[str, Any]],
    all_calls: list[dict[str, Any]],
    main_apis: list[ScoredApiCall],
    ui_draft: Path,
    api_draft: Path,
) -> Path:
    lines = [
        f"# CRM 录制会话摘要: {title}",
        "",
        f"- 目录: `{session_dir.as_posix()}`",
        f"- UI 操作数: {len(actions)}",
        f"- 原始接口数: {len(all_calls)}",
        f"- 主接口数: {len(main_apis)}",
        f"- UI 草稿: `{ui_draft.name}`",
        f"- API 草稿: `{api_draft.name}`",
        "",
        "## 主接口清单",
        "",
    ]
    if not main_apis:
        lines.append("- （无）")
    for api in main_apis:
        lines.append(
            f"- score={api.score} x{api.count} `{api.method} {api.path}` status={api.status}"
        )
    lines.extend(
        [
            "",
            "## 建议下一步",
            "",
            "1. 打开 `drafts/` 检查选择器与 payload",
            "2. 将稳定的主接口沉淀到 `api/services/`，薄测试放到 `tests/`",
            "3. UI 建议抽到 `pages/` page object，不要长期保留录制选择器",
            "4. 确认后挂上日常 marker（如 `pytest.mark.api`）再进 Jenkins",
            "",
        ]
    )
    out = session_dir / "SUMMARY.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
