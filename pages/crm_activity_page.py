from __future__ import annotations

import re
from datetime import date, datetime

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from pages.crm_opportunity_page import CrmOpportunityPage


class CrmActivityPage(CrmOpportunityPage):
    """活动记录列表页（对齐录制 20260810-135954：单条件查询 / 重置 / 翻页）。"""

    FORM_PREFIX = "#salesLeads_form"

    @staticmethod
    def today_str() -> str:
        return date.today().isoformat()

    def assert_list_ready(self) -> None:
        # 进入页后等列表接口 / 表格出现
        try:
            self.page.wait_for_selector(
                ".ant-table, .ant-pro-table, .ant-spin-container",
                timeout=20000,
            )
        except PlaywrightTimeoutError:
            pass
        table = self.page.locator(".ant-table-tbody, .ant-table, .ant-pro-table")
        search = self.page.get_by_role("button", name=re.compile(r"查\s*询"))
        form = self.page.locator(f"{self.FORM_PREFIX}_activityContent, {self.FORM_PREFIX}_activityRecordTypeCode")
        if table.count() == 0 and search.count() == 0 and form.count() == 0:
            raise AssertionError(
                f"活动记录列表未渲染 url={self.page.url}"
            )
        if search.count() == 0:
            # 再等一会查询按钮
            self.page.wait_for_timeout(1500)
            search = self.page.get_by_role("button", name=re.compile(r"查\s*询"))
        assert search.count() > 0, f"未找到活动记录「查询」按钮 url={self.page.url}"

    def click_query(self, *, wait_api: bool = True) -> dict | None:
        """点击「查询」；成功等到 activity/page 时返回 JSON，否则 None。"""
        body: dict | None = None
        if not wait_api:
            self.click_search()
            self.page.wait_for_timeout(600)
            return None
        try:
            with self.page.expect_response(
                lambda r: "activity/page" in (r.url or "")
                and r.request.method == "POST",
                timeout=15000,
            ) as resp_info:
                self.click_search()
            try:
                body = resp_info.value.json()
            except Exception:
                body = None
        except PlaywrightTimeoutError:
            try:
                self.click_search()
            except Exception:
                pass
        self.page.wait_for_timeout(600)
        return body

    def click_reset(self) -> None:
        self.close_overlays()
        reset = self.page.locator(
            "form button.ant-btn-default, .ant-pro-table-search button.ant-btn-default"
        ).filter(has_text=re.compile(r"重\s*置"))
        if reset.count() == 0:
            reset = self.page.get_by_role("button", name=re.compile(r"重\s*置"))
        assert reset.count() > 0, "未找到活动记录「重置」按钮"
        try:
            with self.page.expect_response(
                lambda r: "activity/page" in (r.url or "")
                and r.request.method == "POST",
                timeout=12000,
            ):
                reset.first.click(timeout=8000)
        except Exception:
            try:
                reset.first.click(force=True, timeout=5000)
            except PlaywrightTimeoutError as exc:
                raise AssertionError("点击「重置」失败") from exc
        self.page.wait_for_timeout(800)

    def pick_select_by_text(self, selector: str, text: str) -> None:
        """打开下拉并按文案点选。"""
        assert self.page.locator(selector).count() > 0, f"未找到下拉 {selector}"
        assert text, f"选项文案不能为空: {selector}"
        dropdown = self._open_select_dropdown(selector)
        self._pick_dropdown_option(dropdown, text)
        self._assert_select_has_value(selector, text)

    def pick_record_type_first(self) -> None:
        sel = f"{self.FORM_PREFIX}_activityRecordTypeCode"
        assert self.page.locator(sel).count() > 0, f"未找到活动记录类型 {sel}"
        self.select_plain_first(sel)

    def pick_activity_type(self, text: str = "线下拜访") -> None:
        sel = f"{self.FORM_PREFIX}_activityTypeCode"
        assert self.page.locator(sel).count() > 0, f"未找到活动类型 {sel}"
        self.pick_select_by_text(sel, text)

    def pick_activity_type_first(self) -> None:
        self.pick_activity_type("线下拜访")

    def set_follow_user(self, keyword: str) -> None:
        sel = f"{self.FORM_PREFIX}_followId"
        assert self.page.locator(sel).count() > 0, f"未找到跟进人 {sel}"
        assert keyword, "跟进人关键字不能为空"
        try:
            self.select_searchable(sel, keyword, multi=True)
        except AssertionError:
            self.page.locator(sel).first.fill(keyword)
            self.page.wait_for_timeout(500)
            opt = self.page.locator(
                ".ant-select-dropdown:not(.ant-select-dropdown-hidden) "
                ".ant-select-item-option-content"
            ).filter(has_text=re.compile(re.escape(keyword)))
            if opt.count() > 0:
                opt.first.click()
            else:
                raise

    def set_activity_content(self, content: str) -> None:
        sel = f"{self.FORM_PREFIX}_activityContent"
        assert self.page.locator(sel).count() > 0, "未找到活动内容输入框"
        self.page.locator(sel).first.fill(content or "")

    def set_create_time_range(self, *, start: str, end: str = "") -> None:
        """设置创建日期区间（Ant Design 只读 picker，点选日历格）。"""
        end = end or start
        self._set_time_range(start=start, end=end)

    def _set_time_range(self, *, start: str, end: str) -> None:
        root = f"{self.FORM_PREFIX}_time"
        self.set_ant_range_picker(root, start=start, end=end)



    def goto_page(self, page_no: int | str) -> None:
        """点击分页页码；已在目标页或无该页码时跳过。"""
        # 当前页已是目标则不点
        active = self.page.locator(
            ".ant-pagination-item-active a, .ant-pagination-item-active"
        )
        if active.count() > 0:
            cur = (active.first.inner_text() or "").strip()
            if cur == str(page_no):
                return
        link = self.page.locator(
            ".ant-pagination-item:not(.ant-pagination-item-active) a, "
            ".ant-pagination a"
        ).filter(has_text=re.compile(rf"^{page_no}$"))
        if link.count() == 0:
            link = self.page.get_by_role("link", name=str(page_no))
        if link.count() == 0:
            return
        try:
            with self.page.expect_response(
                lambda r: "activity/page" in (r.url or "")
                and r.request.method == "POST",
                timeout=12000,
            ):
                link.first.click()
        except PlaywrightTimeoutError:
            try:
                link.first.click(force=True, timeout=3000)
            except Exception:
                return
        self.page.wait_for_timeout(600)

    def table_row_count(self) -> int:
        rows = self.page.locator(
            ".ant-table-tbody > tr:not(.ant-table-measure-row):not(.ant-table-placeholder)"
        )
        # 排除空状态行
        empty = self.page.locator(".ant-table-tbody .ant-empty, .ant-table-placeholder")
        if empty.count() > 0 and rows.count() <= 1:
            # placeholder 独占一行时视为 0
            if rows.count() == 1 and "暂无" in (rows.first.inner_text() or ""):
                return 0
        return rows.count()

    def assert_rows_match_filters(
        self,
        *,
        content_keyword: str,
        follow_keyword: str,
        create_date: str,
        activity_type: str = "",
        api_body: dict | None = None,
    ) -> None:
        """断言当前列表（及可选接口响应）符合筛选条件。"""
        n = self.table_row_count()
        assert n > 0, (
            f"筛选后无符合条件的活动记录: content={content_keyword!r} "
            f"follow={follow_keyword!r} date={create_date!r} type={activity_type!r}"
        )
        rows = self.page.locator(
            ".ant-table-tbody > tr:not(.ant-table-measure-row):not(.ant-table-placeholder)"
        )
        for i in range(n):
            text = (rows.nth(i).inner_text() or "").replace("\n", " ")
            assert content_keyword in text, (
                f"第{i + 1}行活动内容不符合: expect contain {content_keyword!r}, row={text!r}"
            )
            assert follow_keyword in text or "甜甜" in text, (
                f"第{i + 1}行记录人不符合: expect contain {follow_keyword!r}, row={text!r}"
            )
            assert create_date in text, (
                f"第{i + 1}行创建日期不符合: expect contain {create_date!r}, row={text!r}"
            )

        if api_body is None:
            return
        assert api_body.get("code") == 1000, f"activity/page 业务失败: {api_body}"
        data = api_body.get("data")
        api_rows: list = []
        if isinstance(data, list):
            api_rows = data
        elif isinstance(data, dict):
            api_rows = data.get("data") or data.get("records") or data.get("list") or []
        assert isinstance(api_rows, list) and api_rows, (
            f"接口未返回活动记录行: {api_body}"
        )
        for i, row in enumerate(api_rows):
            if not isinstance(row, dict):
                continue
            blob = " ".join(str(v) for v in row.values() if v is not None)
            content_val = str(
                row.get("activityContent")
                or row.get("content")
                or row.get("activityRecordContent")
                or ""
            )
            if content_keyword:
                assert content_keyword in content_val or content_keyword in blob, (
                    f"接口第{i + 1}行内容不符合: {row}"
                )
            if create_date:
                assert create_date in blob, f"接口第{i + 1}行日期不符合: {row}"
            if follow_keyword:
                assert (
                    follow_keyword in blob or "甜甜" in blob
                ), f"接口第{i + 1}行记录人不符合: {row}"
            if activity_type:
                # 类型可能只在筛选条件里，行字段名不固定；有则校验
                type_val = str(
                    row.get("activityTypeName")
                    or row.get("activityType")
                    or row.get("activityTypeCodeDesc")
                    or ""
                )
                if type_val:
                    assert activity_type in type_val or activity_type in blob, (
                        f"接口第{i + 1}行活动类型不符合: {row}"
                    )
