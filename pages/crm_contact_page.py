from __future__ import annotations

import re

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from pages.crm_opportunity_page import CrmOpportunityPage

# 录制/页面上联系人来源字段可能的 id
_SOURCE_SELECTORS = [
    "#salesLeads_form_sourceTypeCode",
    "#salesLeads_form_sourceType",
    "#salesLeads_form_source",
    "#salesLeads_form_sourceTypeList",
]


class CrmContactPage(CrmOpportunityPage):
    """联系人页（对齐录制 contact_main；复用 Ant Select 搜索选中能力）。"""

    def click_reset(self) -> None:
        self.close_overlays()
        reset = self.page.locator("button.ant-btn-default").filter(
            has_text=re.compile(r"重\s*置")
        )
        if reset.count() == 0:
            reset = self.page.get_by_role("button", name=re.compile(r"重\s*置"))
        assert reset.count() > 0, "未找到重置按钮"
        reset.first.click()
        self.page.wait_for_timeout(800)

    def _resolve_source_selector(self) -> str | None:
        for sel in _SOURCE_SELECTORS:
            if self.page.locator(sel).count() > 0:
                return sel
        return None

    def set_source_filter(self, text: str) -> None:
        """联系人来源（#salesLeads_form_sourceTypeCode，本地枚举多选）。"""
        if not text:
            return
        sel = "#salesLeads_form_sourceTypeCode"
        if self.page.locator(sel).count() == 0:
            for candidate in _SOURCE_SELECTORS:
                if self.page.locator(candidate).count() > 0:
                    sel = candidate
                    break
        assert self.page.locator(sel).count() > 0, "未找到联系人来源筛选项"
        dropdown = self._open_select_dropdown(sel)
        self._pick_dropdown_option(dropdown, text)
        self._dismiss_select_dropdown()
        self.page.wait_for_timeout(400)
        # 校验已选中
        ant = self._ant_select_root(sel)
        shown = (ant.inner_text() or "").replace("\n", " ")
        assert text[:2] in shown or ant.locator(".ant-select-selection-item").count() > 0, (
            f"来源未选中: expect={text} shown={shown!r}"
        )

    def set_register_status_filter(self, text: str) -> None:
        """注册状态（#salesLeads_form_registerStatus，本地枚举）。"""
        if not text:
            return
        sel = "#salesLeads_form_registerStatus"
        assert self.page.locator(sel).count() > 0, f"未找到注册状态筛选 {sel}"
        dropdown = self._open_select_dropdown(sel)
        self._pick_dropdown_option(dropdown, text)
        self._dismiss_select_dropdown()
        self.page.wait_for_timeout(400)
        ant = self._ant_select_root(sel)
        shown = (ant.inner_text() or "").replace("\n", " ")
        assert text[:2] in shown or ant.locator(".ant-select-selection-item").count() > 0, (
            f"注册状态未选中: expect={text} shown={shown!r}"
        )

    def set_create_time_range(self, *, start: str, end: str) -> None:
        """创建时间 RangePicker（录制：#salesLeads_form_time）。"""
        if not start and not end:
            return
        root = "#salesLeads_form_time"
        assert self.page.locator(root).count() > 0, f"未找到创建时间筛选 {root}"

        picker = self.page.locator(
            f"div.ant-picker:has({root}), "
            f".ant-form-item:has({root}) .ant-picker"
        )
        target = picker.first if picker.count() > 0 else self.page.locator(root).first
        target.click()
        self.page.wait_for_timeout(400)

        inputs = self.page.locator(
            f".ant-form-item:has({root}) .ant-picker-input input, "
            f"div.ant-picker:has({root}) input, "
            f"{root}"
        )
        # RangePicker 通常两个 input
        if inputs.count() >= 2:
            inputs.nth(0).click()
            inputs.nth(0).fill("")
            inputs.nth(0).fill(start)
            self.page.wait_for_timeout(200)
            inputs.nth(1).click()
            inputs.nth(1).fill("")
            inputs.nth(1).fill(end)
            self.page.keyboard.press("Enter")
            self.page.wait_for_timeout(400)
            # 收起日期面板，避免挡住后续 Select（禁止 body 空白点击）
            self._dismiss_select_dropdown()
            self.page.wait_for_timeout(300)
            return

        # 面板点选兜底：打开后选可见日期
        if start:
            inputs.first.fill(start)
            self.page.keyboard.press("Enter")
            self.page.wait_for_timeout(300)
        panel = self.page.locator(
            ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden)"
        )
        if panel.count() > 0:
            day = panel.locator(
                "td.ant-picker-cell-in-view:not(.ant-picker-cell-disabled)"
            )
            if day.count() > 0:
                day.first.click()
                self.page.wait_for_timeout(200)
                if day.count() > 0:
                    day.first.click()
                    self.page.wait_for_timeout(300)

    def filter_contacts(
        self,
        *,
        name: str = "",
        company_keyword: str = "",
        source_text: str = "",
        register_status_text: str = "",
        create_time_start: str = "",
        create_time_end: str = "",
    ) -> None:
        """列表筛选。首次全量筛选可带来源/创建时间/注册状态；按姓名复查时可不传后三项。"""
        self.close_overlays()
        name_input = self.page.locator("#salesLeads_form_name")
        assert name_input.count() > 0, "未找到联系人姓名筛选 #salesLeads_form_name"
        name_input.fill(name)

        company = self.page.locator("#salesLeads_form_companyName")
        if company_keyword and company.count() > 0:
            try:
                self.select_searchable(
                    "#salesLeads_form_companyName", company_keyword, multi=True
                )
            except Exception:
                company.fill(company_keyword)

        if source_text:
            self.set_source_filter(source_text)

        if create_time_start or create_time_end:
            self.set_create_time_range(
                start=create_time_start or create_time_end,
                end=create_time_end or create_time_start,
            )

        if register_status_text:
            self.set_register_status_filter(register_status_text)

        self.click_search()
        self.page.wait_for_timeout(1200)

    def open_create_form(self) -> None:
        self.close_overlays()
        btn = self.page.locator("button.ant-btn-primary").filter(
            has_text=re.compile(r"新建联系人")
        )
        if btn.count() == 0:
            btn = self.page.get_by_role("button", name=re.compile(r"新建联系人"))
        assert btn.count() > 0, "未找到「新建联系人」按钮"
        btn.first.click()
        self.page.wait_for_timeout(1000)
        try:
            self.page.locator("#name").first.wait_for(state="visible", timeout=15000)
        except PlaywrightTimeoutError as exc:
            raise AssertionError("新建联系人表单未打开（无 #name）") from exc

    def fill_create_basic(
        self,
        *,
        name: str,
        customer_keyword: str,
        phone: str,
        email: str,
        wx_code: str,
        whatsapp: str,
    ) -> None:
        self.page.locator("#name").fill(name)
        self.select_searchable("#customerId", customer_keyword)
        if self.page.locator("#sex").count() > 0:
            self.select_plain_first("#sex")
        self.page.locator("#phone").fill(phone)
        if self.page.locator("#email").count() > 0:
            self.page.locator("#email").fill(email)
        if self.page.locator("#wxCode").count() > 0:
            self.page.locator("#wxCode").fill(wx_code)
        if self.page.locator("#whatsapp").count() > 0:
            self.page.locator("#whatsapp").fill(whatsapp)

    def click_edit(self) -> None:
        self.click_toolbar_button(r"编\s*辑")
        self.page.wait_for_timeout(800)

    def fill_edit(self, *, name: str, remark: str) -> None:
        name_input = self.page.locator("#name")
        assert name_input.count() > 0, "编辑表单未找到姓名"
        name_input.fill(name)
        remark_input = self.page.locator("#remark")
        if remark_input.count() > 0:
            remark_input.fill(remark)
