"""拜访日程页。复用基类 Select / 日期 / 禁止 body(5,5) 与裸 Enter。"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from pages.crm_opportunity_page import CrmOpportunityPage


class CrmVisitSchedulePage(CrmOpportunityPage):
    """拜访日程：查询 / 新建 / 编辑 / 关联活动 / 解绑 / 删除。"""

    def _form_host(self):
        wraps = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none']), .ant-drawer-open"
        )
        for i in range(wraps.count()):
            w = wraps.nth(i)
            try:
                if not w.is_visible():
                    continue
            except Exception:
                continue
            text = ""
            try:
                text = w.inner_text() or ""
            except Exception:
                pass
            if "更改提醒时间" in text and "#scheduleName" not in text:
                if w.locator("#scheduleName").count() == 0:
                    continue
            if w.locator("#scheduleName").count() > 0:
                return w
            if "新建日程" in text or "编辑日程" in text:
                return w
        if wraps.count() > 0:
            try:
                if wraps.first.is_visible():
                    return wraps.first
            except Exception:
                pass
        return self.page

    def assert_list_ready(self) -> None:
        create = self.page.get_by_role("button", name=re.compile(r"新建日程"))
        if create.count() == 0:
            create = self.page.locator("button").filter(has_text=re.compile(r"新建日程"))
        table = self.page.locator(".ant-table-tbody, .ant-table")
        name = self.page.locator("#scheduleName")
        if create.count() == 0 and table.count() == 0 and name.count() == 0:
            raise AssertionError(f"拜访日程列表未渲染 url={self.page.url}")
        assert create.count() > 0 or name.count() > 0, (
            f"未找到新建日程/筛选 url={self.page.url}"
        )

    def _list_filter_input(self, selector: str):
        """列表筛选框：排除新建/编辑弹窗里的同名 id。"""
        loc = self.page.locator(selector)
        for i in range(loc.count()):
            el = loc.nth(i)
            try:
                if not el.is_visible():
                    continue
                in_modal = el.evaluate(
                    "e => !!e.closest('.ant-modal, .ant-drawer-content')"
                )
            except Exception:
                continue
            if not in_modal:
                return el
        return loc.first if loc.count() > 0 else None

    def click_reset(self) -> None:
        self.close_overlays()
        reset = self.page.locator("button").filter(has_text=re.compile(r"重\s*置"))
        if reset.count() == 0:
            reset = self.page.get_by_role("button", name=re.compile(r"重\s*置"))
        assert reset.count() > 0, "未找到日程「重置」"
        reset.first.click(timeout=8000)
        self.page.wait_for_timeout(600)

    def search_schedules(
        self,
        *,
        name: str = "",
        customer_keyword: str = "",
        status: str = "",
        wait_api: bool = True,
    ) -> dict | None:
        """列表筛选。跟进对象用可搜索 Select。"""
        self.close_overlays()
        self._wait_list_idle()
        if name:
            loc = self._list_filter_input("#scheduleName")
            assert loc is not None, "列表无日程名称 #scheduleName"
            loc.fill(name)
        if customer_keyword and self.page.locator("#customerIds").count() > 0:
            self.pick_follow_target("#customerIds", customer_keyword, multi=True)
        if status and self.page.locator("#scheduleStatus").count() > 0:
            try:
                self.select_searchable("#scheduleStatus", status)
            except AssertionError:
                dropdown = self._open_select_dropdown("#scheduleStatus")
                self._pick_dropdown_option(dropdown, status)
            self._dismiss_select_dropdown()
        body: dict | None = None
        if wait_api:
            try:
                with self.page.expect_response(
                    lambda r: "visit/schedule/page" in (r.url or "")
                    and r.request.method == "POST",
                    timeout=15000,
                ) as info:
                    self.click_search()
                try:
                    body = info.value.json()
                except Exception:
                    body = None
            except PlaywrightTimeoutError:
                self.click_search()
        else:
            self.click_search()
        self.page.wait_for_timeout(800)
        return body

    def row_by_name(self, name: str):
        row = self.page.locator(".ant-table-tbody tr").filter(has_text=name)
        assert row.count() > 0, f"日程列表未找到: {name}"
        return row.first

    def row_text(self, name: str) -> str:
        return (self.row_by_name(name).inner_text() or "").replace("\n", " ").strip()

    def assert_row_contains(self, name: str, *needles: str) -> str:
        text = self.row_text(name)
        for n in needles:
            if not n:
                continue
            assert n in text, f"日程行未包含 {n!r}: {text!r}"
        print(f"[visit] 行断言通过: {text[:160]!r}", flush=True)
        return text

    def assert_row_absent(self, name: str) -> None:
        self.page.wait_for_timeout(600)
        row = self.page.locator(".ant-table-tbody tr").filter(has_text=name)
        assert row.count() == 0, f"日程仍在列表: {name}"

    def _click_row_action(self, name: str, action: str) -> None:
        row = self.row_by_name(name)
        pat = re.compile(action)
        btn = row.get_by_role("button", name=pat)
        if btn.count() == 0:
            btn = row.locator("button, a, span").filter(has_text=pat)
        assert btn.count() > 0, f"日程行无操作「{action}」: {name}"
        btn.first.click(timeout=8000)
        self.page.wait_for_timeout(600)

    def open_create_form(self) -> None:
        self.close_overlays()
        btn = self.page.get_by_role("button", name=re.compile(r"新建日程"))
        if btn.count() == 0:
            btn = self.page.locator("button").filter(has_text=re.compile(r"新建日程"))
        assert btn.count() > 0, "未找到「新建日程」"
        btn.first.click(timeout=8000)
        self.page.wait_for_timeout(800)
        host = self._form_host()
        name = host.locator("#scheduleName")
        try:
            name.first.wait_for(state="visible", timeout=10000)
        except PlaywrightTimeoutError as exc:
            raise AssertionError("新建日程弹窗未出现 #scheduleName") from exc

    def _set_visit_date_today(self, host) -> None:
        """预计跟进日期：勾全天 → 点选今天（禁止 fill 只读 picker）。"""
        all_day = host.locator("#isAllDay, .ant-checkbox-wrapper").filter(
            has_text=re.compile(r"全天")
        )
        if all_day.count() == 0:
            all_day = host.get_by_text(re.compile(r"全天日程|全天"), exact=False)
        if all_day.count() > 0:
            try:
                box = host.locator("#isAllDay")
                checked = False
                if box.count() > 0:
                    checked = bool(box.first.is_checked())
                if not checked:
                    all_day.first.click(timeout=3000)
                    self.page.wait_for_timeout(200)
            except Exception:
                try:
                    all_day.first.click(timeout=2000)
                except Exception:
                    pass
        picker = host.locator(
            "div.ant-picker:has(#visitDateStr), .ant-form-item:has(#visitDateStr) .ant-picker"
        )
        target = picker.first if picker.count() > 0 else host.locator("#visitDateStr")
        assert target.count() > 0, "新建日程无预计跟进日期"
        target.first.click(timeout=5000)
        self.page.wait_for_timeout(400)
        today = date.today().isoformat()
        cell = self.page.locator(
            f".ant-picker-dropdown:not(.ant-picker-dropdown-hidden) "
            f"td.ant-picker-cell-in-view[title='{today}']"
        )
        if cell.count() == 0:
            self._pick_first_visible_day()
        else:
            cell.first.click(timeout=3000)
        self.page.wait_for_timeout(300)
        self._dismiss_select_dropdown()

    def _remind_time_dialog(self):
        return self.page.locator(
            ".ant-modal-wrap:not([style*='display: none']) .ant-modal"
        ).filter(has_text=re.compile(r"更改提醒时间"))

    def _pick_time_panel_value(self, col_index: int, value: int) -> None:
        """点 Ant TimePicker 某一列（0=时 1=分）的数值。"""
        label = f"{value:02d}"
        panel = self.page.locator(
            ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden) "
            ".ant-picker-time-panel, "
            ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden)"
        )
        cols = panel.locator(".ant-picker-time-panel-column")
        assert cols.count() > col_index, f"时间面板列不足: col={col_index} count={cols.count()}"
        col = cols.nth(col_index)
        cell = col.locator("li").filter(has_text=re.compile(rf"^{label}$"))
        if cell.count() == 0:
            cell = col.locator(
                f"li[data-value='{value}'], li[title='{label}'], "
                "li.ant-picker-time-panel-cell"
            ).filter(has_text=label)
        assert cell.count() > 0, f"时间面板无 {label}（第 {col_index} 列）"
        inner = cell.first.locator(".ant-picker-time-panel-cell-inner")
        node = inner.first if inner.count() > 0 else cell.first
        self._click_dropdown_option_node(node)
        self.page.wait_for_timeout(200)

    def _set_remind_time_after_now(self, host) -> None:
        """点「更改时间」打开「更改提醒时间」弹窗，把 09:00 改成当前之后再确定。"""
        link = host.locator("a, span, button").filter(has_text=re.compile(r"^更改时间$"))
        if link.count() == 0:
            link = host.get_by_text("更改时间", exact=True)
        if link.count() == 0:
            return
        link.first.click(timeout=5000)
        dialog = self._remind_time_dialog()
        try:
            dialog.first.wait_for(state="visible", timeout=8000)
        except PlaywrightTimeoutError as exc:
            raise AssertionError("未出现「更改提醒时间」弹窗") from exc

        now = datetime.now()
        if now.hour >= 23:
            hour, minute = 23, min(59, now.minute + 5)
        else:
            hour, minute = now.hour + 1, 0
        want = f"{hour:02d}:{minute:02d}"

        picker = dialog.locator(".ant-picker, .ant-picker-input, input")
        assert picker.count() > 0, "更改提醒时间弹窗无时间输入"
        picker.first.click(timeout=5000)
        self.page.wait_for_timeout(400)
        dropdown = self.page.locator(
            ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden)"
        )
        if dropdown.count() == 0:
            dialog.locator(".ant-picker-suffix, .anticon-clock-circle").first.click(
                timeout=3000
            )
            self.page.wait_for_timeout(400)
        self._pick_time_panel_value(0, hour)
        if self.page.locator(
            ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden) "
            ".ant-picker-time-panel-column"
        ).count() > 1:
            self._pick_time_panel_value(1, minute)
        picker_ok = self.page.locator(
            ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden) .ant-picker-ok button"
        )
        if picker_ok.count() > 0:
            picker_ok.last.click(timeout=3000)
            self.page.wait_for_timeout(200)

        shown = ""
        inp = dialog.locator("input").first
        try:
            shown = (inp.input_value() or "").strip()
        except Exception:
            shown = (dialog.inner_text() or "").replace("\n", " ")
        assert want[:2] in shown or want in shown, (
            f"提醒时间未改成 {want}，当前={shown!r}"
        )

        ok = dialog.locator("button.ant-btn-primary").filter(
            has_text=re.compile(r"确\s*定")
        )
        if ok.count() == 0:
            ok = dialog.locator("button").filter(has_text=re.compile(r"确\s*定"))
        assert ok.count() > 0, "更改提醒时间弹窗无确定"
        ok.last.click(timeout=5000)
        try:
            dialog.first.wait_for(state="hidden", timeout=8000)
        except PlaywrightTimeoutError as exc:
            raise AssertionError("更改提醒时间弹窗未关闭") from exc
        self.page.wait_for_timeout(200)
        try:
            host.locator("#scheduleName, .ant-modal-title").first.click(timeout=2000)
        except Exception:
            self._dismiss_select_dropdown()
        hint = (host.inner_text() or "").replace("\n", " ")
        assert "09:00" not in hint, f"提醒文案仍是 09:00: {hint[:180]!r}"
        print(f"[visit] 提醒时间已改为 {want}", flush=True)

    def _wait_list_idle(self) -> None:
        for _ in range(20):
            spin = self.page.locator(".ant-spin-spinning")
            try:
                if spin.count() == 0 or not spin.first.is_visible():
                    return
            except Exception:
                return
            self.page.wait_for_timeout(250)

    def pick_follow_target(self, root_selector: str, keyword: str, *, multi: bool = False) -> None:
        """跟进对象：必须键盘输入触发远程搜索，再点选项（禁止只 fill）。"""
        assert keyword, "跟进对象关键字不能为空"
        ant = self._ant_select_root(root_selector)
        shell = ant.locator(".ant-select-selector")
        (shell.first if shell.count() > 0 else ant).click(timeout=5000)
        self.page.wait_for_timeout(200)
        inp = ant.locator("input.ant-select-selection-search-input, input")
        if inp.count() == 0:
            inp = self.page.locator(f"{root_selector}")
        assert inp.count() > 0, f"跟进对象无搜索框: {root_selector}"
        try:
            inp.first.fill("")
            inp.first.press_sequentially(keyword, delay=60)
        except Exception:
            inp.first.fill(keyword)
        self.page.wait_for_timeout(1200)
        dropdown = self.page.locator(
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
        )
        option = self._dropdown_option_locator(dropdown)
        for _ in range(16):
            if option.count() > 0:
                break
            self.page.wait_for_timeout(200)
            option = self._dropdown_option_locator(dropdown)
        assert option.count() > 0, f"跟进对象搜索无结果: {keyword}"
        matched = dropdown.get_by_text(keyword, exact=False)
        if matched.count() > 0:
            self._click_dropdown_option_node(matched.first)
        else:
            self._pick_dropdown_option(dropdown.last, keyword)
        self.page.wait_for_timeout(300)
        if multi:
            self._dismiss_select_dropdown()
        shown = (ant.inner_text() or "").replace("\n", " ")
        assert keyword[:4] in shown or ant.locator(".ant-select-selection-item").count() > 0, (
            f"跟进对象未选中: keyword={keyword!r} shown={shown!r}"
        )

    def fill_create_form(
        self,
        *,
        name: str,
        customer_keyword: str,
        remark: str = "",
        follow_method: str = "线下拜访",
    ) -> None:
        host = self._form_host()
        host.locator("#scheduleName").first.fill(name)
        assert host.locator("#customerId").count() > 0, "新建日程无跟进对象 #customerId"
        self.pick_follow_target("#customerId", customer_keyword)
        self._dismiss_select_dropdown()
        method = host.locator("label, .ant-radio-wrapper, span").filter(
            has_text=re.compile(rf"^{re.escape(follow_method)}$")
        )
        if method.count() > 0:
            try:
                method.first.click(timeout=3000)
            except Exception:
                pass
        self._set_visit_date_today(host)
        self._set_remind_time_after_now(host)
        if remark and host.locator("#remark").count() > 0:
            host.locator("#remark").first.fill(remark)

    def _visible_modal_texts(self) -> list[str]:
        texts: list[str] = []
        wraps = self.page.locator(
            ".ant-modal-wrap, .ant-modal-confirm, .ant-popover"
        )
        for i in range(min(wraps.count(), 8)):
            w = wraps.nth(i)
            try:
                if not w.is_visible():
                    continue
                texts.append((w.inner_text() or "").replace("\n", " ").strip()[:180])
            except Exception:
                continue
        return texts

    def _confirm_wecom_unbound_prompt(self) -> bool:
        """未绑定企微时保存会出「无法收到企微通知，确认是否创建」，点确认继续。"""
        keys = ("尚未绑定", "企微通知", "确认是否创建", "未绑定企微", "无法收到企微")
        wraps = self.page.locator(
            ".ant-modal-wrap, .ant-modal-confirm, .ant-modal-root .ant-modal"
        )
        target = None
        for i in range(min(wraps.count(), 8)):
            w = wraps.nth(i)
            try:
                if not w.is_visible():
                    continue
                text = (w.inner_text() or "").replace("\n", " ")
            except Exception:
                continue
            if any(k in text for k in keys):
                target = w
                break
        if target is None:
            confirm = self.page.locator(".ant-modal-confirm:visible, .ant-modal-confirm-btns")
            if confirm.count() > 0:
                try:
                    if confirm.first.is_visible():
                        target = confirm.first
                except Exception:
                    pass
        if target is None:
            return False
        ok = target.locator("button.ant-btn-primary").filter(
            has_text=re.compile(r"确\s*认|确\s*定")
        )
        if ok.count() == 0:
            ok = target.locator("button").filter(has_text=re.compile(r"确\s*认|确\s*定"))
        if ok.count() == 0:
            ok = self.page.locator(
                ".ant-modal-confirm-btns button.ant-btn-primary, "
                ".ant-modal-confirm button.ant-btn-primary"
            ).filter(has_text=re.compile(r"确\s*认|确\s*定"))
        if ok.count() == 0:
            return False
        ok.last.click(timeout=5000)
        self.page.wait_for_timeout(400)
        print("[visit] 已确认未绑定企微仍创建", flush=True)
        return True

    def _is_schedule_save_response(self, resp) -> bool:
        url = (resp.url or "").lower()
        path = url.split("?")[0]
        if resp.request.method not in ("POST", "PUT"):
            return False
        if path.endswith("/page") or path.endswith("/page/") or "/page?" in url:
            return False
        return "visit/schedule" in path or "saveorupdate" in path

    def save_form(self) -> dict | None:
        self._dismiss_select_dropdown()
        leftover = self._remind_time_dialog()
        if leftover.count() > 0:
            try:
                if leftover.first.is_visible():
                    raise AssertionError("保存前「更改提醒时间」弹窗仍开着，未改完提醒时间")
            except AssertionError:
                raise
            except Exception:
                pass
        host = self._form_host()
        ok = host.get_by_role("button", name=re.compile(r"保\s*存"))
        if ok.count() == 0:
            ok = host.locator("button.ant-btn-primary").filter(
                has_text=re.compile(r"保\s*存")
            )
        if ok.count() == 0:
            ok = host.locator("button").filter(has_text=re.compile(r"保\s*存"))
        assert ok.count() > 0, "日程弹窗无保存按钮"

        captured: list[str] = []
        body: dict | None = None

        def _on_resp(resp) -> None:
            nonlocal body
            url = resp.url or ""
            if "visit" not in url.lower() and "schedule" not in url.lower():
                return
            captured.append(f"{resp.request.method} {url} {resp.status}")
            if self._is_schedule_save_response(resp):
                try:
                    body = resp.json()
                except Exception:
                    pass

        self.page.on("response", _on_resp)
        try:
            try:
                ok.last.click(timeout=8000)
            except PlaywrightTimeoutError:
                ok.last.click(force=True, timeout=5000)
            self.page.wait_for_timeout(400)
            self._confirm_wecom_unbound_prompt()
            for _ in range(24):
                self.page.wait_for_timeout(250)
                self._confirm_wecom_unbound_prompt()
                toast = self.page.locator(
                    ".ant-message-error, .ant-notification-notice-error"
                )
                msg = ""
                if toast.count() > 0:
                    try:
                        msg = (toast.first.inner_text() or "").strip()
                    except Exception:
                        msg = ""
                if "提醒时间" in msg or "不能早于" in msg:
                    self.page.remove_listener("response", _on_resp)
                    self._set_remind_time_after_now(host)
                    return self.save_form()
                form = host.locator("#scheduleName")
                try:
                    if form.count() == 0 or not form.first.is_visible():
                        break
                except Exception:
                    break
                if body is not None:
                    break
        finally:
            try:
                self.page.remove_listener("response", _on_resp)
            except Exception:
                pass

        self._wait_list_idle()
        form = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none']) #scheduleName"
        )
        still_open = False
        try:
            still_open = form.count() > 0 and form.first.is_visible()
        except Exception:
            still_open = False
        if still_open:
            toast = self.page.locator(
                ".ant-message-notice, .ant-notification-notice"
            )
            tmsg = ""
            if toast.count() > 0:
                try:
                    tmsg = (toast.first.inner_text() or "").strip()
                except Exception:
                    tmsg = ""
            raise AssertionError(
                f"保存后新建弹窗仍在 toast={tmsg!r} captured={captured} "
                f"body={body} modals={self._visible_modal_texts()!r}"
            )
        print(f"[visit] 保存完成 captured={captured} body={body}", flush=True)
        return body

    def cancel_form(self) -> None:
        host = self._form_host()
        cancel = host.locator("button").filter(has_text=re.compile(r"取\s*消"))
        if cancel.count() > 0:
            cancel.last.click(timeout=5000)
            self.page.wait_for_timeout(300)
            self._stay_on_form_if_discard_prompt()

    def open_edit_form(self, name: str) -> None:
        self._click_row_action(name, r"编\s*辑")
        host = self._form_host()
        try:
            host.locator("#scheduleName").first.wait_for(state="visible", timeout=8000)
        except PlaywrightTimeoutError as exc:
            raise AssertionError(f"编辑日程弹窗未打开: {name}") from exc

    def fill_remark(self, remark: str) -> None:
        host = self._form_host()
        assert host.locator("#remark").count() > 0, "日程表单无备注"
        host.locator("#remark").first.fill(remark)

    def delete_row(self, name: str) -> None:
        self._click_row_action(name, r"删\s*除")
        confirm = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none']), "
            ".ant-popconfirm:not(.ant-popover-hidden)"
        )
        ok = confirm.locator("button").filter(
            has_text=re.compile(r"确\s*定|确\s*认|删\s*除")
        )
        if ok.count() > 0:
            ok.last.click(timeout=8000)
        self.page.wait_for_timeout(1000)

    def bind_activity(self, name: str) -> None:
        """已过期/今日拜访：关联活动记录。"""
        self._click_row_action(name, r"关联活动记录")
        modal = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none'])"
        ).filter(has_text=re.compile(r"活动|关联"))
        assert modal.count() > 0, f"未出现关联活动弹窗: {name}"
        host = modal.first
        row = host.locator(".ant-table-tbody tr, .ant-list-item, .ant-radio-wrapper")
        picked = False
        if row.count() > 0:
            try:
                row.first.click(timeout=5000)
                picked = True
            except Exception:
                pass
        if not picked:
            radio = host.locator(".ant-radio-wrapper, input.ant-radio-input")
            if radio.count() > 0:
                radio.first.click(force=True, timeout=5000)
                picked = True
        assert picked or host.locator(".ant-empty").count() == 0, (
            f"关联弹窗无可选活动: {name}"
        )
        ok = host.locator("button.ant-btn-primary").filter(
            has_text=re.compile(r"确\s*定|确\s*认|关\s*联")
        )
        if ok.count() == 0:
            ok = host.locator("button").filter(has_text=re.compile(r"确\s*定|确\s*认|关\s*联"))
        assert ok.count() > 0, "关联弹窗无确定"
        ok.last.click(timeout=8000)
        self.page.wait_for_timeout(1200)

    def unbind_activity(self, name: str) -> None:
        self._click_row_action(name, r"解\s*绑")
        confirm = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none']), "
            ".ant-popconfirm:not(.ant-popover-hidden)"
        ).filter(has_text=re.compile(r"解绑|确认"))
        assert confirm.count() > 0, f"未出现解绑确认: {name}"
        text = (confirm.first.inner_text() or "").replace("\n", " ")
        assert "解绑" in text, f"解绑弹窗文案不符: {text!r}"
        ok = confirm.locator("button").filter(has_text=re.compile(r"确\s*定|确\s*认"))
        assert ok.count() > 0, "解绑确认无确定"
        ok.last.click(timeout=8000)
        self.page.wait_for_timeout(1200)

    def first_row_name_with_action(self, action: str, *, customer: str = "") -> str:
        """找带指定操作的第一行日程名称（第 2 列）。"""
        rows = self.page.locator(".ant-table-tbody tr")
        pat = re.compile(action)
        for i in range(min(rows.count(), 20)):
            row = rows.nth(i)
            text = (row.inner_text() or "").replace("\n", " ")
            if customer and customer not in text:
                continue
            btn = row.locator("button, a, span").filter(has_text=pat)
            if btn.count() == 0:
                continue
            cols = [c.strip() for c in re.split(r"\t+", text) if c.strip()]
            # 序号 + 日程名称
            name = cols[1] if len(cols) > 1 else ""
            if name:
                return name
        raise AssertionError(
            f"列表没有可「{action}」且对象含 {customer!r} 的日程"
        )
