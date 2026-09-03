"""CRM 销售线索主路径 UI 冒烟（对齐 recordings/20260807-160515）。

覆盖：
  1) 新建线索（含同公司「线索重复 → 继续创建」）→ 筛选断言 → 详情
  2) 独立删除回滚用例（页面操作删除上一条新建线索）

运行:
  $env:HEADLESS="false"
  pytest tests/test_crm_lead_smoke.py -m crm_ui -v -s
  # 浏览器兼容矩阵:
  pytest tests/test_crm_lead_smoke.py -m crm_ui --ui-browsers=chromium,firefox,webkit
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import allure
import pytest
from playwright.sync_api import expect

from config.settings import (
    APP_HOME_URL,
    CRM_UI_LEAD_COMPANY_KEYWORD,
    CRM_UI_LEAD_EXHIBITION_KEYWORD,
    CRM_UI_LEAD_FOLLOW_KEYWORD,
    CRM_UI_LEAD_QICHACHA_BACKFILL,
    CRM_UI_LEAD_SOURCE_TEXT,
    CRM_UI_PAUSE_ON_FAILURE,
    PLATFORM_BASE_URL,
    PROJECT_ROOT,
)
from pages.crm_lead_page import CrmLeadPage
from pages.crm_page import CrmPage
from pages.home_page import HomePage

pytestmark = pytest.mark.crm_ui

LEAD_URL = f"{PLATFORM_BASE_URL}/memberCenter/crm2Ability/salesClue"
# 优先用 CRM 专用样例（真实 JPEG）；兼容旧路径
_SAMPLE_JPG = PROJECT_ROOT / "testdata" / "crm" / "lead_attachment_sample.jpg"
if not _SAMPLE_JPG.is_file():
    _SAMPLE_JPG = PROJECT_ROOT / "testdata" / "order" / "contract_sample.jpg"
_LEAD_CTX_DIR = PROJECT_ROOT / "reports"
_LEAD_CTX_FILE = _LEAD_CTX_DIR / "crm_lead_last_created.json"

# 同进程内按浏览器隔离交接（--ui-browsers 矩阵时避免互相覆盖）
_LEAD_CTX_BY_BROWSER: dict[str, dict] = {}


def _log(msg: str) -> None:
    print(f"[lead-smoke] {msg}", flush=True)


def _ctx_key(browser_name: str | None) -> str:
    return (browser_name or "chromium").strip().lower() or "chromium"


def _lead_ctx_path(browser_name: str | None) -> Path:
    key = _ctx_key(browser_name)
    if key == "chromium":
        # 兼容单浏览器历史路径
        return _LEAD_CTX_FILE
    return _LEAD_CTX_DIR / f"crm_lead_last_created_{key}.json"


def _save_lead_ctx(ctx: dict, *, browser_name: str = "chromium") -> None:
    key = _ctx_key(browser_name)
    payload = dict(ctx)
    payload["browser"] = key
    _LEAD_CTX_BY_BROWSER[key] = payload
    path = _lead_ctx_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_lead_ctx(*, browser_name: str = "chromium") -> dict:
    key = _ctx_key(browser_name)
    mem = _LEAD_CTX_BY_BROWSER.get(key) or {}
    if mem.get("name"):
        return dict(mem)
    path = _lead_ctx_path(key)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("name"):
                return data
        except Exception:
            pass
    return {}


def _clear_lead_ctx(*, browser_name: str = "chromium") -> None:
    key = _ctx_key(browser_name)
    _LEAD_CTX_BY_BROWSER.pop(key, None)
    path = _lead_ctx_path(key)
    if path.is_file():
        path.unlink(missing_ok=True)


def _goto_resilient(page, target: str, *, label: str) -> None:
    _log(f"{label}: goto {target}")
    try:
        page.goto(target, wait_until="domcontentloaded", timeout=60000)
    except Exception as exc:
        _log(f"{label}: domcontentloaded 超时 ({exc.__class__.__name__}), 改用 commit")
        page.goto(target, wait_until="commit", timeout=60000)
    page.wait_for_timeout(1500)
    _log(f"{label}: 当前 url={page.url}")


def _open_lead_list(authenticated_page):
    page = authenticated_page
    with allure.step("进入平台并打开销售线索"):
        _goto_resilient(page, APP_HOME_URL, label="首页")
        assert "login" not in page.url.lower(), f"登录态注入失败: {page.url}"
        home = HomePage(page)
        try:
            page.wait_for_timeout(1500)
            _log("点击侧栏 CRM 2.0")
            crm_tab = home.open_crm_2()
            crm_tab.wait_for_timeout(2000)
            home.assert_crm_page_loaded(crm_tab)
            page = crm_tab
            _log(f"CRM 已打开 url={page.url}")
        except AssertionError as exc:
            _log(f"WARN: open_crm_2 失败 ({exc})，直达线索页")
            _goto_resilient(page, LEAD_URL, label="线索直达")
            assert "login" not in page.url.lower(), f"直达线索页掉登录: {page.url}"

        crm = CrmPage(page)
        lead = CrmLeadPage(page)
        page.set_default_timeout(25000)
        _goto_resilient(page, LEAD_URL, label="线索列表")
        if "salesclue" not in page.url.lower() and "salesClue" not in page.url:
            crm.open_menu_path("销售线索")

        # SPA 首屏偶发空壳：等列表关键控件，必要时刷新一次
        ready = page.locator(
            "button:has-text('新建线索'), button:has-text('新增线索'), "
            "#salesclue_form_companyName, .ant-table-tbody"
        )
        for attempt in range(3):
            try:
                ready.first.wait_for(state="visible", timeout=25000)
                break
            except Exception:
                _log(f"线索页未就绪 attempt={attempt + 1}，刷新重试")
                try:
                    page.reload(wait_until="commit", timeout=60000)
                except Exception as exc:
                    _log(f"reload 异常 ({exc.__class__.__name__})，改 goto")
                    try:
                        page.goto(LEAD_URL, wait_until="commit", timeout=60000)
                    except Exception as exc2:
                        _log(f"goto 仍失败: {exc2}")
                page.wait_for_timeout(2500)
        else:
            # 最后再等一次，不因白屏探测过严直接失败
            try:
                ready.first.wait_for(state="visible", timeout=15000)
            except Exception:
                raise AssertionError(f"销售线索页未出现列表/新建入口 url={page.url}")

        crm.assert_menu_reachable("销售线索")
        _log("线索列表就绪")
        return page, crm, lead


def _screenshot_on_fail(page, name: str):
    png = page.screenshot(full_page=True)
    allure.attach(png, name=name, attachment_type=allure.attachment_type.PNG)
    if CRM_UI_PAUSE_ON_FAILURE:
        page.pause()


@allure.feature("CRM UI 改版回归")
@allure.story("销售线索主路径")
@allure.title("销售线索：新建 → 筛选查询 → 详情")
def test_crm_lead_main_path_smoke(authenticated_page, browser_name):
    """创建（重复则继续创建）→ 筛选断言 → 详情；线索留给同浏览器删除用例回滚。"""
    stamp = datetime.now().strftime("%m%d%H%M%S")
    # 浏览器后缀避免矩阵并行/同秒撞名
    suffix = {"chromium": "", "firefox": "F", "webkit": "W"}.get(browser_name, browser_name[:1].upper())
    lead_name = f"自动化线索{stamp}{suffix}"
    phone = f"138{stamp[-8:]}"[:11]
    if suffix:
        # 同秒多浏览器时错开手机号末位
        phone = (phone[:-1] + {"F": "1", "W": "2"}.get(suffix, "3"))[:11]
    email = f"auto_lead_{stamp}{suffix.lower() or 'c'}@qq.com"
    today = CrmLeadPage.today_str()
    page = authenticated_page
    _log(f"browser={browser_name}")

    try:
        page, crm, lead = _open_lead_list(page)

        with allure.step(f"新建线索: {lead_name}"):
            _log(f"新建 name={lead_name} phone={phone}")
            lead.open_create_form()
            lead.fill_create_basic(
                name=lead_name,
                phone=phone,
                email=email,
                follow_user_keyword=CRM_UI_LEAD_FOLLOW_KEYWORD,
                channel_detail="自动化渠道详情",
                company_keyword=CRM_UI_LEAD_COMPANY_KEYWORD,
                remark=f"自动化询盘备注{stamp}",
                source_text=CRM_UI_LEAD_SOURCE_TEXT,
                exhibition_keyword=CRM_UI_LEAD_EXHIBITION_KEYWORD,
                qichacha_backfill=CRM_UI_LEAD_QICHACHA_BACKFILL,
                attachment=_SAMPLE_JPG if _SAMPLE_JPG.is_file() else None,
            )
            lead.confirm_save()  # 先保存；若查重再「继续创建」
            page.wait_for_timeout(1500)
            _log("保存完成（含重复确认）")

        with allure.step("按企业/手机/邮箱/创建时间筛选并断言"):
            lead.search_leads(
                company_name=CRM_UI_LEAD_COMPANY_KEYWORD,
                phone=phone,
                email=email,
                follow_keyword=CRM_UI_LEAD_FOLLOW_KEYWORD,
                create_time_start=today,
                create_time_end=today,
            )
            row = page.locator(".ant-table-tbody a").filter(has_text=lead_name)
            if row.count() == 0:
                row = page.locator(".ant-table-tbody a").filter(
                    has_text=re.compile(
                        f"{re.escape(lead_name)}|{re.escape(CRM_UI_LEAD_COMPANY_KEYWORD)}"
                    )
                )
            expect(row.first).to_be_visible(timeout=20000)
            lead.assert_row_exists(lead_name)
            _log("筛选命中新建线索")

        with allure.step("打开线索详情并断言询盘/附件/关键决策人"):
            if page.get_by_role("link", name=lead_name).count() > 0:
                lead.open_row_by_name(lead_name)
            else:
                page.locator(".ant-table-tbody a").first.click()
                page.wait_for_timeout(1200)
            # 详情：关键决策人应为「是」
            detail = page.locator(
                ".ant-drawer-open, .ant-modal-wrap:not([style*='display: none'])"
            ).filter(has_text=re.compile(r"线索详情|基础信息"))
            host = detail.first if detail.count() > 0 else page
            dm = host.get_by_text(re.compile(r"关键决策人")).first
            try:
                dm.scroll_into_view_if_needed(timeout=3000)
            except Exception:
                pass
            # 同一表单项附近应出现「是」
            dm_row = host.locator(".ant-descriptions-item, .ant-form-item, tr, div").filter(
                has_text=re.compile(r"关键决策人")
            )
            dm_text = ""
            if dm_row.count() > 0:
                dm_text = (dm_row.first.inner_text() or "").replace("\n", " ")
            assert "是" in dm_text, f"详情关键决策人未选上（仍像默认否）: {dm_text!r}"
            _log(f"详情关键决策人: {dm_text!r}")

            # 详情：附件区应有缩略图/链接，不能只有空「上传附件」占位
            att_zone = host.locator(".ant-form-item, .ant-descriptions-item, section, div").filter(
                has_text=re.compile(r"上传附件")
            )
            zone = att_zone.first if att_zone.count() > 0 else host
            att = zone.locator(
                ".ant-upload-list-item-done, .ant-upload-list-item-success, "
                ".ant-upload-list-item img[src], .ant-image img[src], "
                "a[href*='http'], img[src*='http']"
            )
            # 排除空占位：至少要有 done / 真实 http(s) 图或链接
            ok_att = False
            if att.count() > 0:
                for i in range(min(att.count(), 10)):
                    node = att.nth(i)
                    cls = (node.get_attribute("class") or "")
                    src = node.get_attribute("src") or ""
                    href = node.get_attribute("href") or ""
                    if "done" in cls or "success" in cls:
                        ok_att = True
                        break
                    if src.startswith("http") or href.startswith("http"):
                        ok_att = True
                        break
            assert ok_att, (
                "详情上传附件仍为空占位：创建时附件可能未写入表单。"
                "请把真实样例放到 testdata/crm/（如 lead_attachment_sample.jpg）"
            )
            _log("详情已看到附件内容")
            lead.close_drawer()

        with allure.step("校验未掉回登录页"):
            expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=10000)
            crm.assert_not_kicked_to_login()

        _save_lead_ctx(
            {
                "name": lead_name,
                "phone": phone,
                "email": email,
                "company_keyword": CRM_UI_LEAD_COMPANY_KEYWORD,
                "created_at": today,
            },
            browser_name=browser_name,
        )
        _log(f"已写入删除用例上下文[{browser_name}]: {lead_name}")
    except Exception as exc:
        _log(f"失败: {exc.__class__.__name__}: {exc}")
        _screenshot_on_fail(page, f"lead_main_failed_{browser_name}")
        raise


@allure.feature("CRM UI 改版回归")
@allure.story("销售线索主路径")
@allure.title("销售线索：删除回滚（页面操作）")
def test_crm_lead_delete_rollback(authenticated_page, browser_name):
    """独立删除用例：筛选上一条同浏览器自动化线索 → 页面删除 → 断言不存在。

    依赖同文件新建用例写入的上下文（按 browser 隔离；内存或 reports/crm_lead_last_created*.json）。
    """
    ctx = _load_lead_ctx(browser_name=browser_name)
    if not ctx.get("name"):
        pytest.skip(
            f"无待删除线索上下文[{browser_name}]：请先跑 test_crm_lead_main_path_smoke，"
            "或提供 reports/crm_lead_last_created*.json"
        )

    lead_name = ctx["name"]
    phone = ctx.get("phone") or ""
    email = ctx.get("email") or ""
    company = ctx.get("company_keyword") or CRM_UI_LEAD_COMPANY_KEYWORD
    today = ctx.get("created_at") or CrmLeadPage.today_str()
    page = authenticated_page
    _log(f"browser={browser_name}")

    try:
        page, crm, lead = _open_lead_list(page)

        with allure.step(f"筛选待删除线索: {lead_name}"):
            _log(f"删除回滚 name={lead_name}")
            lead.search_leads(
                company_name=company,
                phone=phone,
                email=email,
                follow_keyword=CRM_UI_LEAD_FOLLOW_KEYWORD,
                create_time_start=today,
                create_time_end=today,
            )
            lead.assert_row_exists(lead_name)

        with allure.step("页面删除线索并确认"):
            lead.delete_row_by_name(lead_name)

        with allure.step("再次筛选断言已删除"):
            lead.search_leads(
                company_name=company,
                phone=phone,
                email=email,
                follow_keyword=CRM_UI_LEAD_FOLLOW_KEYWORD,
                create_time_start=today,
                create_time_end=today,
            )
            lead.assert_row_absent(lead_name)
            _log("删除回滚完成")

        with allure.step("校验未掉回登录页"):
            expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=10000)
            crm.assert_not_kicked_to_login()

        _clear_lead_ctx(browser_name=browser_name)
    except Exception as exc:
        _log(f"失败: {exc.__class__.__name__}: {exc}")
        _screenshot_on_fail(page, f"lead_delete_failed_{browser_name}")
        raise