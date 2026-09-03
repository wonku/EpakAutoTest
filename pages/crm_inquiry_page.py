from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from pages.crm_opportunity_page import CrmOpportunityPage


class CrmInquiryPage(CrmOpportunityPage):
    """客户详情发起内部询价单（对齐录制 inquiry_main）。"""

    def filter_customer_by_company(self, keyword: str) -> None:
        self.close_overlays()
        name_input = self.page.locator("#salesLeads_form_companyName")
        assert name_input.count() > 0, "未找到客户企业名称筛选项"
        name_input.fill(keyword)
        self.click_search()
        self.page.wait_for_timeout(1200)

    def open_customer_row(self, keyword: str) -> None:
        link = self.page.locator(".ant-table-tbody a").filter(has_text=keyword)
        if link.count() == 0:
            link = self.page.locator(".ant-table-tbody a").first
        assert link.count() > 0, f"客户列表未找到: {keyword}"
        link.first.click()
        self.page.wait_for_timeout(1500)

    def open_create_internal_inquiry(self) -> None:
        """客户详情点击「发起内部询价单」。"""
        pattern = re.compile(r"发起.*内部询价|新建.*询价|\+\s*发起")
        btn = self.page.locator("button").filter(has_text=pattern)
        if btn.count() == 0:
            btn = self.page.get_by_role("button", name=pattern)
        assert btn.count() > 0, "未找到发起内部询价单入口"
        btn.first.click()
        self.page.wait_for_timeout(1500)
        assert self.page.locator("#subs_0_name, #address").count() > 0, (
            "询价表单未打开"
        )

    def _fill_input(self, selector: str, value: str | int | float) -> None:
        loc = self.page.locator(selector)
        assert loc.count() > 0, f"未找到字段 {selector}"
        target = loc.first
        target.scroll_into_view_if_needed(timeout=3000)
        target.click(timeout=3000)
        target.fill("")
        target.fill(str(value))
        self.page.wait_for_timeout(200)

    def _pick_first_select_option(self, root_selector: str) -> None:
        if self.page.locator(root_selector).count() == 0:
            return
        dropdown = self._open_select_dropdown(root_selector)
        option = dropdown.locator(
            ".ant-select-item-option:not(.ant-select-item-option-disabled)"
        ).first
        if option.count() == 0:
            return
        option.click()
        self.page.wait_for_timeout(300)

    def _pick_cascader_path(self, root_selector: str, depth: int = 4) -> None:
        """品类等 Cascader：逐级点第一项。"""
        if self.page.locator(root_selector).count() == 0:
            return
        root = self.page.locator(root_selector).first
        # Cascader 常把 id 挂在 input 上
        shell = self.page.locator(
            f".ant-form-item:has({root_selector}) .ant-select, "
            f"div.ant-cascader:has({root_selector}), "
            f"div.ant-select:has({root_selector})"
        )
        target = shell.first if shell.count() > 0 else root
        target.click()
        self.page.wait_for_timeout(500)
        for _ in range(depth):
            menus = self.page.locator(
                ".ant-cascader-menus:visible .ant-cascader-menu, "
                ".ant-cascader-dropdown:not(.ant-cascader-dropdown-hidden) "
                ".ant-cascader-menu"
            )
            if menus.count() == 0:
                break
            item = menus.last.locator(
                ".ant-cascader-menu-item:not(.ant-cascader-menu-item-disabled)"
            ).first
            if item.count() == 0:
                break
            item.click()
            self.page.wait_for_timeout(350)

    def fill_region_if_needed(self) -> None:
        """地址省市区：尽量点开可见级联并选第一路径。"""
        candidates = [
            "#countryCode",
            "#provinceCode",
            "#cityCode",
            "#districtCode",
            "#streetCode",
            "input[id*='province']",
            "input[id*='city']",
        ]
        for sel in candidates:
            if self.page.locator(sel).count() > 0:
                try:
                    self._pick_first_select_option(sel)
                except Exception:
                    continue

        # 录制里是动态 rc_select；兜底按文案找省市区 Select
        for label in ("省", "市", "区", "街道"):
            item = self.page.locator(".ant-form-item").filter(has_text=label)
            if item.count() == 0:
                continue
            ant = item.first.locator(".ant-select").first
            if ant.count() == 0:
                continue
            try:
                ant.click()
                self.page.wait_for_timeout(300)
                opt = self.page.locator(
                    ".ant-select-dropdown:not(.ant-select-dropdown-hidden) "
                    ".ant-select-item-option"
                ).first
                if opt.count() > 0:
                    opt.click()
                    self.page.wait_for_timeout(250)
            except PlaywrightTimeoutError:
                continue

    def fill_inquiry_form(
        self,
        *,
        address: str,
        material_name: str,
        year_purchase_qty: int = 1000,
        qty: int = 10,
        weight: str = "10",
        length: str = "20",
        width: str = "30",
        height: str = "20",
        specification: str = "自动化规格",
        material: str = "材质要求自动化",
        inside: str = "内装物品自动化",
        usage: str = "使用要求自动化",
        test_condition: str = "测试条件自动化",
        remark: str = "自动化备注",
    ) -> None:
        self.fill_region_if_needed()
        self._fill_input("#address", address)
        self._fill_input("#subs_0_yearPurchaseQty", year_purchase_qty)
        self._pick_cascader_path("#subs_0_categoryFullId", depth=4)
        self._fill_input("#subs_0_weight", weight)
        self._fill_input("#subs_0_specificationModel", specification)
        self._fill_input("#subs_0_material", material)
        self._fill_input("#subs_0_length", length)
        self._fill_input("#subs_0_width", width)
        self._fill_input("#subs_0_name", material_name)
        self._fill_input("#subs_0_height", height)
        self._fill_input("#subs_0_inside", inside)
        self._pick_first_select_option("#subs_0_color")
        self._pick_first_select_option("#subs_0_storageEnvironment")
        self._fill_input("#subs_0_qty", qty)
        self._fill_input("#subs_0_testCondition", test_condition)
        self._fill_input("#subs_0_usageRequirement", usage)
        self._fill_input("#subs_0_remark", remark)

    def upload_attachment_if_present(self, file_path: str | Path | None = None) -> None:
        if not file_path:
            return
        path = Path(file_path)
        if not path.exists():
            return
        upload_input = self.page.locator("input[type='file']")
        if upload_input.count() == 0:
            # 先点上传按钮再找 input
            up_btn = self.page.locator("button").filter(has_text=re.compile(r"上传"))
            if up_btn.count() > 0:
                up_btn.first.click()
                self.page.wait_for_timeout(400)
            upload_input = self.page.locator("input[type='file']")
        if upload_input.count() == 0:
            return
        upload_input.first.set_input_files(str(path))
        self.page.wait_for_timeout(1200)

    def save_draft(self) -> None:
        btn = self.page.locator("button").filter(has_text=re.compile(r"保存草稿"))
        assert btn.count() > 0, "未找到保存草稿按钮"
        btn.last.click()
        self.page.wait_for_timeout(2000)

    def save_and_submit(self) -> None:
        btn = self.page.locator("button.ant-btn-primary").filter(
            has_text=re.compile(r"保存并提交|提\s*交")
        )
        if btn.count() == 0:
            btn = self.page.get_by_role(
                "button", name=re.compile(r"保存并提交|提\s*交")
            )
        assert btn.count() > 0, "未找到保存并提交按钮"
        btn.last.click()
        self.page.wait_for_timeout(2500)

    def open_view_detail(self) -> None:
        btn = self.page.locator("button").filter(has_text=re.compile(r"查看详情"))
        if btn.count() == 0:
            return
        btn.first.click()
        self.page.wait_for_timeout(1000)

    def click_edit(self) -> None:
        btn = self.page.locator("button").filter(has_text=re.compile(r"^编\s*辑$"))
        if btn.count() == 0:
            btn = self.page.get_by_role("button", name=re.compile(r"编\s*辑"))
        if btn.count() == 0:
            return
        btn.first.click()
        self.page.wait_for_timeout(1000)
