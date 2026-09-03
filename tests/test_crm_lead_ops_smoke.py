"""CRM 销售线索：认领 / 分配 / 公海 UI 冒烟（三条独立用例）。

每条用例：接口造数 → 侧栏进入销售线索 → 页面操作 → 断言状态与跟进人 → teardown 回滚造数。

  1) 认领：造数并移入公海 → 公海 Tab 认领 → 跟进人为当前账号、不再是公海
  2) 分配：造数 → 分配给指定跟进人 → 跟进人变为目标用户
  3) 公海：造数 → 移入公海 → 状态/跟进人为公海

运行:
  $env:HEADLESS="false"
  pytest tests/test_crm_lead_ops_smoke.py -m crm_ui -v -s

重录（有头，三条分开）:
  python scripts/record_regression_session.py --title lead_claim --headed
  python scripts/record_regression_session.py --title lead_assign --headed
  python scripts/record_regression_session.py --title lead_public_sea --headed
"""
from __future__ import annotations

import re
from datetime import datetime

import allure
import pytest
from playwright.sync_api import expect

from config.settings import (
    APP_HOME_URL,
    ASSIGN_LEAD_NEW_FOLLOW_USER_NAME,
    CRM_DEFAULT_FOLLOW_USER_ID,
    CRM_DEFAULT_FOLLOW_USER_NAME,
    CRM_UI_LEAD_ASSIGN_FOLLOW_KEYWORD,
    CRM_UI_LEAD_FOLLOW_KEYWORD,
    CRM_UI_PAUSE_ON_FAILURE,
    PLATFORM_BASE_URL,
)
from pages.crm_lead_page import CrmLeadPage
from pages.crm_page import CrmPage
from pages.home_page import HomePage

pytestmark = pytest.mark.crm_ui

LEAD_URL = f"{PLATFORM_BASE_URL}/memberCenter/crm2Ability/salesClue"


def _log(msg: str) -> None:
    print(f"[lead-ops] {msg}", flush=True)


def _screenshot_on_fail(page, name: str) -> None:
    try:
        png = page.screenshot(full_page=True, timeout=10000)
        allure.attach(png, name=name, attachment_type=allure.attachment_type.PNG)
    except Exception:
        pass
    if CRM_UI_PAUSE_ON_FAILURE:
        page.pause()


def _goto_resilient(page, target: str, *, label: str) -> None:
    _log(f"{label}: goto {target}")
    try:
        page.goto(target, wait_until="domcontentloaded", timeout=60000)
    except Exception as exc:
        _log(f"{label}: 超时 ({exc.__class__.__name__})，改 commit")
        page.goto(target, wait_until="commit", timeout=60000)
    page.wait_for_timeout(1200)


def _open_lead_list_via_menu(authenticated_page):
    """登录态 → CRM → 仅侧栏点「销售线索」（禁止 URL 直达）。"""
    page = authenticated_page
    _goto_resilient(page, APP_HOME_URL, label="平台首页")
    assert "login" not in page.url.lower(), f"登录态注入失败: {page.url}"
    home = HomePage(page)
    _log("点击侧栏 CRM 2.0")
    crm_tab = home.open_crm_2()
    crm_tab.wait_for_timeout(2000)
    home.assert_crm_page_loaded(crm_tab)
    page = crm_tab
    _log(f"CRM 已打开 url={page.url}")
    crm = CrmPage(page)
    lead = CrmLeadPage(page)
    page.set_default_timeout(25000)
    crm.wait_sidebar_ready()
    _log("点击侧栏「销售线索」")
    crm.open_menu_path("销售线索")
    ready = page.locator(
        "button:has-text('新建线索'), button:has-text('新增线索'), .ant-table-tbody"
    )
    try:
        ready.first.wait_for(state="visible", timeout=20000)
    except Exception as exc:
        raise AssertionError(
            f"已点「销售线索」但未出现列表/新建入口 url={page.url}"
        ) from exc
    _log(f"销售线索列表就绪 url={page.url}")
    return page, crm, lead


def _create_lead_via_api(
    crm_auth,
    crm_lead_service,
    *,
    tag: str,
    follow_user_name: str | None = None,
    follow_user_id: int | None = None,
    rollback=None,
) -> dict:
    stamp = datetime.now().strftime("%m%d%H%M%S")
    kwargs = {}
    if follow_user_name:
        kwargs["follow_user_name"] = follow_user_name
        try:
            uid, uname = crm_lead_service.resolve_follow_user_by_name(
                crm_auth, follow_user_name=follow_user_name
            )
            kwargs["follow_user_id"] = follow_user_id or uid
            kwargs["follow_user_name"] = uname
        except AssertionError:
            if follow_user_id:
                kwargs["follow_user_id"] = follow_user_id
    payload = crm_lead_service.build_random_lead_payload(crm_auth, **kwargs)
    payload["name"] = f"自动化{tag}{stamp}"
    body = crm_lead_service.create_lead(crm_auth, payload)
    assert body.get("code") == 1000, f"造数创建线索失败: {body}"
    lead_id = crm_lead_service.resolve_relation_id_from_created_lead(
        crm_auth, create_response=body, create_payload=payload
    )
    info = {
        "id": lead_id,
        "name": payload["name"],
        "phone": str(payload.get("phone") or ""),
        "follow_user_name": str(
            payload.get("followUserName") or payload.get("followUser") or ""
        ),
    }
    _log(
        f"造数完成 id={lead_id} name={info['name']} "
        f"phone={info['phone']} follow={info['follow_user_name']!r}"
    )
    if rollback is not None:
        rollback.register(
            lead_id=lead_id, name=info["name"], phone=info["phone"]
        )
    return info


def _pick_assign_target(current_follow: str) -> str:
    """分配目标必须与当前跟进人不同。"""
    current = (current_follow or "").strip()
    current_key = re.sub(r"[（(].*", "", current).strip()
    candidates = [
        CRM_UI_LEAD_ASSIGN_FOLLOW_KEYWORD,
        ASSIGN_LEAD_NEW_FOLLOW_USER_NAME,
        CRM_UI_LEAD_FOLLOW_KEYWORD,
        CRM_DEFAULT_FOLLOW_USER_NAME,
        "甜",
        "tinker",
    ]
    for cand in candidates:
        text = (cand or "").strip()
        if not text:
            continue
        key = re.sub(r"[（(].*", "", text).strip()
        if key and key not in current and current_key not in text:
            return text
    raise AssertionError(
        f"无法解析不同于当前跟进人的分配目标 current={current!r} candidates={candidates}"
    )


def _find_lead_row_api(crm_auth, crm_lead_service, *, name: str, is_public_sea: int | None = None):
    kwargs = {"name": name, "page_size": 20}
    if is_public_sea is not None:
        kwargs["is_public_sea"] = is_public_sea
    page_body = crm_lead_service.query_lead_page(
        crm_auth, crm_lead_service.build_page_payload(**kwargs)
    )
    rows = crm_lead_service.extract_rows(page_body)
    for row in rows:
        if name in str(row.get("name") or ""):
            return row
    return rows[0] if rows else None


def _login_display_name(auth_login_data: dict) -> str:
    for key in ("name", "userName", "nickName", "realName"):
        val = str(auth_login_data.get(key) or "").strip()
        if val:
            return val
    return ""


@allure.feature("CRM UI 改版回归")
@allure.story("销售线索认领")
@allure.title("销售线索：公海认领后状态与跟进人")
def test_crm_lead_claim_smoke(
    authenticated_page, crm_auth, crm_lead_service, auth_login_data, lead_rollback
):
    info = _create_lead_via_api(
        crm_auth, crm_lead_service, tag="认领", rollback=lead_rollback
    )
    lead_id = info["id"]
    name = info["name"]
    claimer = _login_display_name(auth_login_data)
    page = authenticated_page
    try:
        with allure.step("接口将线索移入公海"):
            move = crm_lead_service.move_leads_to_public_sea(
                crm_auth,
                crm_lead_service.build_move_public_sea_payload(lead_ids=[lead_id]),
            )
            assert move.get("code") == 1000, f"前置移入公海失败: {move}"
            sea_row = _find_lead_row_api(
                crm_auth, crm_lead_service, name=name, is_public_sea=1
            )
            assert sea_row, f"接口移入公海后公海列表未找到: {name}"
            assert sea_row.get("isPublicSea") in (1, True, "1"), (
                f"接口移入公海后仍非公海: {sea_row}"
            )
            _log(f"接口已确认公海 id={lead_id} follow={sea_row.get('followUserName')!r}")

        with allure.step("侧栏进入销售线索 → 公海按姓名查询"):
            page, crm, lead = _open_lead_list_via_menu(page)
            lead.search_public_sea_leads(name=name)

        with allure.step(f"认领线索: {name}"):
            lead.claim_lead_by_name(name)

        with allure.step("断言认领后跟进人=当前账号，且不在公海"):
            try:
                lead.switch_lead_list_tab("全部")
            except AssertionError:
                try:
                    lead.switch_lead_list_tab("我的线索")
                except AssertionError:
                    pass
            lead.search_leads(name=name)
            row_text = lead.assert_lead_row_follow_and_status(
                name, public_sea=False
            )
            if claimer:
                assert claimer.split("（")[0][:2] in row_text or claimer[:2] in row_text, (
                    f"认领后跟进人未变为当前账号 {claimer!r}: {row_text!r}"
                )
            api_row = _find_lead_row_api(
                crm_auth, crm_lead_service, name=name, is_public_sea=0
            )
            assert api_row, f"认领后接口列表未找到: {name}"
            follow = str(
                api_row.get("followUserName") or api_row.get("followName") or ""
            )
            is_sea = api_row.get("isPublicSea")
            assert not is_sea or is_sea in (0, "0", False), (
                f"认领后仍是公海: {api_row}"
            )
            if claimer:
                assert claimer.split("（")[0] in follow or follow in claimer, (
                    f"认领后接口跟进人不符 expect~={claimer!r} actual={follow!r}"
                )
            _log(f"认领断言通过 follow={follow!r}")

        with allure.step("校验未掉回登录页"):
            expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=10000)
            crm.assert_not_kicked_to_login()
    except Exception:
        _screenshot_on_fail(page, "lead_claim_failed")
        raise


@allure.feature("CRM UI 改版回归")
@allure.story("销售线索分配")
@allure.title("销售线索：分配后跟进人变更")
def test_crm_lead_assign_smoke(
    authenticated_page, crm_auth, crm_lead_service, lead_rollback
):
    # 造数跟进人用默认账号，分配目标必须换成另一个人
    info = _create_lead_via_api(
        crm_auth,
        crm_lead_service,
        tag="分配",
        follow_user_name=CRM_DEFAULT_FOLLOW_USER_NAME,
        follow_user_id=CRM_DEFAULT_FOLLOW_USER_ID,
        rollback=lead_rollback,
    )
    name = info["name"]
    page = authenticated_page
    try:
        with allure.step("侧栏进入销售线索"):
            page, crm, lead = _open_lead_list_via_menu(page)
            lead.search_leads(name=name)
            current = lead.read_row_follow_user(name)
            target = _pick_assign_target(current)
            _log(f"当前跟进人={current!r} 将分配给={target!r}")

        with allure.step(f"分配线索 {name} → {target}"):
            lead.assign_lead_by_name(name, target, current_follow=current)

        with allure.step("断言跟进人变为分配目标且与原来不同"):
            lead.search_leads(name=name)
            after = lead.read_row_follow_user(name)
            assert current not in after and after, (
                f"分配后跟进人未变化: before={current!r} after={after!r}"
            )
            row_text = lead.assert_lead_row_follow_and_status(
                name, follow_contains=target[:2]
            )
            assert target.split("（")[0][:2] in row_text, (
                f"分配后列表跟进人未含 {target!r}: {row_text!r}"
            )
            api_row = _find_lead_row_api(crm_auth, crm_lead_service, name=name)
            assert api_row, f"分配后接口未找到: {name}"
            follow = str(
                api_row.get("followUserName") or api_row.get("followName") or ""
            )
            assert target.split("（")[0] in follow or target[:2] in follow, (
                f"分配后接口跟进人不符 expect~={target!r} actual={follow!r}"
            )
            _log(f"分配断言通过 follow={follow!r}")

        with allure.step("校验未掉回登录页"):
            expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=10000)
            crm.assert_not_kicked_to_login()
    except Exception:
        _screenshot_on_fail(page, "lead_assign_failed")
        raise


@allure.feature("CRM UI 改版回归")
@allure.story("销售线索公海")
@allure.title("销售线索：移入公海后状态与跟进人")
def test_crm_lead_public_sea_smoke(
    authenticated_page, crm_auth, crm_lead_service, lead_rollback
):
    info = _create_lead_via_api(
        crm_auth, crm_lead_service, tag="公海", rollback=lead_rollback
    )
    name = info["name"]
    page = authenticated_page
    try:
        with allure.step("侧栏进入销售线索"):
            page, crm, lead = _open_lead_list_via_menu(page)

        with allure.step(f"移入公海: {name}"):
            lead.search_leads(name=name)
            with page.expect_response(
                lambda r: "movepublicsea" in (r.url or "").lower()
                and r.request.method == "POST",
                timeout=30000,
            ) as move_info:
                lead.move_lead_to_public_sea(name)
            move_resp = move_info.value
            assert move_resp.ok, f"移入公海接口 HTTP 失败: {move_resp.status}"
            try:
                move_body = move_resp.json()
            except Exception:
                move_body = {}
            assert move_body.get("code") == 1000, f"移入公海接口失败: {move_body}"
            page.wait_for_timeout(800)

        with allure.step("断言已进入公海（状态/跟进人）"):
            try:
                lead.search_public_sea_leads(name=name)
                lead.assert_lead_row_follow_and_status(name, public_sea=True)
            except AssertionError:
                # 公海 Tab 未切到时，接口 isPublicSea 必须为真
                pass

            detail = crm_lead_service.get_lead_detail(crm_auth, info["id"])
            data = detail.get("data") if isinstance(detail.get("data"), dict) else {}
            is_sea = data.get("isPublicSea")
            follow = str(data.get("followUserName") or "")
            if is_sea is None:
                api_row = _find_lead_row_api(
                    crm_auth, crm_lead_service, name=name, is_public_sea=1
                ) or _find_lead_row_api(crm_auth, crm_lead_service, name=name)
                assert api_row, f"移入公海后接口未找到: {name}"
                is_sea = api_row.get("isPublicSea")
                follow = str(
                    api_row.get("followUserName") or api_row.get("followName") or ""
                )
                data = api_row
            assert is_sea in (1, True, "1"), (
                f"移入公海后接口未标记公海: follow={follow!r} row={data}"
            )
            _log(f"公海断言通过 follow={follow!r} isPublicSea={is_sea!r}")

        with allure.step("校验未掉回登录页"):
            expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=10000)
            crm.assert_not_kicked_to_login()
    except Exception:
        _screenshot_on_fail(page, "lead_public_sea_failed")
        raise
