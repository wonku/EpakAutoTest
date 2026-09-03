from __future__ import annotations

import re
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect

from pages.crm_opportunity_page import CrmOpportunityPage


class CrmCustomerPage(CrmOpportunityPage):
    """客户页：国内（工商下拉选企业）/ 海外新建。"""

    def close_overlays(self) -> None:
        """新建客户表单打开时禁止 Escape/关抽屉，否则会弹出「未保存将失效」。"""
        if self._is_customer_create_form_open():
            # 只收起下拉，不关表单
            self._dismiss_select_dropdown()
            return
        super().close_overlays()

    def _is_customer_create_form_open(self) -> bool:
        title = self.page.get_by_text(re.compile(r"新建客户"))
        company = self.page.locator("#companyName")
        try:
            return company.count() > 0 and company.first.is_visible() and title.count() > 0
        except Exception:
            return company.count() > 0

    def _dismiss_blocking_overlays(self) -> None:
        """Close tip/info modals that intercept clicks (keep create drawer open)."""
        for _ in range(3):
            wraps = self.page.locator(".ant-modal-wrap").filter(
                has=self.page.locator(".ant-modal-content")
            )
            # visible wraps only
            visible = []
            for i in range(min(wraps.count(), 5)):
                w = wraps.nth(i)
                try:
                    if w.is_visible():
                        visible.append(w)
                except Exception:
                    continue
            if not visible:
                break
            modal = visible[0]
            text_m = ""
            try:
                text_m = modal.inner_text() or ""
            except Exception:
                text_m = ""
            if re.search(r"未保存|是否取消", text_m):
                cancel_btn = modal.locator("button").filter(
                    has_text=re.compile(r"取\s*消")
                )
                if cancel_btn.count() > 0:
                    cancel_btn.first.click(force=True, timeout=3000)
                    self.page.wait_for_timeout(300)
                continue
            closer = modal.locator("button").filter(has_text=re.compile(r"知\s*道\s*了|确\s*定|关\s*闭|我知道了"))
            if closer.count() > 0:
                try:
                    closer.first.click(force=True, timeout=3000)
                    self.page.wait_for_timeout(300)
                    continue
                except Exception:
                    pass
            xbtn = modal.locator("button.ant-modal-close")
            if xbtn.count() > 0:
                try:
                    xbtn.first.click(force=True, timeout=2000)
                    self.page.wait_for_timeout(300)
                    continue
                except Exception:
                    pass
            try:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(200)
            except Exception:
                pass
            # if still blocking, force-hide pointer events on wrap (last resort)
            try:
                modal.evaluate(
                    "el => { el.style.display='none'; "
                    "const wrap=el.closest('.ant-modal-wrap'); "
                    "if (wrap) wrap.style.display='none'; }"
                )
            except Exception:
                pass
            break
        try:
            self._dismiss_select_dropdown()
        except Exception:
            pass

    def open_create_form(self, kind: str = "domestic") -> None:
        """打开新建表单。kind: domestic | overseas。

        必须点到对应二级项（新建国外客户 / 新建国内客户），禁止回退点「客户」误开国内。
        """
        if kind not in {"domestic", "overseas"}:
            raise AssertionError(f"不支持的客户类型: {kind}")

        self.close_overlays()
        company = self.page.locator("#companyName")
        if company.count() > 0 and company.first.is_visible():
            # 表单已开时也必须切到目标类型，避免沿用上次国内表单
            self._ensure_customer_kind(kind, required=True)
            return

        create_entry = self.page.locator("button").filter(
            has_text=re.compile(r"新\s*建")
        )
        if create_entry.count() == 0:
            create_entry = self.page.get_by_role("button", name=re.compile(r"新\s*建"))
        if create_entry.count() == 0:
            create_entry = self.page.locator(
                "button.ant-btn-primary, button.ant-btn-default, a.ant-btn"
            ).filter(has_text=re.compile(r"新\s*建"))
        # 列表未就绪时稍等
        if create_entry.count() == 0:
            end = time.time() + 15
            while time.time() < end and create_entry.count() == 0:
                self.page.wait_for_timeout(500)
                create_entry = self.page.locator("button, a").filter(
                    has_text=re.compile(r"新\s*建")
                )
        assert create_entry.count() > 0, (
            f"未找到「新建」客户入口，当前 url={self.page.url}"
        )

        last_error: Exception | None = None
        for attempt in range(2):
            create_entry.first.click()
            self.page.wait_for_timeout(500)
            try:
                self._click_create_kind_menu(kind)
            except AssertionError as exc:
                last_error = exc
                # 下拉没出来：再点一次新建
                self.page.wait_for_timeout(400)
                continue
            try:
                self.page.locator("#companyName").first.wait_for(
                    state="visible", timeout=12000
                )
                self._ensure_customer_kind(kind, required=True)
                return
            except PlaywrightTimeoutError as exc:
                last_error = exc
                self.page.wait_for_timeout(500)

        raise AssertionError(
            f"打开新建{('国外' if kind == 'overseas' else '国内')}客户表单后未出现 #companyName"
            f"（{last_error}）"
        ) from last_error

    def _create_kind_patterns(self, kind: str) -> list[re.Pattern[str]]:
        if kind == "overseas":
            # 页面文案为「新建国外客户」（兼容旧称「海外」）
            return [
                re.compile(r"新建\s*国外\s*客户"),
                re.compile(r"国外\s*客户"),
                re.compile(r"^国外$"),
                re.compile(r"新建\s*海外\s*客户"),
                re.compile(r"海外\s*客户"),
            ]
        return [
            re.compile(r"新建\s*国内\s*客户"),
            re.compile(r"国内\s*客户|境内\s*客户"),
            re.compile(r"^国内$|^境内$"),
        ]

    def _dropdown_menu_items(self):
        return self.page.locator(
            ".ant-dropdown:not(.ant-dropdown-hidden) .ant-dropdown-menu-item, "
            ".ant-dropdown:not(.ant-dropdown-hidden) li[role='menuitem'], "
            ".ant-dropdown:not(.ant-dropdown-hidden) li, "
            ".ant-dropdown:not(.ant-dropdown-hidden) button, "
            ".ant-popover:not(.ant-popover-hidden) .ant-dropdown-menu-item, "
            ".ant-popover:not(.ant-popover-hidden) li, "
            "[class*='dropdown']:not([class*='hidden']) .ant-dropdown-menu-item"
        )

    def _click_create_kind_menu(self, kind: str) -> None:
        """点击新建下的国内/国外菜单项；找不到对应项直接失败。"""
        label = "新建国外客户" if kind == "overseas" else "新建国内客户"
        foreign_re = re.compile(r"国外|海外")
        domestic_re = re.compile(r"国内|境内")

        deadline_ms = 8000
        waited = 0
        menu = self._dropdown_menu_items()
        while waited < deadline_ms and menu.count() == 0:
            self.page.wait_for_timeout(200)
            waited += 200
            menu = self._dropdown_menu_items()

        assert menu.count() > 0, (
            f"点击「新建」后未出现下拉菜单，无法选择「{label}」"
        )

        # 只在下拉菜单内匹配，禁止扫全页 text（易点到列表/文案误触）
        for pat in self._create_kind_patterns(kind):
            matched = menu.filter(has_text=pat)
            for i in range(min(matched.count(), 8)):
                item = matched.nth(i)
                try:
                    if not item.is_visible():
                        continue
                except Exception:
                    continue
                text = (item.inner_text() or "").strip().replace("\n", "")
                if kind == "overseas":
                    if domestic_re.search(text) or not foreign_re.search(text):
                        continue
                else:
                    if foreign_re.search(text) or not domestic_re.search(text):
                        continue
                try:
                    item.scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass
                try:
                    item.click(timeout=5000)
                except Exception:
                    item.evaluate("el => el.click()")
                self.page.wait_for_timeout(1000)
                return

        visible_texts = []
        for i in range(min(menu.count(), 10)):
            try:
                visible_texts.append((menu.nth(i).inner_text() or "").strip())
            except Exception:
                pass
        raise AssertionError(
            f"未找到「{label}」入口（禁止回退点国内客户）。"
            f"当前下拉可见项: {visible_texts}"
        )

    def _ensure_customer_kind(self, kind: str, *, required: bool = False) -> None:
        """表单内若有国内/国外切换则点选；required 时切不到就失败。"""
        foreign_re = re.compile(r"国外|海外")
        domestic_re = re.compile(r"国内|境内")
        if kind == "overseas":
            pats = [
                re.compile(r"新建\s*国外\s*客户|国外\s*客户|^国外$"),
                re.compile(r"新建\s*海外\s*客户|海外\s*客户|^海外$"),
            ]
        else:
            pats = [re.compile(r"新建\s*国内\s*客户|国内\s*客户|境内\s*客户|^国内$|^境内$")]

        for pat in pats:
            tab = self.page.get_by_role("radio", name=pat)
            if tab.count() == 0:
                tab = self.page.locator(
                    ".ant-radio-wrapper, label, button, .ant-tabs-tab, span"
                ).filter(has_text=pat)
            if tab.count() == 0:
                continue
            for i in range(min(tab.count(), 5)):
                el = tab.nth(i)
                text = (el.inner_text() or "").strip()
                if kind == "overseas" and (domestic_re.search(text) or not foreign_re.search(text)):
                    continue
                if kind == "domestic" and (foreign_re.search(text) or not domestic_re.search(text)):
                    continue
                try:
                    el.click(timeout=3000)
                    self.page.wait_for_timeout(500)
                    return
                except Exception:
                    continue

        if required and kind == "overseas":
            has_country = self.page.locator("#countryCode").count() > 0
            has_qichacha = self.page.get_by_text(re.compile(r"工商信息查询")).count() > 0
            if has_qichacha and not has_country:
                raise AssertionError(
                    "当前仍是国内客户表单（存在工商信息查询、无国家字段），"
                    "未成功进入「新建国外客户」"
                )
    def search_by_company_name(self, company_name: str) -> None:
        name_input = self.page.locator("#salesLeads_form_companyName")
        assert name_input.count() > 0, "列表缺少企业名称筛选 #salesLeads_form_companyName"
        name_input.fill(company_name)
        self.click_search()
        self.page.wait_for_timeout(1500)

    def open_row_by_company(self, company_name: str) -> None:
        link = self.page.get_by_role("link", name=company_name)
        if link.count() == 0:
            link = self.page.locator(".ant-table-tbody a").filter(has_text=company_name)
        assert link.count() > 0, f"列表未找到客户: {company_name}"
        try:
            with self.page.expect_response(
                lambda r: "customer/findById" in (r.url or "") and r.ok,
                timeout=20000,
            ):
                link.first.click()
        except PlaywrightTimeoutError:
            # 详情接口偶发未匹配到时仍继续等 UI
            pass
        self.page.wait_for_timeout(800)
        self.wait_customer_detail_loaded()

    def wait_customer_detail_loaded(self) -> None:
        """等待客户详情抽屉/面板出现（编辑按钮或企业名称）。"""
        deadline = time.time() + 15
        while time.time() < deadline:
            edit = self.page.locator("button").filter(has_text=re.compile(r"编\s*辑"))
            drawer = self.page.locator(".ant-drawer-open")
            try:
                if edit.count() > 0 and edit.first.is_visible():
                    return
                if drawer.count() > 0 and drawer.first.is_visible():
                    return
            except Exception:
                pass
            self.page.wait_for_timeout(300)
        raise AssertionError("打开客户后未出现详情（无编辑按钮/抽屉）")

    def click_edit(self) -> None:
        edit = self.page.locator("button").filter(has_text=re.compile(r"编\s*辑"))
        if edit.count() == 0:
            edit = self.page.get_by_role("button", name=re.compile(r"编\s*辑"))
        assert edit.count() > 0, "详情未找到编辑按钮"
        edit.first.click()
        self.page.wait_for_timeout(1000)
        try:
            self.page.locator("#companyName").first.wait_for(state="visible", timeout=12000)
        except PlaywrightTimeoutError as exc:
            raise AssertionError("点击编辑后未出现客户表单") from exc
        # 等详情回填：企业名非空（最长 ~8s）
        for _ in range(16):
            val = self._read_input_value("#companyName")
            if val:
                break
            self.page.wait_for_timeout(500)

    def read_company_name(self) -> str:
        loc = self.page.locator("#companyName")
        if loc.count() == 0:
            return ""
        try:
            val = loc.first.input_value(timeout=2000)
            if val:
                return val.strip()
        except Exception:
            pass
        return (loc.first.inner_text() or "").strip()

    def _detail_root(self):
        drawer = self.page.locator(".ant-drawer-open")
        if drawer.count() > 0:
            try:
                if drawer.first.is_visible():
                    return drawer.first
            except Exception:
                pass
        modal = self.page.locator(".ant-modal-wrap:not([style*='display: none'])").filter(
            has=self.page.locator(".ant-modal-content")
        )
        if modal.count() > 0:
            return modal.first
        return self.page.locator("body")

    def read_detail_panel_text(self) -> str:
        root = self._detail_root()
        try:
            return (root.inner_text(timeout=5000) or "").strip()
        except Exception:
            return ""

    def _read_input_value(self, selector: str) -> str:
        loc = self.page.locator(selector)
        if loc.count() == 0:
            return ""
        target = loc.first
        try:
            target.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        try:
            val = (target.input_value(timeout=2000) or "").strip()
            if val:
                return val
        except Exception:
            pass
        try:
            return (target.inner_text(timeout=2000) or "").strip()
        except Exception:
            return ""

    def _read_select_display(self, selector: str) -> str:
        root = self.page.locator(selector)
        if root.count() == 0:
            return ""
        item = root.first
        for sel in (
            ".ant-select-selection-item",
            ".ant-select-selection-overflow-item",
            ".ant-select-selection-placeholder",
        ):
            nodes = item.locator(sel)
            if nodes.count() == 0:
                continue
            texts = []
            for i in range(min(nodes.count(), 6)):
                t = (nodes.nth(i).inner_text() or "").strip()
                if t and t not in {"请选择", "请输入"}:
                    texts.append(t)
            if texts:
                return " / ".join(texts)
        try:
            return (item.inner_text(timeout=2000) or "").strip()
        except Exception:
            return ""

    def read_domestic_form_snapshot(self) -> dict[str, str]:
        """编辑态表单快照（用于与新建入参比对）。"""
        snap: dict[str, str] = {
            "company_name": self._read_input_value("#companyName"),
            "company_email": self._read_input_value("#email"),
            "company_phone": self._read_input_value("#companyPhone"),
            "company_people_num": self._read_input_value("#companyPeopleNum"),
            "annual_turnover": self._read_input_value("#annualTurnover"),
            "registered_capital": self._read_input_value("#registeredCapital"),
            "establishment_time": self._read_input_value("#establishmentTime"),
            "business_scope": self._read_input_value("#businessScope"),
            "standard_industry": self._read_input_value("#standardIndustry"),
            "office_address": self._read_input_value("#officeAddress"),
            "register_address": self._read_input_value("#registerAddress"),
            "contact_name": self._read_input_value(
                "#contactPersonSaveOrUpdateReq_name"
            ),
            "contact_phone": self._read_input_value(
                "#contactPersonSaveOrUpdateReq_phone"
            ),
            "contact_department": self._read_input_value(
                "#contactPersonSaveOrUpdateReq_department"
            )
            or self._read_input_value("#contactPersonSaveOrUpdateReq_dept")
            or self._read_input_value(
                "#contactPersonSaveOrUpdateReq_departmentName"
            ),
            "cooperation_supplier": self._read_input_value("#cooperationSupplier")
            or self._read_input_value("#cooperationSupplierName")
            or self._read_input_value("#cooperativeSupplier"),
            "sales_market": self._read_input_value("#salesMarket")
            or self._read_input_value("#salesMarketName")
            or self._read_select_display("#salesMarketCodes")
            or self._read_select_display("#targetSalesMarketCodes")
            or self._read_select_display("#predictMarketCode"),
            "year_purchase_qty": self._read_input_value("#yearPurchaseQty")
            or self._read_input_value("#annualPurchaseAmount")
            or self._read_input_value("#yearPurchaseAmount"),
            "remark": self._read_input_value("#remark"),
            "inquiry_keyword": self._read_select_display("#inquiryKeywordCode")
            or self._read_input_value("#inquiryKeyword"),
            "requirement_clarity": self._read_select_display(
                "#requirementClarityCode"
            )
            or self._read_select_display("#demandClarityCode"),
            "province": self._read_select_display("#provinceCode")
            or self._read_select_display("#province"),
            "city": self._read_select_display("#cityCode")
            or self._read_select_display("#city"),
            "district": self._read_input_value("#district")
            or self._read_select_display("#district"),
            "business_type": self._read_select_display("#businessTypeCode"),
            "business_sub_type": self._read_select_display("#businessSubTypeCode"),
            "industry": self._read_select_display("#industryCode"),
            "follow_user": self._read_select_display("#followUserId"),
            "contact_position": self._read_select_display(
                "#contactPersonSaveOrUpdateReq_positionCode"
            ),
        }
        return {k: v for k, v in snap.items() if v is not None}

    def discard_edit_and_close_detail(self) -> None:
        """退出编辑（不保存）并关闭详情。"""
        cancel = self.page.locator(
            ".ant-drawer-open button, .ant-modal-wrap:not([style*='display: none']) button"
        ).filter(has_text=re.compile(r"取\s*消"))
        if cancel.count() > 0:
            try:
                cancel.first.click(timeout=3000)
                self.page.wait_for_timeout(400)
            except Exception:
                pass
        leave = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none'])"
        ).filter(has_text=re.compile(r"未保存|是否取消|失效"))
        if leave.count() > 0:
            # 「未保存将失效」：确定=离开编辑；取消=留在表单
            confirm = leave.locator("button").filter(
                has_text=re.compile(r"确\s*定|离\s*开|不保存")
            )
            if confirm.count() > 0:
                try:
                    confirm.first.click(timeout=3000)
                    self.page.wait_for_timeout(300)
                except Exception:
                    pass
        self.close_drawer()

    def open_detail_tab(self, tab_name: str) -> None:
        """客户详情底部 Tab（活动记录/联系人/销售机会…）。"""
        root = self._detail_root()
        tab = root.locator(
            ".ant-tabs-tab, [role='tab'], .ant-tabs-nav-list > div"
        ).filter(has_text=re.compile(rf"^\s*{re.escape(tab_name)}\s*$"))
        if tab.count() == 0:
            tab = root.get_by_text(re.compile(rf"^\s*{re.escape(tab_name)}\s*$"))
        assert tab.count() > 0, f"详情未找到 Tab「{tab_name}」"
        try:
            tab.first.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        tab.first.click(timeout=5000)
        self.page.wait_for_timeout(1000)

    def read_contacts_tab_text(self) -> str:
        """打开「联系人」Tab 并返回表格区域文案。"""
        self.open_detail_tab("联系人")
        root = self._detail_root()
        # 等表格或空态出现
        for _ in range(10):
            body = root.locator(".ant-table-tbody, .ant-empty, .ant-spin-container")
            if body.count() > 0:
                break
            self.page.wait_for_timeout(300)
        table = root.locator(
            ".ant-tabs-tabpane-active .ant-table, "
            ".ant-tabs-content-holder .ant-table, "
            ".ant-table"
        )
        if table.count() > 0:
            try:
                return (table.first.inner_text(timeout=5000) or "").strip()
            except Exception:
                pass
        try:
            return (root.inner_text(timeout=5000) or "").strip()
        except Exception:
            return ""

    def assert_contact_in_detail_tab(
        self,
        *,
        contact_name: str,
        contact_phone: str = "",
    ) -> dict[str, str]:
        """在客户详情「联系人」Tab 断言新建联系人可见。"""
        text = self.read_contacts_tab_text()
        miss: list[str] = []
        name = (contact_name or "").strip()
        phone = (contact_phone or "").strip()
        if name and name not in text:
            miss.append(f"联系人姓名未在联系人Tab找到: {name}")
        if phone and phone not in text:
            miss.append(f"联系人手机未在联系人Tab找到: {phone}")
        if miss:
            raise AssertionError(
                "联系人Tab与新建不一致:\n- "
                + "\n- ".join(miss)
                + f"\n--- tab text ---\n{text[:800]}"
            )
        return {"contact_name": name, "contact_phone": phone, "tab_text": text[:500]}

    def assert_domestic_saved_matches(
        self,
        expected: dict[str, str],
        *,
        via_edit: bool = True,
    ) -> dict[str, str]:
        """断言详情与新建入参一致。

        - 主表/编辑态：企业基础信息、工商、询盘（不含联系人主表字段）
        - 联系人：详情底部「联系人」Tab 核对姓名/手机
        """
        panel_text = self.read_detail_panel_text()

        def _norm(s: str) -> str:
            return re.sub(r"\s+", "", (s or "").strip())

        def _contains(hay: str, needle: str) -> bool:
            h, n = _norm(hay), _norm(needle)
            if not n:
                return True
            return n in h or h in n

        mismatches: list[str] = []
        actual: dict[str, str] = {"panel_preview": panel_text[:500]}

        def _panel_has(exp: str) -> bool:
            if not exp:
                return True
            if exp in panel_text or _contains(panel_text, exp):
                return True
            if f"{exp}省" in panel_text or exp.rstrip("省") in panel_text:
                return True
            return False

        # 主详情：企业名必须可见；联系人不在主表
        company = (expected.get("company_name") or "").strip()
        if company and not _panel_has(company):
            mismatches.append(f"company_name: 详情主表未包含「{company}」")

        if via_edit:
            self.click_edit()
            try:
                form = self.read_domestic_form_snapshot()
                actual.update({f"form_{k}": v for k, v in form.items()})
                # 编辑态不校验联系人主表字段（保存后联系人在独立 Tab）
                field_map = (
                    ("company_name", "company_name", True),
                    ("company_email", "company_email", False),
                    ("company_people_num", "company_people_num", False),
                    ("annual_turnover", "annual_turnover", False),
                    ("office_address", "office_address", False),
                    ("cooperation_supplier", "cooperation_supplier", False),
                    ("sales_market", "sales_market", False),
                    ("year_purchase_qty", "year_purchase_qty", False),
                    ("remark", "remark", False),
                    ("inquiry_keyword", "inquiry_keyword", False),
                )
                for exp_key, act_key, required in field_map:
                    exp = (expected.get(exp_key) or "").strip()
                    if not exp:
                        continue
                    got = (form.get(act_key) or "").strip()
                    if not got:
                        if _panel_has(exp):
                            continue
                        if required:
                            mismatches.append(
                                f"{exp_key}: 编辑态为空，期望「{exp}」"
                            )
                        else:
                            mismatches.append(
                                f"{exp_key}: 详情/编辑态均未找到「{exp}」"
                            )
                        continue
                    if not _contains(got, exp):
                        mismatches.append(f"{exp_key}: 期望「{exp}」实际「{got}」")

                for exp_key, act_key in (
                    ("province", "province"),
                    ("city", "city"),
                    ("district", "district"),
                ):
                    exp = (expected.get(exp_key) or "").strip()
                    if not exp:
                        continue
                    got = (form.get(act_key) or "").strip()
                    if got and not _contains(got, exp):
                        mismatches.append(f"{exp_key}: 期望「{exp}」实际「{got}」")
                    elif not got and not _panel_has(exp):
                        mismatches.append(f"{exp_key}: 详情未找到「{exp}」")

                bt1 = (expected.get("business_type_l1") or "").strip()
                bt2 = (expected.get("business_type_l2") or "").strip()
                bt_got = " ".join(
                    [form.get("business_type") or "", form.get("business_sub_type") or ""]
                )
                if bt1 and bt_got and not _contains(bt_got, bt1):
                    mismatches.append(
                        f"business_type_l1: 期望「{bt1}」实际「{bt_got}」"
                    )
                elif bt1 and not bt_got and not _panel_has(bt1):
                    mismatches.append(f"business_type_l1: 详情未找到「{bt1}」")
                if bt2 and bt_got and not _contains(bt_got, bt2):
                    mismatches.append(
                        f"business_type_l2: 期望「{bt2}」实际「{bt_got}」"
                    )
            finally:
                # 退出编辑，回到详情以便切 Tab（不关抽屉）
                cancel = self.page.locator(
                    ".ant-drawer-open button, .ant-modal-wrap:not([style*='display: none']) button"
                ).filter(has_text=re.compile(r"取\s*消"))
                if cancel.count() > 0:
                    try:
                        cancel.first.click(timeout=3000)
                        self.page.wait_for_timeout(400)
                    except Exception:
                        pass
                leave = self.page.locator(
                    ".ant-modal-wrap:not([style*='display: none'])"
                ).filter(has_text=re.compile(r"未保存|是否取消|失效"))
                if leave.count() > 0:
                    confirm = leave.locator("button").filter(
                        has_text=re.compile(r"确\s*定|离\s*开|不保存")
                    )
                    if confirm.count() > 0:
                        try:
                            confirm.first.click(timeout=3000)
                            self.page.wait_for_timeout(400)
                        except Exception:
                            pass
        else:
            for key in (
                "company_name",
                "company_email",
                "office_address",
                "cooperation_supplier",
                "sales_market",
                "year_purchase_qty",
                "remark",
                "inquiry_keyword",
                "province",
                "city",
                "district",
                "business_type_l1",
                "business_type_l2",
                "industry_l1",
            ):
                exp = (expected.get(key) or "").strip()
                if exp and not _panel_has(exp):
                    mismatches.append(f"{key}: 详情主表未包含「{exp}」")

        # 联系人独立 Tab
        contact_name = (expected.get("contact_name") or "").strip()
        contact_phone = (expected.get("contact_phone") or "").strip()
        if contact_name or contact_phone:
            try:
                contact_actual = self.assert_contact_in_detail_tab(
                    contact_name=contact_name,
                    contact_phone=contact_phone,
                )
                actual["contact_tab"] = contact_actual.get("tab_text", "")
            except AssertionError as exc:
                mismatches.append(str(exc))

        self.close_drawer()

        if mismatches:
            raise AssertionError(
                "详情与新建内容不一致:\n- " + "\n- ".join(mismatches)
            )
        return actual

    def _fill_if_present(self, selector: str, value: str) -> None:
        loc = self.page.locator(selector)
        if loc.count() == 0 or not value:
            return
        loc.first.scroll_into_view_if_needed(timeout=3000)
        loc.first.fill(value)
        self.page.wait_for_timeout(200)

    def _select_if_present(
        self,
        selector: str,
        *,
        keyword: str = "",
        first: bool = False,
        multi: bool = False,
        soft: bool = True,
    ) -> None:
        if self.page.locator(selector).count() == 0:
            return
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                self._dismiss_select_dropdown()
                self.page.wait_for_timeout(200)
                if keyword:
                    self.select_searchable(selector, keyword, multi=multi)
                elif first:
                    self._select_plain_first_resilient(selector)
                self._assert_create_form_still_open(f"选择 {selector}")
                return
            except AssertionError:
                raise
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self.page.wait_for_timeout(400 * (attempt + 1))
        if soft:
            return
        raise AssertionError(f"选择失败: {selector}（{last_error}）") from last_error

    def _select_plain_first_resilient(self, root_selector: str) -> None:
        """兼容旧调用名；统一走基类 select_plain_first。"""
        self.select_plain_first(root_selector)
    def _visible_select_options(self):
        """当前可见的 Select / 远程搜索下拉项（兼容多种 DOM）。"""
        dropdowns = self.page.locator(
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
        )
        # 从后往前找：取真正带选项的那一层
        for i in range(dropdowns.count() - 1, -1, -1):
            d = dropdowns.nth(i)
            try:
                if not d.is_visible():
                    continue
            except Exception:
                continue
            opts = d.locator(
                ".ant-select-item-option:not(.ant-select-item-option-disabled), "
                ".ant-select-item:not(.ant-select-item-option-disabled), "
                "[role='option'], "
                ".rc-virtual-list-holder-inner > div"
            )
            if opts.count() > 0:
                return opts
        # 兜底：整页可见下拉里的可点行
        return self.page.locator(
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden) "
            ".ant-select-item-option, "
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden) [role='option'], "
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden) "
            ".rc-virtual-list-holder-inner > div"
        )

    def _wait_and_pick_option(
        self,
        *,
        prefer_texts: list[str] | None = None,
        keyword: str = "",
        timeout_ms: int = 12000,
        exclude_texts: list[str] | None = None,
    ) -> str:
        """等待下拉出现后点选：优先匹配 prefer_texts；可排除指定文案。返回选中文案。"""
        end_t = time.time() + timeout_ms / 1000
        opt = self._visible_select_options()
        while time.time() < end_t and opt.count() == 0:
            self.page.wait_for_timeout(250)
            opt = self._visible_select_options()
        assert opt.count() > 0, (
            f"搜索后未出现可点选下拉项 keyword={keyword!r} prefer={prefer_texts}"
        )

        excludes = exclude_texts or []
        target = None
        for text in prefer_texts or []:
            if not text:
                continue
            matched = opt.filter(has_text=text)
            for i in range(min(matched.count(), 8)):
                cand = matched.nth(i)
                t = (cand.inner_text() or "").strip()
                if t == "系统分配" or any(ex and ex == t for ex in excludes):
                    continue
                target = cand
                break
            if target is not None:
                break
        if target is None and keyword:
            matched = opt.filter(has_text=keyword)
            for i in range(min(matched.count(), 8)):
                cand = matched.nth(i)
                t = (cand.inner_text() or "").strip()
                if t == "系统分配":
                    continue
                target = cand
                break
        if target is None:
            for i in range(min(opt.count(), 10)):
                cand = opt.nth(i)
                t = (cand.inner_text() or "").strip()
                if not t or t == "系统分配":
                    continue
                target = cand
                break
        assert target is not None, (
            f"下拉无可选中项 keyword={keyword!r} prefer={prefer_texts} "
            f"options={[o.strip()[:40] for o in opt.all_inner_texts()[:8]]}"
        )

        label = (target.inner_text() or "").strip().replace("\n", " ")
        try:
            target.wait_for(state="visible", timeout=5000)
            target.click(timeout=8000)
        except PlaywrightTimeoutError:
            self.page.keyboard.press("ArrowDown")
            self.page.wait_for_timeout(200)
            self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(500)
        return label

    def _assign_follow_user(
        self,
        follow_user_keyword: str,
        *,
        prefer_text: str = "采购员",
        required: bool = True,
    ) -> None:
        """跟进人：必须输入关键字后点击返回的下拉值；禁止停留在「系统分配」。"""
        sel = "#followUserAssignType"
        if self.page.locator(sel).count() == 0:
            if required:
                raise AssertionError("跟进人字段不存在 (#followUserAssignType)")
            return

        keyword = (follow_user_keyword or "甜").strip() or "甜"
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                self._dismiss_select_dropdown()
                ant = self._ant_select_root(sel)
                ant.scroll_into_view_if_needed(timeout=5000)

                clearer = ant.locator(".ant-select-clear")
                if clearer.count() > 0:
                    try:
                        clearer.first.click(timeout=2000)
                        self.page.wait_for_timeout(300)
                    except Exception:
                        pass

                shell = ant.locator(".ant-select-selector")
                (shell.first if shell.count() else ant).click(timeout=5000)
                self.page.wait_for_timeout(400)

                search = ant.locator("input.ant-select-selection-search-input")
                if search.count() == 0:
                    search = self.page.locator(
                        f".ant-form-item:has({sel}) input.ant-select-selection-search-input"
                    )
                if search.count() == 0:
                    search = self.page.locator(sel)
                assert search.count() > 0, "跟进人下拉无搜索输入框"

                search.first.click(timeout=3000)
                # Ctrl+A 清空再输入，确保触发远程搜索
                search.first.press("Control+A")
                search.first.fill(keyword)
                self.page.wait_for_timeout(1800)

                dropdown = self.page.locator(
                    ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
                )
                try:
                    dropdown.last.wait_for(state="visible", timeout=10000)
                except PlaywrightTimeoutError as exc:
                    raise AssertionError(
                        f"输入「{keyword}」后跟进人下拉未出现"
                    ) from exc

                # 优先按可见文案点「…采购员」/「甜甜」
                picked = ""
                for pattern in (
                    re.compile(rf"指定到个人\s*/\s*.*{re.escape(prefer_text)}"),
                    re.compile(rf".*{re.escape(prefer_text)}.*"),
                    re.compile(r"指定到个人\s*/\s*甜甜"),
                    re.compile(r"甜甜"),
                    re.compile(re.escape(keyword)),
                ):
                    by_text = dropdown.last.get_by_text(pattern)
                    if by_text.count() == 0:
                        continue
                    # 跳过纯「系统分配」
                    for i in range(min(by_text.count(), 6)):
                        node = by_text.nth(i)
                        t = (node.inner_text() or "").strip().replace("\n", " ")
                        if not t or t == "系统分配":
                            continue
                        try:
                            node.click(timeout=8000)
                        except PlaywrightTimeoutError:
                            node.click(force=True, timeout=5000)
                        picked = t
                        self.page.wait_for_timeout(500)
                        break
                    if picked:
                        break

                if not picked:
                    picked = self._wait_and_pick_option(
                        prefer_texts=[
                            prefer_text,
                            "甜甜 (采购员)",
                            "甜甜",
                            "指定到个人 /",
                            keyword,
                        ],
                        keyword=keyword,
                        exclude_texts=["系统分配"],
                        timeout_ms=8000,
                    )

                self._dismiss_select_dropdown()

                shown = (ant.inner_text() or "").strip().replace("\n", " ")
                if shown.strip() == "系统分配" or re.fullmatch(r"\s*系统分配\s*", shown):
                    raise AssertionError(
                        f"跟进人仍是系统分配，未点中下拉。picked={picked!r} shown={shown!r}"
                    )
                if "系统分配" in shown and "甜" not in shown and "指定" not in shown:
                    raise AssertionError(
                        f"跟进人未切换出指定人员。picked={picked!r} shown={shown!r}"
                    )
                if not (
                    prefer_text in shown
                    or "甜甜" in shown
                    or "指定" in shown
                    or keyword in shown
                ):
                    raise AssertionError(
                        f"跟进人点选后文案不符合预期。picked={picked!r} shown={shown!r}"
                    )

                self._assert_create_form_still_open("跟进人")
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self._dismiss_select_dropdown()
                self.page.wait_for_timeout(400 * (attempt + 1))

        if required:
            raise AssertionError(
                f"跟进人选择失败（需输入「{keyword}」后点选下拉，不能停在系统分配）: {last_error}"
            ) from last_error

    def pick_company_via_qichacha(
        self,
        keyword: str,
        *,
        prefer_option: str = "",
    ) -> str:
        """国内企业名称：键入关键字 → 等待并点选目标下拉公司名 → 再工商查询/回填。

        与手工一致：必须先出现下拉并点选（如「白象食品股份有限公司」），再点工商查询。
        """
        assert keyword, "工商查询关键字不能为空"
        prefer = (prefer_option or "").strip()
        form_item = self.page.locator(".ant-form-item:has(#companyName)")
        assert self.page.locator("#companyName").count() > 0, "未找到企业名称 #companyName"
        if form_item.count() == 0:
            form_item = self.page.locator("div.ant-select:has(#companyName), #companyName")

        def _search_input():
            cands = [
                form_item.locator("input.ant-select-selection-search-input"),
                self.page.locator(
                    "div.ant-select:has(#companyName) input.ant-select-selection-search-input"
                ),
                form_item.locator("input.ant-input"),
                self.page.locator("#companyName"),
            ]
            for loc in cands:
                if loc.count() > 0:
                    return loc.first
            raise AssertionError("企业名称无可用输入框")

        def _read_typed() -> str:
            search = _search_input()
            try:
                return (search.input_value(timeout=1000) or "").strip()
            except Exception:
                try:
                    return (search.evaluate("el => el.value || ''") or "").strip()
                except Exception:
                    return ""


        def _focus_and_type(kw: str) -> None:
            self._dismiss_select_dropdown()
            try:
                form_item.first.scroll_into_view_if_needed(timeout=5000)
            except Exception:
                pass

            shell = form_item.locator(
                ".ant-select-selector, .ant-select, .ant-input-affix-wrapper"
            )
            try:
                if shell.count() > 0:
                    shell.first.click(timeout=5000)
                else:
                    self.page.locator("#companyName").first.click(timeout=5000)
            except Exception:
                self.page.locator("#companyName").first.click(force=True, timeout=5000)
            self.page.wait_for_timeout(350)

            search = _search_input()
            search.evaluate(
                """el => {
                    el.removeAttribute('readonly');
                    el.removeAttribute('unselectable');
                    el.style.opacity = '1';
                    el.focus();
                }"""
            )
            search.press("Control+A")
            search.press("Backspace")
            for _ in range(8):
                search.press("Backspace")
            self.page.wait_for_timeout(150)

            # 键入 + 监听可能的企业搜索接口
            def _do_type():
                try:
                    search.press_sequentially(kw, delay=100)
                except Exception:
                    search.type(kw, delay=100)

            try:
                with self.page.expect_response(
                    lambda r: r.request.method in {"GET", "POST"}
                    and r.status == 200
                    and any(
                        k in (r.url or "").lower()
                        for k in (
                            "qichacha",
                            "company",
                            "enterprise",
                            "fuzzy",
                            "suggest",
                            "search",
                            "keyword",
                        )
                    ),
                    timeout=8000,
                ):
                    _do_type()
            except Exception:
                _do_type()
            self.page.wait_for_timeout(1000)

            typed = _read_typed()
            if kw not in typed:
                search.click(force=True, timeout=3000)
                self.page.keyboard.press("Control+A")
                self.page.keyboard.press("Backspace")
                self.page.keyboard.type(kw, delay=120)
                self.page.wait_for_timeout(1000)
                typed = _read_typed()

            # React/Ant：原生 value setter 触发 onSearch（输入框有值但下拉不出时关键）
            search.evaluate(
                """(el, kw) => {
                    el.focus();
                    const setNative = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value'
                    ).set;
                    const fire = (val) => {
                        setNative.call(el, val);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    };
                    fire('');
                    let cur = '';
                    for (const ch of kw) {
                        cur += ch;
                        fire(cur);
                    }
                }""",
                kw,
            )
            self.page.wait_for_timeout(2000)
            typed = _read_typed()
            print(f"DBG_COMPANY: typed={typed!r}", flush=True)
            assert kw in typed, (
                f"公司名称输入未生效: expect contain {kw!r}, actual={typed!r}"
            )

        def _collect_options():
            panels = self.page.locator(
                ".ant-select-dropdown:not(.ant-select-dropdown-hidden), "
                ".ant-auto-complete-dropdown:not(.ant-select-dropdown-hidden)"
            )
            items: list[tuple] = []
            for i in range(panels.count() - 1, -1, -1):
                panel = panels.nth(i)
                try:
                    if not panel.is_visible():
                        continue
                except Exception:
                    continue
                opts = panel.locator(
                    ".ant-select-item-option:not(.ant-select-item-option-disabled), "
                    "[role='option']"
                )
                for j in range(min(opts.count(), 20)):
                    node = opts.nth(j)
                    shown = (
                        (node.get_attribute("title") or "").strip()
                        or (node.inner_text() or "").strip().replace("\n", " ")
                    )
                    if not shown or shown in {"展会", "系统分配", "未知"}:
                        continue
                    items.append((node, shown.split("\n")[0]))
                if items:
                    break
            return items

        def _wait_prefer_option():
            if not prefer:
                return None
            loc = self.page.locator(
                ".ant-select-dropdown:not(.ant-select-dropdown-hidden) "
                ".ant-select-item-option:not(.ant-select-item-option-disabled), "
                ".ant-auto-complete-dropdown:not(.ant-select-dropdown-hidden) "
                ".ant-select-item-option:not(.ant-select-item-option-disabled)"
            ).filter(has_text=prefer)
            try:
                loc.first.wait_for(state="visible", timeout=12000)
                title = (loc.first.get_attribute("title") or "").strip()
                text = title or (loc.first.inner_text() or "").strip().split("\n")[0]
                return loc.first, text
            except PlaywrightTimeoutError:
                return None

        def _pick_from_dropdown() -> str:
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    # 已回填目标公司则直接成功（手工/上次输入残留）
                    already = (self.read_company_name() or "").strip()
                    if prefer and prefer in already:
                        print(f"DBG_COMPANY: already selected={already!r}", flush=True)
                        return already
                    if keyword and already and keyword in already and len(already) > len(keyword) + 2:
                        print(f"DBG_COMPANY: already selected={already!r}", flush=True)
                        return already

                    _focus_and_type(keyword)

                    # 下拉层有时不是标准 ant-select-dropdown：直接按文案点
                    if prefer:
                        by_text = self.page.locator(
                            ".ant-select-item-option:visible, "
                            "[role='option']:visible, "
                            "div.ant-select-item:visible"
                        ).filter(has_text=prefer)
                        try:
                            if by_text.count() > 0 and by_text.first.is_visible():
                                self._click_dropdown_option_node(by_text.first)
                                self.page.wait_for_timeout(600)
                                selected = self.read_company_name() or prefer
                                if prefer in selected or prefer[:6] in selected:
                                    print(
                                        f"DBG_COMPANY: picked_by_text={selected!r}",
                                        flush=True,
                                    )
                                    return selected
                        except Exception:
                            pass
                        # 页面任意可见「白象食品…」
                        loose = self.page.get_by_text(prefer, exact=False)
                        for i in range(min(loose.count(), 8)):
                            node = loose.nth(i)
                            try:
                                if not node.is_visible():
                                    continue
                                self._click_dropdown_option_node(node)
                                self.page.wait_for_timeout(600)
                                selected = self.read_company_name() or prefer
                                if prefer in selected or len(selected) > len(keyword):
                                    print(
                                        f"DBG_COMPANY: picked_loose={selected!r}",
                                        flush=True,
                                    )
                                    return selected
                            except Exception:
                                continue

                    hit = _wait_prefer_option()
                    if hit is None:
                        items = _collect_options()
                        end_t = time.time() + 12
                        while time.time() < end_t and not items:
                            self.page.wait_for_timeout(300)
                            hit = _wait_prefer_option()
                            if hit is not None:
                                break
                            items = _collect_options()
                        if hit is None:
                            texts = [t for _, t in items]
                            # 输入后若选择器已回填全称，视为成功
                            filled = (self.read_company_name() or "").strip()
                            if prefer and prefer in filled:
                                return filled
                            if keyword in filled and len(filled) > len(keyword) + 2:
                                return filled
                            assert items, (
                                f"输入「{keyword}」后未出现公司下拉选项"
                                f"（输入框值={_read_typed()!r} filled={filled!r}）"
                            )
                            target = None
                            text = ""
                            if prefer:
                                for node, shown in items:
                                    if shown == prefer or prefer in shown:
                                        target, text = node, shown
                                        break
                                assert target is not None, (
                                    f"下拉未找到目标公司「{prefer}」，当前选项={texts[:12]!r}"
                                )
                            else:
                                for node, shown in items:
                                    if keyword in shown and len(shown) > len(keyword):
                                        target, text = node, shown
                                        break
                                assert target is not None, (
                                    f"下拉无含「{keyword}」的公司名，当前选项={texts[:12]!r}"
                                )
                            hit = (target, text)

                    node, text = hit
                    self._click_dropdown_option_node(node)
                    self.page.wait_for_timeout(800)
                    self._dismiss_select_dropdown()
                    selected = self.read_company_name() or text
                    assert selected and "请输入" not in selected, (
                        f"点选下拉后公司名称仍为空: {selected!r}"
                    )
                    if prefer:
                        assert prefer in selected or prefer[:6] in selected, (
                            f"点选后未回填目标公司: expect={prefer!r} shown={selected!r}"
                        )
                    print(f"DBG_COMPANY: selected={selected!r}", flush=True)
                    return selected if len(selected) >= len(text) else text
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    print(
                        f"DBG_COMPANY: attempt={attempt + 1} err={exc.__class__.__name__}: {exc}",
                        flush=True,
                    )
                    self._dismiss_select_dropdown()
                    self.page.wait_for_timeout(500 * (attempt + 1))
            raise AssertionError(
                f"未能从下拉选中公司名称 keyword={keyword!r} prefer={prefer!r}: {last_error}"
            ) from last_error

        selected = _pick_from_dropdown()

        query = self.page.get_by_role("link", name=re.compile(r"工商信息查询"))
        if query.count() == 0:
            query = self.page.locator("a, button, span").filter(
                has_text=re.compile(r"工商信息查询")
            )
        if query.count() == 0:
            return selected

        try:
            with self.page.expect_response(
                lambda r: ("qichacha" in (r.url or "") or "company" in (r.url or ""))
                and r.status == 200,
                timeout=20000,
            ):
                query.first.click(timeout=8000)
        except Exception:
            query.first.click(timeout=8000)
        self.page.wait_for_timeout(1200)

        result_row = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none']) .ant-table-tbody tr, "
            ".ant-modal-wrap:not([style*='display: none']) .ant-list-item, "
            ".ant-drawer-open .ant-table-tbody tr, "
            ".ant-popover:not(.ant-popover-hidden) .ant-table-tbody tr"
        )
        if result_row.count() > 0:
            try:
                needle = prefer or keyword
                matched = result_row.filter(has_text=needle)
                target = matched.first if matched.count() > 0 else result_row.first
                target.click(force=True)
                self.page.wait_for_timeout(400)
            except Exception:
                pass

        backfill = self.page.get_by_role("button", name=re.compile(r"回\s*填"))
        if backfill.count() == 0:
            backfill = self.page.locator("button").filter(
                has_text=re.compile(r"回\s*填")
            )
        if backfill.count() > 0 and backfill.first.is_visible():
            backfill.first.click(timeout=8000)
            self.page.wait_for_timeout(1200)
            end = time.time() + 10
            while time.time() < end:
                cur = self.read_company_name()
                if cur and cur != keyword and len(cur) > len(keyword):
                    selected = cur
                    break
                self.page.wait_for_timeout(300)

        self._dismiss_select_dropdown()
        final_name = self.read_company_name() or selected
        assert final_name and "请输入" not in final_name, (
            f"公司名称最终仍为空: {final_name!r}"
        )
        return final_name

    def _input_value(self, selector: str) -> str:
        loc = self.page.locator(selector)
        if loc.count() == 0:
            return ""
        try:
            val = loc.first.input_value(timeout=1500)
            if val is not None:
                return str(val).strip()
        except Exception:
            pass
        try:
            return (loc.first.inner_text() or "").strip()
        except Exception:
            return ""

    def _ensure_input(
        self,
        selector: str,
        value: str,
        *,
        required: bool = True,
        as_textarea: bool = False,
    ) -> None:
        """Fill input/textarea when empty; dismiss blocking modals first."""
        if self.page.locator(selector).count() == 0:
            if required:
                raise AssertionError(f"missing required field: {selector}")
            return
        current = self._input_value(selector)
        if current:
            return
        if not value:
            if required:
                raise AssertionError(f"required field empty, no default: {selector}")
            return
        self._dismiss_blocking_overlays()
        loc = self.page.locator(selector).first
        try:
            loc.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            pass
        try:
            loc.click(timeout=2000)
        except Exception:
            try:
                loc.click(force=True, timeout=2000)
            except Exception:
                pass
        try:
            loc.fill(str(value), force=True)
        except TypeError:
            loc.fill(str(value))
        except Exception:
            loc.evaluate(
                """(el, v) => {
                    const proto = el.tagName === 'TEXTAREA'
                        ? window.HTMLTextAreaElement.prototype
                        : window.HTMLInputElement.prototype;
                    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                    if (desc && desc.set) desc.set.call(el, v);
                    else el.value = v;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                str(value),
            )
        self.page.wait_for_timeout(200)
        after = self._input_value(selector)
        if required and not after:
            loc.evaluate(
                """(el, v) => {
                    const proto = el.tagName === 'TEXTAREA'
                        ? window.HTMLTextAreaElement.prototype
                        : window.HTMLInputElement.prototype;
                    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                    if (desc && desc.set) desc.set.call(el, v);
                    else el.value = v;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                str(value),
            )
            self.page.wait_for_timeout(200)
            after = self._input_value(selector)
        if required and not after:
            raise AssertionError(f"still empty after fill: {selector}")

    def _ensure_select(
        self,
        selector: str,
        *,
        keyword: str = "",
        first: bool = False,
        required: bool = True,
    ) -> None:
        if self.page.locator(selector).count() == 0:
            if required:
                raise AssertionError(f"缺少必填下拉: {selector}")
            return
        if self._select_has_value(selector):
            return
        if keyword:
            self._type_select_keyword(selector, keyword, required=required)
            return
        if first or required:
            self._select_required(selector, first=True)
            return

    def _fill_date(
        self, selector: str, date_str: str, *, required: bool = False
    ) -> None:
        """成立时间等 DatePicker：优先直接填 YYYY-MM-DD。"""
        if self.page.locator(selector).count() == 0:
            if required:
                raise AssertionError(f"缺少日期字段: {selector}")
            return
        current = self._input_value(selector)
        if current:
            return
        if not date_str:
            if required:
                raise AssertionError(f"日期值为空: {selector}")
            return
        picker = self.page.locator(
            f"div.ant-picker:has({selector}), "
            f".ant-form-item:has({selector}) .ant-picker"
        )
        target = picker.first if picker.count() > 0 else self.page.locator(selector).first
        target.scroll_into_view_if_needed(timeout=5000)
        target.click(timeout=5000)
        self.page.wait_for_timeout(300)
        inp = self.page.locator(
            f".ant-form-item:has({selector}) .ant-picker-input input, "
            f"div.ant-picker:has({selector}) input, "
            f"{selector}"
        )
        assert inp.count() > 0, f"日期输入框不存在: {selector}"
        inp.first.fill("")
        inp.first.fill(date_str)
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(300)
        self._dismiss_select_dropdown()
        self.page.wait_for_timeout(200)
        after = self._input_value(selector)
        if required and not after:
            raise AssertionError(f"日期未填入: {selector} expect={date_str}")


    def fill_domestic_region(
        self,
        *,
        province: str = "江苏",
        city: str = "苏州",
        district: str = "姑苏区",
    ) -> None:
        """省/市/区：本地枚举 Select（readonly）按文案点选；区可文本。强制校验非「请选择」。"""
        self._dismiss_blocking_overlays()
        self._dismiss_select_dropdown()

        def _resolve_select(*selectors: str, label_pat: str) -> str | None:
            for sel in selectors:
                if self.page.locator(sel).count() > 0:
                    return sel
            # 按 label 找 form-item 内 ant-select，取其内部带 id 的 input
            item = self.page.locator(".ant-form-item").filter(
                has=self.page.locator(
                    ".ant-form-item-label", has_text=re.compile(label_pat)
                )
            )
            if item.count() == 0:
                return None
            ant = item.first.locator(".ant-select").first
            if ant.count() == 0:
                return None
            # 给临时定位：用 form-item 内 search input 的 id
            inp = ant.locator("input.ant-select-selection-search-input, input[role='combobox']")
            if inp.count() > 0:
                eid = inp.first.get_attribute("id") or ""
                if eid:
                    return f"#{eid}"
            # 兜底：给该 select 加 data 标记不便，改为直接点选逻辑用 locator 对象
            return "__label__:" + label_pat

        def _assert_selected(selector: str) -> None:
            if selector.startswith("__label__:"):
                pat = selector.split(":", 1)[1]
                item = self.page.locator(".ant-form-item").filter(
                    has=self.page.locator(
                        ".ant-form-item-label", has_text=re.compile(pat)
                    )
                )
                ant = item.first.locator(".ant-select").first
                shown = (ant.inner_text() or "").strip().replace("\n", " ")
            else:
                shown = (
                    self._ant_select_root(selector).inner_text() or ""
                ).strip().replace("\n", " ")
            assert shown and "请选择" not in shown and "请输入" not in shown, (
                f"地区仍未选中: {selector} shown={shown!r}"
            )

        def _click_option_in_dropdown(keyword: str) -> bool:
            dropdown = self.page.locator(
                ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
            ).last
            try:
                dropdown.wait_for(state="visible", timeout=8000)
            except PlaywrightTimeoutError:
                return False
            option = dropdown.locator(
                ".ant-select-item-option:not(.ant-select-item-option-disabled)"
            )
            if option.count() == 0:
                return False
            kw = (keyword or "").strip()
            candidates = []
            if kw:
                candidates.append(kw)
                if not any(kw.endswith(s) for s in ("省", "市", "区", "州", "县")):
                    candidates.extend([f"{kw}省", f"{kw}市", f"{kw}区"])
            pick = None
            for text in candidates:
                exact = option.filter(has_text=re.compile(rf"^{re.escape(text)}$"))
                if exact.count() > 0:
                    pick = exact.first
                    break
                fuzzy = option.filter(has_text=text)
                if fuzzy.count() > 0:
                    pick = fuzzy.first
                    break
            if pick is None:
                pick = option.first
            try:
                pick.scroll_into_view_if_needed(timeout=3000)
            except Exception:
                pass
            try:
                pick.click(timeout=8000)
            except Exception:
                pick.evaluate("el => el.click()")
            self.page.wait_for_timeout(400)
            return True

        def _pick_region(
            *,
            selectors: tuple[str, ...],
            label_pat: str,
            keyword: str,
            required: bool,
        ) -> None:
            sel = _resolve_select(*selectors, label_pat=label_pat)
            if not sel:
                if required:
                    raise AssertionError(
                        f"缺少地区字段 selectors={selectors} label={label_pat}"
                    )
                return
            # 已有值则跳过
            if not sel.startswith("__label__:") and self._select_has_value(sel):
                _assert_selected(sel)
                return
            if sel.startswith("__label__:"):
                item = self.page.locator(".ant-form-item").filter(
                    has=self.page.locator(
                        ".ant-form-item-label", has_text=re.compile(label_pat)
                    )
                )
                if self._select_has_value_on_locator(item.first.locator(".ant-select").first):
                    return

            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    self._dismiss_blocking_overlays()
                    self._dismiss_select_dropdown()
                    self.page.wait_for_timeout(200)
                    if sel.startswith("__label__:"):
                        item = self.page.locator(".ant-form-item").filter(
                            has=self.page.locator(
                                ".ant-form-item-label", has_text=re.compile(label_pat)
                            )
                        )
                        shell = item.first.locator(".ant-select .ant-select-selector")
                        shell.first.scroll_into_view_if_needed(timeout=5000)
                        shell.first.click(timeout=5000)
                        self.page.wait_for_timeout(400)
                    else:
                        self._open_select_dropdown(sel)
                    if not _click_option_in_dropdown(keyword):
                        raise AssertionError(f"地区下拉无选项: {sel} kw={keyword}")
                    self._dismiss_select_dropdown()
                    _assert_selected(sel)
                    return
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    self.page.wait_for_timeout(300 * (attempt + 1))
            if required:
                raise AssertionError(
                    f"地区未选中: {sel} keyword={keyword!r} ({last_error})"
                ) from last_error

        _pick_region(
            selectors=("#provinceCode", "#province"),
            label_pat=r"省\s*/?\s*州|省份|省",
            keyword=province or "江苏",
            required=True,
        )
        _pick_region(
            selectors=("#cityCode", "#city"),
            label_pat=r"城\s*市|市",
            keyword=city or "苏州",
            required=True,
        )
        # 区：下拉或文本
        if self.page.locator("#districtCode").count() > 0:
            _pick_region(
                selectors=("#districtCode",),
                label_pat=r"^区$|区\s*/",
                keyword=district or "姑苏",
                required=True,
            )
        # 文本区
        for sel in ("#district", "#area", "#areaName"):
            if self.page.locator(sel).count() > 0:
                self._ensure_input(sel, district or "姑苏区", required=True)
                break
        else:
            # 按 label「区」找 input
            item = self.page.locator(".ant-form-item").filter(
                has=self.page.locator(
                    ".ant-form-item-label", has_text=re.compile(r"^区$")
                )
            )
            if item.count() > 0:
                inp = item.first.locator("input, textarea").first
                if inp.count() > 0:
                    cur = ""
                    try:
                        cur = (inp.input_value(timeout=1000) or "").strip()
                    except Exception:
                        cur = ""
                    if not cur:
                        inp.click(timeout=3000)
                        inp.fill(district or "姑苏区")
                        self.page.wait_for_timeout(200)

    def _select_has_value_on_locator(self, ant) -> bool:
        if ant is None or ant.count() == 0:
            return False
        items = ant.locator(
            ".ant-select-selection-item:not(.ant-select-selection-item-disabled)"
        )
        if items.count() > 0:
            for i in range(min(items.count(), 5)):
                text = (items.nth(i).inner_text() or "").strip()
                if text and "请选择" not in text:
                    return True
        shown = (ant.inner_text() or "").strip()
        return bool(shown) and "请选择" not in shown

    def _form_item_by_label(self, label: str):
        return self.page.locator(".ant-form-item").filter(
            has=self.page.locator(
                ".ant-form-item-label",
                has_text=re.compile(rf"^{re.escape(label)}$"),
            )
        )

    def _fill_field_by_label(
        self,
        label: str,
        value: str = "",
        *,
        as_select: bool | None = None,
        first_option: bool = False,
    ) -> bool:
        """按 label 填输入框或下拉。as_select=None 时自动判断。"""
        item = self._form_item_by_label(label)
        if item.count() == 0:
            # 宽松匹配（label 可能带空格/冒号）
            item = self.page.locator(".ant-form-item").filter(
                has=self.page.locator(
                    ".ant-form-item-label",
                    has_text=re.compile(re.escape(label)),
                )
            )
        if item.count() == 0:
            return False
        root = item.first
        try:
            root.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass

        ant = root.locator(".ant-select, .ant-cascader").first
        has_select = ant.count() > 0
        use_select = has_select if as_select is None else (as_select and has_select)

        if use_select:
            shown = (ant.inner_text() or "").strip()
            if shown and not re.search(r"请选择|请输入", shown) and not first_option and not value:
                return True
            try:
                ant.click(timeout=5000)
                self.page.wait_for_timeout(350)
                dropdown = self.page.locator(
                    ".ant-select-dropdown:not(.ant-select-dropdown-hidden), "
                    ".ant-cascader-dropdown:not(.ant-cascader-dropdown-hidden)"
                ).last
                opts = dropdown.locator(
                    ".ant-select-item-option:visible:not(.ant-select-item-option-disabled), "
                    ".ant-cascader-menu-item:visible, "
                    "[role='option']:visible"
                )
                if value:
                    hit = opts.filter(has_text=re.compile(re.escape(value)))
                    if hit.count() > 0:
                        hit.first.click(timeout=5000)
                        self.page.wait_for_timeout(250)
                        self._dismiss_select_dropdown()
                        return True
                    # 远程搜索
                    search = dropdown.locator("input").first
                    if search.count() == 0:
                        search = ant.locator("input").first
                    if search.count() > 0:
                        search.fill(value)
                        self.page.wait_for_timeout(600)
                        opts = dropdown.locator(
                            ".ant-select-item-option:visible:not(.ant-select-item-option-disabled), "
                            "[role='option']:visible"
                        )
                        hit = opts.filter(has_text=re.compile(re.escape(value)))
                        if hit.count() > 0:
                            hit.first.click(timeout=5000)
                            self.page.wait_for_timeout(250)
                            self._dismiss_select_dropdown()
                            return True
                if opts.count() > 0:
                    opts.first.click(timeout=5000)
                    self.page.wait_for_timeout(250)
                    self._dismiss_select_dropdown()
                    return True
            except Exception:
                self._dismiss_select_dropdown()
                return False
            return False

        if not value:
            return False
        inp = root.locator("textarea, input:not([type='hidden'])").first
        if inp.count() == 0:
            return False
        try:
            cur = (inp.input_value(timeout=1000) or "").strip()
        except Exception:
            cur = ""
        if cur and not first_option:
            return True
        try:
            inp.click(timeout=3000)
            inp.fill(str(value))
            self.page.wait_for_timeout(200)
            return True
        except Exception:
            return False

    def fill_cooperation_supplier(self, value: str = "自动化合作供应商") -> None:
        """非必填：合作供应商。"""
        if not value:
            return
        for sel in (
            "#cooperationSupplier",
            "#cooperativeSupplier",
            "#partnerSupplier",
            "#cooperationSupplierName",
        ):
            if self.page.locator(sel).count() > 0:
                self._ensure_input(sel, value, required=False)
                return
        item = self._form_item_by_label("合作供应商")
        if item.count() == 0:
            return
        inp = item.first.locator("input, textarea").first
        if inp.count() == 0:
            return
        try:
            cur = (inp.input_value(timeout=1000) or "").strip()
        except Exception:
            cur = ""
        if cur:
            return
        inp.click(timeout=3000)
        inp.fill(value)
        self.page.wait_for_timeout(200)

    def fill_sales_market(self, value: str = "") -> None:
        """国内销售市场：省份枚举下拉（全国/上海/北京/江苏省…），不是国家。"""
        # 候选：配置值 → 去「省」后缀 → 加「省」→ 直辖市/兜底
        raw = (value or "").strip()
        candidates: list[str] = []
        if raw:
            candidates.append(raw)
            if raw.endswith("省"):
                candidates.append(raw[:-1])
            elif raw not in {"全国", "上海", "北京", "天津", "重庆"} and not raw.endswith(
                ("市", "区", "自治区")
            ):
                candidates.append(f"{raw}省")
        for fb in ("江苏省", "江苏", "上海", "北京", "全国"):
            if fb not in candidates:
                candidates.append(fb)

        selectors = (
            "#salesMarketCode",
            "#salesMarketCodes",
            "#salesMarket",
            "#targetSalesMarketCodes",
            "#predictMarketCode",
            "#predictMarket",
        )

        def _pick_from_open_dropdown(preferred: list[str]) -> bool:
            dropdown = self.page.locator(
                ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
            ).last
            opts = dropdown.locator(
                ".ant-select-item-option:visible:not(.ant-select-item-option-disabled), "
                "[role='option']:visible"
            )
            try:
                opts.first.wait_for(state="visible", timeout=5000)
            except PlaywrightTimeoutError:
                return False
            for kw in preferred:
                # 精确优先，再包含匹配（河北 vs 河北省）
                exact = opts.filter(has_text=re.compile(rf"^{re.escape(kw)}$"))
                if exact.count() > 0:
                    exact.first.click(timeout=5000)
                    self.page.wait_for_timeout(250)
                    self._dismiss_select_dropdown()
                    return True
                soft = opts.filter(has_text=re.compile(re.escape(kw)))
                if soft.count() > 0:
                    soft.first.click(timeout=5000)
                    self.page.wait_for_timeout(250)
                    self._dismiss_select_dropdown()
                    return True
            # 兜底第一项（通常是「全国」）
            if opts.count() > 0:
                opts.first.click(timeout=5000)
                self.page.wait_for_timeout(250)
                self._dismiss_select_dropdown()
                return True
            return False

        for sel in selectors:
            if self.page.locator(sel).count() == 0:
                continue
            # 已有选中值则跳过
            if self._select_has_value(sel):
                return
            try:
                self._dismiss_select_dropdown()
                self._open_select_dropdown(sel)
                if _pick_from_open_dropdown(candidates):
                    return
            except Exception:
                self._dismiss_select_dropdown()
                continue

        # 无稳定 id：按 label「销售市场」打开下拉
        item = self._form_item_by_label("销售市场")
        if item.count() == 0:
            item = self.page.locator(".ant-form-item").filter(
                has=self.page.locator(
                    ".ant-form-item-label", has_text=re.compile(r"销售市场")
                )
            )
        if item.count() == 0:
            return
        ant = item.first.locator(".ant-select").first
        if ant.count() == 0:
            return
        shown = (ant.inner_text() or "").strip()
        if shown and not re.search(r"请选择|请输入", shown):
            return
        try:
            ant.click(timeout=5000)
            self.page.wait_for_timeout(350)
            _pick_from_open_dropdown(candidates)
        except Exception:
            self._dismiss_select_dropdown()

    def fill_inquiry_extra_fields(
        self,
        *,
        inquiry_keyword: str = "",
        year_purchase_qty: str = "100",
        requirement_clarity: str = "",
        remark: str = "自动化备注",
    ) -> None:
        """询盘信息：询盘关键词 / 年采购量 / 需求明确度 / 备注。"""
        # 询盘关键词（枚举下拉优先）
        filled_kw = False
        for sel in (
            "#inquiryKeywordCode",
            "#inquiryKeyword",
            "#inquiryKeywords",
            "#inquiryKeywordCodes",
        ):
            if self.page.locator(sel).count() == 0:
                continue
            if "Code" in sel:
                if inquiry_keyword:
                    try:
                        self._ensure_select(sel, keyword=inquiry_keyword, required=False)
                    except TypeError:
                        self._ensure_select(sel, first=True, required=False)
                    except Exception:
                        self._ensure_select(sel, first=True, required=False)
                else:
                    self._ensure_select(sel, first=True, required=False)
            elif inquiry_keyword:
                self._ensure_input(sel, inquiry_keyword, required=False)
            filled_kw = True
            break
        if not filled_kw:
            self._fill_field_by_label(
                "询盘关键词",
                inquiry_keyword or "",
                first_option=not inquiry_keyword,
            )

        # 年采购量
        filled_qty = False
        for sel in (
            "#yearPurchaseQty",
            "#annualPurchaseAmount",
            "#yearPurchaseAmount",
            "#annualPurchaseQty",
        ):
            if self.page.locator(sel).count() == 0:
                continue
            if year_purchase_qty:
                self._ensure_input(sel, year_purchase_qty, required=False)
            filled_qty = True
            break
        if not filled_qty and year_purchase_qty:
            self._fill_field_by_label("年采购量", year_purchase_qty)
        for unit_sel in (
            "#yearPurchaseQtyUnitCode",
            "#annualPurchaseUnitCode",
            "#yearPurchaseUnitCode",
        ):
            if self.page.locator(unit_sel).count() > 0:
                self._ensure_select(unit_sel, first=True, required=False)
                break

        # 需求明确度
        filled_clarity = False
        for sel in (
            "#requirementClarityCode",
            "#demandClarityCode",
            "#requirementClearCode",
            "#needClarityCode",
        ):
            if self.page.locator(sel).count() == 0:
                continue
            if requirement_clarity:
                try:
                    self._ensure_select(sel, keyword=requirement_clarity, required=False)
                except Exception:
                    self._ensure_select(sel, first=True, required=False)
            else:
                self._ensure_select(sel, first=True, required=False)
            filled_clarity = True
            break
        if not filled_clarity:
            self._fill_field_by_label(
                "需求明确度",
                requirement_clarity or "",
                as_select=True,
                first_option=not requirement_clarity,
            )

        # 备注
        if remark:
            if self.page.locator("#remark").count() > 0:
                self._ensure_input("#remark", remark, required=False, as_textarea=True)
            else:
                self._fill_field_by_label("备注", remark)

    def fill_contact_department(self, value: str = "采购部") -> None:
        """联系人部门。"""
        if not value:
            return
        for sel in (
            "#contactPersonSaveOrUpdateReq_department",
            "#contactPersonSaveOrUpdateReq_dept",
            "#contactPersonSaveOrUpdateReq_departmentName",
            "#contactPersonSaveOrUpdateReq_departmentCode",
        ):
            if self.page.locator(sel).count() == 0:
                continue
            if sel.endswith("Code"):
                try:
                    self._ensure_select(sel, keyword=value, required=False)
                except Exception:
                    self._ensure_select(sel, first=True, required=False)
            else:
                self._ensure_input(sel, value, required=False)
            return
        self._fill_field_by_label("联系人部门", value)

    def fill_predict_market(self, value: str = "") -> None:
        """兼容旧调用：转销售市场。"""
        self.fill_sales_market(value)

    def fill_create_domestic_basic(
        self,
        *,
        company_keyword: str,
        contact_name: str,
        contact_phone: str,
        follow_user_keyword: str,
        annual_turnover: str = "1000",
        company_email: str = "",
        contact_position: str = "采购员",
        contact_department: str = "采购部",
        business_type_l1: str = "终端客户",
        business_type_l2: str = "品牌方",
        industry_l1: str = "食品行业",
        industry_l2: str = "",
        company_people_num: str = "100",
        company_phone: str = "0512-88888888",
        registered_capital: str = "1000",
        establishment_time: str = "2020-01-01",
        business_scope: str = "自动化经营范围（测试）",
        standard_industry: str = "商贸零售",
        province: str = "江苏",
        city: str = "苏州",
        district: str = "姑苏区",
        office_address: str = "自动化办公地址",
        register_address: str = "",
        cooperation_supplier: str = "自动化合作供应商",
        sales_market: str = "",
        predict_market: str = "",
        inquiry_keyword: str = "",
        year_purchase_qty: str = "100",
        requirement_clarity: str = "",
        remark: str = "自动化备注",
        attachment: Path | None = None,
    ) -> str:
        """国内客户：工商选企业后强制补齐红星必填（含经营类型/行业二层）。"""
        print("DBG_DOMESTIC: qichacha", flush=True)
        company_name = self.pick_company_via_qichacha(company_keyword)
        print("DBG_DOMESTIC: company", company_name, flush=True)

        self._assign_follow_user(
            follow_user_keyword, prefer_text="采购员", required=True
        )

        # 经营类型：一级 → 二级（禁止软跳过）
        print("DBG_DOMESTIC: business_type", flush=True)
        self.select_business_type_cascade(
            level1=business_type_l1, level2=business_type_l2
        )
        print("DBG_DOMESTIC: business_type done", flush=True)

        # 行业地位 / 客户级别 / 客户等级
        self._ensure_select("#industryStatusCode", first=True, required=True)
        self._ensure_select("#customerGradeCode", first=True, required=True)
        if self.page.locator("#customerLevelCode").count() > 0:
            self._ensure_select("#customerLevelCode", first=True, required=False)

        # 行业：一级（食品行业）→ 二级（配置项或右侧第一可见子项）
        print("DBG_DOMESTIC: industry", flush=True)
        self.select_industry_cascade(
            level1=industry_l1 or "食品行业",
            level2=industry_l2 or "",
        )

        if company_email:
            self._ensure_input("#email", company_email, required=False)

        # 联系人
        self._fill_required("#contactPersonSaveOrUpdateReq_name", contact_name)
        if self.page.locator("#contactPersonSaveOrUpdateReq_phone").count() > 0:
            self._fill_required(
                "#contactPersonSaveOrUpdateReq_phone", contact_phone
            )
        if self.page.locator("#contactPersonSaveOrUpdateReq_positionCode").count() > 0:
            self.select_contact_position(contact_position)
        self.fill_contact_department(contact_department)

        # 人数 / 年营业额 / 公司电话 / 注册资金 / 成立时间
        self._ensure_input("#companyPeopleNum", company_people_num, required=True)
        self._ensure_input("#annualTurnover", annual_turnover, required=True)
        self._ensure_input("#companyPhone", company_phone, required=False)
        if company_email:
            self._ensure_input("#email", company_email, required=False)

        # 非必填也维护：合作供应商、销售市场、询盘信息
        self.fill_cooperation_supplier(cooperation_supplier)
        self.fill_sales_market(sales_market or predict_market)
        self.fill_inquiry_extra_fields(
            inquiry_keyword=inquiry_keyword,
            year_purchase_qty=year_purchase_qty,
            requirement_clarity=requirement_clarity,
            remark=remark,
        )
        self._ensure_input("#registeredCapital", registered_capital, required=False)
        if self.page.locator("#registeredCapitalUnitCode").count() > 0:
            self._ensure_select(
                "#registeredCapitalUnitCode", first=True, required=False
            )
        self._fill_date(
            "#establishmentTime", establishment_time, required=False
        )

        # 经营范围 / 标准行业 / 企业性质 / 地址
        self._dismiss_blocking_overlays()
        self._ensure_input(
            "#businessScope", business_scope, required=True, as_textarea=True
        )
        self._ensure_input(
            "#standardIndustry", standard_industry, required=False, as_textarea=True
        )
        if self.page.locator("#enterpriseNatureCode").count() > 0:
            self._ensure_select("#enterpriseNatureCode", first=True, required=True)
        elif self.page.locator("#enterpriseNature").count() > 0:
            self._ensure_select("#enterpriseNature", first=True, required=False)

        # standard industry cascader when present
        if self.page.locator("#fullCategoryId").count() > 0:
            self.select_cascader_levels(
                "#fullCategoryId",
                depth=3,
                required=False,
                field_name="标准行业",
            )

        print("DBG_DOMESTIC: region", flush=True)
        self.fill_domestic_region(
            province=province, city=city, district=district
        )
        print("DBG_DOMESTIC: region done", flush=True)
        # 办公/注册地址：必填，工商未回填则写入默认值
        self._dismiss_blocking_overlays()
        addr_office = office_address or "苏州市自动化办公地址"
        addr_register = (
            register_address
            or self._input_value("#registerAddress")
            or f"{province or '江苏'}{city or '苏州'}自动化注册地址"
        )
        self._ensure_input("#officeAddress", addr_office, required=True)
        self._ensure_input("#registerAddress", addr_register, required=True)
        # 兼容无 id 时按 label 填
        for label, value in (
            ("办公地址", addr_office),
            ("注册地址", addr_register),
        ):
            item = self.page.locator(".ant-form-item").filter(
                has=self.page.locator(
                    ".ant-form-item-label", has_text=re.compile(rf"^{re.escape(label)}$")
                )
            )
            if item.count() == 0:
                continue
            inp = item.first.locator("input, textarea").first
            if inp.count() == 0:
                continue
            try:
                cur = (inp.input_value(timeout=1000) or "").strip()
            except Exception:
                cur = ""
            if not cur:
                inp.click(timeout=3000)
                inp.fill(value)
                self.page.wait_for_timeout(200)

        # 采购偏好等（接口强校验：采购偏好不能为空）
        if self.page.locator("#purchasePreferenceCode").count() > 0:
            self._select_required("#purchasePreferenceCode", first=True)
        if self.page.locator("#purchaseFrequencyCode").count() > 0:
            self._select_if_present("#purchaseFrequencyCode", first=True, soft=True)

        # 客户背调报告等上传（国内常必填）
        print("DBG_DOMESTIC: before attachment", flush=True)
        if attachment is not None and Path(attachment).is_file():
            uploaded = self.upload_required_create_attachments(Path(attachment))
            bg_ok = (
                self.upload_by_field_label("客户背调报告", Path(attachment))
                or self.upload_by_field_label("背调报告", Path(attachment))
                or self.upload_sample_if_present("#backgroundReportUrls", Path(attachment))
                or self.upload_sample_if_present("#customerReportUrls", Path(attachment))
            )
            if not (bg_ok or uploaded > 0):
                # field may be hidden; leave for save-time validation retry
                pass

        print("DBG_DOMESTIC: fill done", flush=True)
        return company_name

    def _upload_list_has_file(self, item) -> bool:
        """列表有 done 文件名，或 picture-card 缩略图（可能无文案）即视为已上传。"""
        # picture-card：done + img 即可，详情依赖表单里的 url 而不是文件名文案
        pic_done = item.locator(
            ".ant-upload-list-item-done img[src], "
            ".ant-upload-list-item-success img[src], "
            ".ant-upload-list-item-done a[href^='http'], "
            ".ant-upload-list-item-done"
        )
        if pic_done.count() > 0:
            # 纯 done 节点也接受（无文件名的卡片上传）
            return True

        listed = item.locator(
            ".ant-upload-list-item-done, .ant-upload-list-item-success, "
            ".ant-upload-list-item-name, .ant-upload-list-item a, "
            ".ant-upload-list-item img[src]"
        )
        if listed.count() == 0:
            return False
        for i in range(min(listed.count(), 6)):
            node = listed.nth(i)
            text = (node.inner_text() or "").strip()
            src = ""
            try:
                if node.evaluate("el => el.tagName") == "IMG":
                    src = node.get_attribute("src") or ""
                else:
                    img = node.locator("img[src]")
                    if img.count() > 0:
                        src = img.first.get_attribute("src") or ""
            except Exception:
                src = ""
            if src and (
                src.startswith("http")
                or src.startswith("blob:")
                or src.startswith("data:image")
            ):
                return True
            if not text:
                continue
            if text.startswith("点击") or "请上传" in text or text == "上传文件":
                continue
            # 至少要有文件名片段（扩展名或非占位文案）
            if "." in text or len(text) >= 4:
                return True
        return False

    def _upload_form_item_file(self, item, file_path: Path) -> bool:
        """对单个 ant-form-item 上传文件，并等待 /api/file/file/upload 落库。

        上传后必须等列表出现 done/文件名，不能立刻点保存（CRM 客户/线索均已踩坑）。
        """
        if item is None or item.count() == 0 or not file_path.is_file():
            return False
        if self._upload_list_has_file(item):
            return True

        file_input = item.locator("input[type='file']")
        if file_input.count() == 0:
            return False
        try:
            item.first.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            pass
        try:
            with self.page.expect_response(
                lambda r: "file/file/upload" in (r.url or "")
                and r.request.method == "POST"
                and r.ok,
                timeout=20000,
            ):
                file_input.first.set_input_files(str(file_path))
        except Exception:
            try:
                file_input.first.set_input_files(str(file_path))
                self.page.wait_for_timeout(2000)
            except Exception:
                return False

        # 接口成功后列表落库仍可能慢一拍
        end = time.time() + 25
        while time.time() < end:
            if self._upload_list_has_file(item):
                self.page.wait_for_timeout(800)
                return True
            # 上传中/失败态
            err = item.locator(".ant-upload-list-item-error")
            if err.count() > 0:
                return False
            self.page.wait_for_timeout(400)
        return self._upload_list_has_file(item)

    def upload_sample_if_present(self, input_selector: str, file_path: Path) -> bool:
        """按字段 id 上传；id 常挂在 Upload 容器上，需取其 form-item 内 file input。"""
        if not file_path.is_file():
            return False
        item = self.page.locator(f".ant-form-item:has({input_selector})")
        if item.count() == 0:
            # 兼容：id 本身就是 file input
            direct = self.page.locator(f"input[type='file']{input_selector}")
            if direct.count() == 0:
                return False
            item = direct.locator(
                "xpath=ancestor::div[contains(@class,'ant-form-item')][1]"
            )
            if item.count() == 0:
                try:
                    with self.page.expect_response(
                        lambda r: "file/file/upload" in (r.url or "")
                        and r.request.method == "POST",
                        timeout=8000,
                    ):
                        direct.first.set_input_files(str(file_path))
                    self.page.wait_for_timeout(800)
                    return True
                except Exception:
                    return False
        return self._upload_form_item_file(item.first, file_path)

    def upload_by_field_label(self, label_text: str, file_path: Path) -> bool:
        """按表单项标题上传（如 客户名片 / 客户背调报告 / 海关记录附件）。"""
        if not file_path.is_file():
            return False
        item = self.page.locator(".ant-form-item").filter(
            has=self.page.locator(
                ".ant-form-item-label",
                has_text=re.compile(rf"^{re.escape(label_text)}$"),
            )
        )
        if item.count() == 0:
            item = self.page.locator(".ant-form-item").filter(
                has=self.page.locator(
                    ".ant-form-item-label",
                    has_text=re.compile(re.escape(label_text)),
                )
            )
        if item.count() == 0:
            item = self.page.locator(".ant-form-item").filter(
                has=self.page.locator(".ant-form-item-label", has_text=label_text)
            )
        if item.count() == 0:
            return False
        return self._upload_form_item_file(item.first, file_path)

    def upload_required_create_attachments(self, file_path: Path) -> int:
        """上传客户名片、客户报告、海关记录附件（进口记录为「有」时必填）。"""
        if not file_path.is_file():
            return 0
        targets = (
            ("客户名片", "#customerBusinessCardUrls"),
            ("客户报告", "#customerReportUrls"),
            ("客户背调报告", "#backgroundReportUrls"),
            ("背调报告", "#backgroundReportUrls"),
            ("海关记录附件", "#customsRecordAttachmentUrls"),
        )
        done = 0
        for label, sel in targets:
            # 字段未渲染则跳过（如进口记录选「无」时海关附件可能隐藏）
            visible = (
                self.page.locator(sel).count() > 0
                or self.page.locator(f".ant-form-item:has({sel})").count() > 0
                or self.page.locator(".ant-form-item-label", has_text=label).count() > 0
            )
            if not visible:
                continue
            ok = self.upload_by_field_label(label, file_path)
            if not ok:
                ok = self.upload_sample_if_present(sel, file_path)
            if ok:
                done += 1
        # 兼容旧录制别名
        if done < 2:
            for sel in ("#businessCardUrls", "#customerReportUrl"):
                if self.upload_sample_if_present(sel, file_path):
                    done += 1
        return done

    def pick_company_via_dropdown(self, company_name: str) -> str:
        """国外客户：输入随机企业名后，必须点选下拉返回项才能真正填入（不走工商校验）。"""
        assert company_name, "企业名称不能为空"
        company = self.page.locator("#companyName")
        assert company.count() > 0, "未找到企业名称 #companyName"
        company.first.click()
        company.first.fill("")
        company.first.fill(company_name)
        self.page.wait_for_timeout(600)

        dropdown_opts = self.page.locator(
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden) "
            ".ant-select-item-option:not(.ant-select-item-option-disabled), "
            ".ant-auto-complete-dropdown:not(.ant-select-dropdown-hidden) "
            ".ant-select-item-option, "
            ".rc-virtual-list .ant-select-item-option:not(.ant-select-item-option-disabled)"
        )
        # 等下拉出现
        end = time.time() + 12
        while time.time() < end and dropdown_opts.count() == 0:
            self.page.wait_for_timeout(300)

        assert dropdown_opts.count() > 0, (
            f"输入企业名「{company_name}」后未出现可点选下拉项"
        )

        # 优先点与输入一致/包含的项，否则点第一项
        matched = dropdown_opts.filter(has_text=company_name)
        if matched.count() == 0 and len(company_name) >= 4:
            matched = dropdown_opts.filter(has_text=company_name[:8])
        target = matched.first if matched.count() > 0 else dropdown_opts.first
        text = (target.inner_text() or "").strip().split("\n")[0]
        # 虚拟列表项常不稳定，避免 scroll_into_view_if_needed 卡死
        try:
            target.wait_for(state="visible", timeout=5000)
            target.click(timeout=8000)
        except PlaywrightTimeoutError:
            self.page.keyboard.press("ArrowDown")
            self.page.wait_for_timeout(200)
            self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(600)
        self._assert_create_form_still_open("企业名下拉点选")

        selected = self.read_company_name() or text or company_name
        assert selected, "点选企业名下拉后字段仍为空"
        return selected

    def _fill_required(self, selector: str, value: str) -> None:
        loc = self.page.locator(selector)
        assert loc.count() > 0, f"缺少必填字段: {selector}"
        assert value, f"必填字段值为空: {selector}"
        loc.first.scroll_into_view_if_needed(timeout=5000)
        loc.first.click(timeout=5000)
        loc.first.fill(str(value))
        self.page.wait_for_timeout(200)

    def _select_required(self, selector: str, *, keyword: str = "", first: bool = False) -> None:
        assert self.page.locator(selector).count() > 0, f"缺少必填下拉: {selector}"
        last_shown = ""
        for attempt in range(3):
            self._dismiss_select_dropdown()
            self.page.wait_for_timeout(200)
            if keyword:
                self._type_select_keyword(selector, keyword, multi=False, required=False)
            else:
                assert first, f"必填下拉需 keyword 或 first: {selector}"
                try:
                    self._select_plain_first_resilient(selector)
                except Exception:
                    try:
                        ant = self._ant_select_root(selector)
                        ant.locator(".ant-select-selector").first.click(timeout=3000)
                        self.page.wait_for_timeout(400)
                        self.page.keyboard.press("ArrowDown")
                        self.page.wait_for_timeout(200)
                        self.page.keyboard.press("Enter")
                        self.page.wait_for_timeout(400)
                    except Exception:
                        pass
            ant = self._ant_select_root(selector)
            last_shown = (ant.inner_text() or "").strip().replace("\n", " ")
            if last_shown and "请选择" not in last_shown:
                self._assert_create_form_still_open(f"必填下拉 {selector}")
                return
            self.page.wait_for_timeout(400 * (attempt + 1))
        raise AssertionError(f"必填下拉未选中: {selector} shown={last_shown!r}")

    def _select_enum_by_text(
        self, selector: str, option_text: str, *, required: bool = False
    ) -> None:
        """本地枚举 Select：按选项文案点选（如进口记录「有」）。"""
        if self.page.locator(selector).count() == 0:
            if required:
                raise AssertionError(f"缺少枚举下拉: {selector}")
            return
        assert option_text, f"枚举选项文案不能为空: {selector}"
        last_shown = ""
        for attempt in range(3):
            try:
                self._dismiss_select_dropdown()
                dropdown = self._open_select_dropdown(selector)
                option = dropdown.locator(
                    ".ant-select-item-option:not(.ant-select-item-option-disabled)"
                )
                option.first.wait_for(state="visible", timeout=8000)
                matched = option.filter(
                    has_text=re.compile(rf"^{re.escape(option_text)}$")
                )
                if matched.count() == 0:
                    matched = option.filter(has_text=option_text)
                if matched.count() == 0:
                    raise AssertionError(
                        f"{selector} 未找到选项「{option_text}」，"
                        f"可见: {[t.strip() for t in option.all_inner_texts()[:8]]}"
                    )
                matched.first.click(timeout=8000)
                self.page.wait_for_timeout(400)
                self._dismiss_select_dropdown()
                last_shown = (
                    self._ant_select_root(selector).inner_text() or ""
                ).strip().replace("\n", " ")
                if option_text in last_shown:
                    self._assert_create_form_still_open(f"枚举 {selector}={option_text}")
                    return
            except AssertionError:
                if required and attempt == 2:
                    raise
            except Exception:
                pass
            self.page.wait_for_timeout(300 * (attempt + 1))
        if required:
            raise AssertionError(
                f"枚举未选中: {selector} expect={option_text} shown={last_shown!r}"
            )

    def collect_create_form_errors(self) -> list[str]:
        """Collect create-form validation / toast / has-error labels."""
        errs: list[str] = []
        try:
            locs = self.page.locator(
                ".ant-form-item-explain-error, .ant-message-error, "
                ".ant-notification-notice-description"
            )
            for i in range(min(locs.count(), 40)):
                t = (locs.nth(i).inner_text() or "").strip()
                if t and t not in errs:
                    errs.append(t)
        except Exception:
            pass
        try:
            bad = self.page.locator(".ant-form-item-has-error")
            for i in range(min(bad.count(), 40)):
                item = bad.nth(i)
                label = ""
                try:
                    label = (
                        item.locator(".ant-form-item-label").inner_text() or ""
                    ).strip()
                except Exception:
                    label = ""
                explain = ""
                try:
                    explain = (
                        item.locator(".ant-form-item-explain-error").inner_text()
                        or ""
                    ).strip()
                except Exception:
                    explain = ""
                msg = explain or (f"{label} invalid" if label else "")
                if msg and msg not in errs:
                    errs.append(msg)
        except Exception:
            pass
        return errs

    def handle_customer_duplicate_modal(self) -> bool:
        """若出现「客户重复」弹窗（仅「取消创建」），点击关闭并返回 True。"""
        modal = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none'])"
        ).filter(has_text=re.compile(r"客户重复|重复客户|已存在.*客户|客户.*重复"))
        if modal.count() == 0:
            return False
        btn = modal.locator("button").filter(
            has_text=re.compile(r"取消创建|取\s*消|关\s*闭")
        )
        if btn.count() == 0:
            btn = self.page.locator(
                ".ant-modal-wrap:not([style*='display: none']) button"
            ).filter(has_text=re.compile(r"取消创建|取\s*消"))
        if btn.count() > 0:
            try:
                btn.first.click(force=True, timeout=5000)
            except Exception:
                btn.first.evaluate("el => el.click()")
            self.page.wait_for_timeout(600)
            return True
        xbtn = modal.locator("button.ant-modal-close")
        if xbtn.count() > 0:
            xbtn.first.click(force=True, timeout=3000)
            self.page.wait_for_timeout(400)
            return True
        return False

    def confirm_customer_create_save(self) -> None:
        """点新建客户表单「确定」；避免误关表单 / 误点取消保存。"""
        print("DBG_CONFIRM: start", flush=True)
        # 仅关掉真正的阻塞提示，不要点「新建客户」自己的确定
        for _ in range(3):
            modal = self.page.locator(
                ".ant-modal-wrap:not([style*='display: none']) .ant-modal-content"
            )
            if modal.count() == 0:
                break
            text = ""
            try:
                text = modal.first.inner_text() or ""
            except Exception:
                text = ""
            # 新建客户主表单：不要在这里点确定/关闭
            if re.search(r"新建客户|编辑客户", text) and not re.search(
                r"客户重复|未保存|是否取消", text
            ):
                break
            if re.search(r"未保存|是否取消", text):
                cancel = self.page.locator(
                    ".ant-modal-wrap:not([style*='display: none']) button"
                ).filter(has_text=re.compile(r"取\s*消"))
                if cancel.count() > 0:
                    cancel.first.click(force=True, timeout=3000)
                    self.page.wait_for_timeout(300)
                break
            if re.search(r"客户重复|重复客户", text):
                # 留给上层 handle_customer_duplicate_modal
                break
            closer = self.page.locator(
                ".ant-modal-wrap:not([style*='display: none']) button"
            ).filter(has_text=re.compile(r"知\s*道\s*了|我知道了|关\s*闭"))
            if closer.count() > 0:
                try:
                    closer.first.click(force=True, timeout=3000)
                    self.page.wait_for_timeout(400)
                    continue
                except Exception:
                    pass
            break

        # 优先：标题含「新建客户」的弹窗/抽屉脚注
        pattern = re.compile(r"确\s*定|保\s*存|提\s*交")
        create_hosts = [
            self.page.locator(".ant-modal-wrap:not([style*='display: none'])").filter(
                has_text=re.compile(r"新建客户")
            ),
            self.page.locator(".ant-drawer-open").filter(
                has_text=re.compile(r"新建客户")
            ),
            self.page.locator(".ant-drawer-open"),
            self.page.locator(".ant-modal-wrap:not([style*='display: none'])"),
        ]
        candidates = []
        for host in create_hosts:
            if host.count() == 0:
                continue
            candidates.append(
                host.first.locator(
                    ".ant-modal-footer button.ant-btn-primary, "
                    ".ant-drawer-footer button.ant-btn-primary, "
                    ".ant-pro-footer-bar button.ant-btn-primary, "
                    "button.ant-btn-primary"
                )
            )
        candidates.append(
            self.page.locator("button.ant-btn-primary").filter(has_text=pattern)
        )

        for loc in candidates:
            if loc.count() == 0:
                continue
            for i in range(loc.count() - 1, -1, -1):
                item = loc.nth(i)
                try:
                    if not item.is_visible():
                        continue
                    text = (item.inner_text() or "").strip()
                    # primary 无文案时也允许（部分主题只显示图标+确定在子节点）
                    if text and not re.search(r"确\s*定|保\s*存|提\s*交", text):
                        continue
                    in_modal = item.locator(
                        "xpath=ancestor::div[contains(@class,'ant-modal')][1]"
                    )
                    if in_modal.count() > 0:
                        modal_text = in_modal.inner_text() or ""
                        if re.search(r"未保存|是否取消", modal_text):
                            continue
                    try:
                        item.scroll_into_view_if_needed(timeout=3000)
                    except Exception:
                        pass
                    try:
                        item.click(force=True, timeout=5000)
                    except Exception:
                        item.evaluate("el => el.click()")
                    print("DBG_CONFIRM: clicked", flush=True)
                    self.page.wait_for_timeout(1200)
                    discard2 = self.page.locator(
                        ".ant-modal-wrap:not([style*='display: none'])"
                    ).filter(has_text=re.compile(r"未保存|是否取消"))
                    if discard2.count() > 0:
                        cancel = discard2.locator("button").filter(
                            has_text=re.compile(r"取\s*消")
                        )
                        if cancel.count() > 0:
                            cancel.first.click(timeout=3000)
                        raise AssertionError(
                            "点击确定后出现「未保存将失效」弹窗，说明未真正触发保存"
                        )
                    return
                except AssertionError:
                    raise
                except Exception:
                    continue
        print("DBG_CONFIRM: no button", flush=True)
        raise AssertionError("未找到新建客户「确定/保存」按钮")

    def select_contact_position(self, position_text: str = "采购员") -> None:
        """联系人职务：按文案点选（默认采购员）。"""
        sel = "#contactPersonSaveOrUpdateReq_positionCode"
        assert self.page.locator(sel).count() > 0, f"未找到联系人职务 {sel}"
        assert position_text, "联系人职务文案不能为空"
        self._dismiss_select_dropdown()
        dropdown = self._open_select_dropdown(sel)
        option = dropdown.locator(
            ".ant-select-item-option:not(.ant-select-item-option-disabled)"
        )
        option.first.wait_for(state="visible", timeout=10000)
        matched = option.filter(has_text=re.compile(rf"^{re.escape(position_text)}$"))
        if matched.count() == 0:
            matched = option.filter(has_text=position_text)
        assert matched.count() > 0, (
            f"联系人职务下拉未找到「{position_text}」，"
            f"可见项: {[t.strip() for t in option.all_inner_texts()[:12]]}"
        )
        try:
            matched.first.wait_for(state="visible", timeout=5000)
            matched.first.click(timeout=8000)
        except PlaywrightTimeoutError:
            # 列表较长时滚到可见项再点
            matched.first.evaluate("el => el.scrollIntoView({block:'nearest'})")
            matched.first.click(timeout=8000)
        self.page.wait_for_timeout(400)
        self._dismiss_select_dropdown()
        shown = (self._ant_select_root(sel).inner_text() or "").strip()
        assert position_text in shown, (
            f"联系人职务未选中: expect={position_text} shown={shown!r}"
        )
        self._assert_create_form_still_open("联系人职务")




    def fill_create_overseas_basic(
        self,
        *,
        company_name: str,
        contact_name: str,
        contact_phone: str,
        contact_email: str,
        country: str,
        follow_user_keyword: str,
        company_email: str,
        main_product: str,
        main_business: str,
        annual_turnover: str,
        company_people_num: str,
        overseas_address: str,
        remark: str,
        inquiry_remark: str,
        import_country: str = "日本",
        target_market: str = "",
        contact_position: str = "采购员",
        business_type_l1: str = "终端客户",
        business_type_l2: str = "品牌方",
    ) -> str:
        """国外客户：按录制补齐页面红星必填；企业名点选下拉，不走工商。"""
        if self.page.get_by_text(re.compile(r"工商信息查询")).count() > 0:
            if self.page.locator("#countryCode").count() == 0:
                raise AssertionError(
                    "fill_create_overseas_basic 检测到国内表单（工商信息查询），"
                    "请确认已点击「新建国外客户」"
                )

        final_company = self.pick_company_via_dropdown(company_name)

        self._fill_required("#contactPersonSaveOrUpdateReq_name", contact_name)
        if self.page.locator("#contactPersonSaveOrUpdateReq_phone").count() > 0:
            self._fill_required("#contactPersonSaveOrUpdateReq_phone", contact_phone)
        self.select_contact_position(contact_position)
        if contact_email:
            self._fill_if_present("#contactPersonSaveOrUpdateReq_email", contact_email)

        self._type_select_keyword("#countryCode", country, required=True)
        if self.page.locator("#contactPersonSaveOrUpdateReq_countryCode").count() > 0:
            shown = (
                self._ant_select_root(
                    "#contactPersonSaveOrUpdateReq_countryCode"
                ).inner_text()
                or ""
            )
            if country[:2] not in shown:
                self._type_select_keyword(
                    "#contactPersonSaveOrUpdateReq_countryCode", country
                )

        # 本轮只验证：经营类型一级 → 二级
        self.select_business_type_cascade(level1=business_type_l1, level2=business_type_l2)
        if company_email:
            self._fill_if_present("#email", company_email)
        self._select_required("#customerGradeCode", first=True)
        self._assign_follow_user(
            follow_user_keyword, prefer_text="采购员", required=True
        )

        self._fill_required("#mainProduct", main_product)
        self._fill_required("#mainBusiness", main_business)
        # 目标销售市场：多选远程搜；关键字对不上时回退日本/法国/第一项
        self._type_select_keyword(
            "#targetSalesMarketCodes",
            target_market or country or "日本",
            multi=True,
            required=True,
        )
        self._fill_required("#annualTurnover", annual_turnover)
        self._fill_if_present("#companyPeopleNum", company_people_num)
        self._fill_if_present("#overseasDetailAddress", overseas_address)
        self._fill_if_present("#remark", remark)

        self._select_required("#purchasePreferenceCode", first=True)
        self._select_if_present("#purchaseFrequencyCode", first=True, soft=True)
        # 进口记录/海关下单选「有」才会出现「海关记录附件」必填
        self._select_enum_by_text("#importRecordCode", "有", required=True)
        self._type_select_keyword("#importCountryCodes", import_country, multi=True)
        self._select_enum_by_text("#customsOrderCode", "有", required=False)
        self._fill_if_present("#customsRecordRemark", "自动化海关备注")

        if self.page.locator("#fullCategoryId").count() > 0:
            try:
                cascader = self.page.locator(
                    "div.ant-cascader:has(#fullCategoryId), "
                    ".ant-form-item:has(#fullCategoryId) .ant-cascader, "
                    ".ant-form-item:has(#fullCategoryId) .ant-select"
                ).first
                if cascader.count() > 0:
                    cascader.scroll_into_view_if_needed(timeout=3000)
                    cascader.click()
                    self.page.wait_for_timeout(400)
                    for _ in range(4):
                        items = self.page.locator(
                            ".ant-cascader-menus:visible .ant-cascader-menu-item:visible, "
                            ".ant-cascader-dropdown:not(.ant-cascader-dropdown-hidden) "
                            ".ant-cascader-menu-item:visible"
                        )
                        if items.count() == 0:
                            break
                        items.first.click()
                        self.page.wait_for_timeout(300)
                    self._dismiss_select_dropdown()
            except Exception:
                pass
        self._fill_if_present("#inquiryRemark", inquiry_remark)
        return final_company

    def _select_has_value(self, selector: str) -> bool:
        """判断 Select 是否已有选中值（兼容多选 tag / 单选文案）。"""
        try:
            ant = self._ant_select_root(selector)
        except Exception:
            return False
        items = ant.locator(
            ".ant-select-selection-item:not(.ant-select-selection-item-disabled), "
            ".ant-select-selection-overflow-item:not(.ant-select-selection-overflow-item-rest)"
        )
        if items.count() > 0:
            # overflow 里的 placeholder 不算
            for i in range(min(items.count(), 5)):
                text = (items.nth(i).inner_text() or "").strip()
                if text and "请选择" not in text and text != "+":
                    return True
        shown = (ant.inner_text() or "").strip()
        return bool(shown) and "请选择" not in shown

    def _type_select_keyword(
        self,
        selector: str,
        keyword: str,
        *,
        multi: bool = False,
        required: bool = False,
        prefer_texts: list[str] | None = None,
    ) -> None:
        """可搜索 Select：输入关键字后必须点选下拉项（禁止只填不点）。"""
        if self.page.locator(selector).count() == 0:
            if required:
                raise AssertionError(f"必填可搜索下拉不存在: {selector}")
            return
        last_error: Exception | None = None
        # 关键字失败时依次回退；空串表示直接展开点第一项
        candidates = [keyword] if keyword else [""]
        if multi and keyword:
            for fb in ("日本", "法国", "美国", "英国", "德国"):
                if fb != keyword and fb not in candidates:
                    candidates.append(fb)
            candidates.append("")

        for kw in candidates:
            try:
                self._dismiss_select_dropdown()
                ant = self._ant_select_root(selector)
                ant.scroll_into_view_if_needed(timeout=5000)
                shell = ant.locator(".ant-select-selector")
                (shell.first if shell.count() else ant).click(timeout=5000)
                self.page.wait_for_timeout(300)
                search = ant.locator("input.ant-select-selection-search-input")
                if search.count() == 0:
                    search = self.page.locator(selector)
                can_type = False
                if search.count() > 0:
                    try:
                        # Ant Select often marks search input readonly/unselectable
                        ro = search.first.get_attribute("readonly")
                        unsel = search.first.get_attribute("unselectable")
                        disabled = search.first.is_disabled()
                        can_type = (ro is None) and (unsel != "on") and (not disabled)
                    except Exception:
                        can_type = False
                if kw and can_type:
                    search.first.fill("")
                    search.first.fill(kw)
                    self.page.wait_for_timeout(1200)
                    self._wait_and_pick_option(
                        prefer_texts=prefer_texts or [kw],
                        keyword=kw,
                    )
                elif kw:
                    # readonly combobox: click matching visible option by text
                    self.page.wait_for_timeout(400)
                    opts = self._visible_select_options()
                    end_t = time.time() + 8
                    while time.time() < end_t and opts.count() == 0:
                        self.page.wait_for_timeout(200)
                        opts = self._visible_select_options()
                    matched = opts.filter(has_text=re.compile(re.escape(kw)))
                    if matched.count() == 0:
                        matched = opts.filter(has_text=kw)
                    if matched.count() > 0:
                        matched.first.click(force=True, timeout=8000)
                    elif opts.count() > 0:
                        # fallback: scan titles
                        picked = False
                        for i in range(min(opts.count(), 40)):
                            t = (opts.nth(i).inner_text() or "").strip()
                            if kw in t:
                                opts.nth(i).click(force=True, timeout=8000)
                                picked = True
                                break
                        if not picked:
                            raise AssertionError(
                                f"option not found for {selector}: {kw!r}"
                            )
                    else:
                        raise AssertionError(f"no options for {selector}")
                    self.page.wait_for_timeout(400)
                else:
                    opt = self._visible_select_options()
                    if opt.count() == 0:
                        self.page.keyboard.press("ArrowDown")
                        self.page.wait_for_timeout(200)
                        self.page.keyboard.press("Enter")
                        self.page.wait_for_timeout(400)
                    else:
                        opt.first.click(force=True, timeout=8000)
                        self.page.wait_for_timeout(400)
                if multi:
                    self._dismiss_select_dropdown()
                if self._select_has_value(selector):
                    self._assert_create_form_still_open(f"可搜索下拉 {selector}")
                    return
                last_error = AssertionError(
                    f"下拉点选后仍无值: {selector} keyword={kw!r}"
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self._dismiss_select_dropdown()
                continue

        if required:
            raise AssertionError(
                f"必填下拉未选中: {selector} keyword={keyword!r} ({last_error})"
            ) from last_error

    # --- 客户查重（仅菜单进入，对齐录制 customerDuplicateCheck）---

    def _duplicate_check_keyword_input(self):
        return self.page.locator(
            'input[placeholder*="企业全称"], input[placeholder*="关键字"]'
        )

    def open_duplicate_check_via_menu(self, crm) -> None:
        """仅侧栏「客户 → 客户查重」进入，禁止 goto 直达。"""
        crm.open_menu_path("客户", "客户查重")
        crm.assert_menu_reachable("客户查重")
        url = (self.page.url or "").lower()
        assert "customerduplicatecheck" in url or "duplicate" in url, (
            f"菜单进入后 URL 不像客户查重页: {self.page.url}"
        )
        self._duplicate_check_keyword_input().first.wait_for(
            state="visible", timeout=20000
        )

    def search_duplicate_check(self, keyword: str) -> dict:
        """客户查重页：输入关键字 → 点「立即查询」→ 等 checkRepeatPage。"""
        text = (keyword or "").strip()
        assert text, "查重关键字不能为空"
        inp = self._duplicate_check_keyword_input()
        assert inp.count() > 0, "客户查重页无查询输入框"
        inp.first.fill(text)
        btn = self.page.locator("button.ant-btn-primary").filter(
            has_text=re.compile(r"立即查询")
        )
        assert btn.count() > 0, "客户查重页无「立即查询」按钮"

        def _is_dup(resp) -> bool:
            u = (resp.url or "").lower()
            return (
                resp.request.method == "POST"
                and "customer/checkrepeatpage" in u
                and resp.ok
            )

        with self.page.expect_response(_is_dup, timeout=30000) as info:
            btn.first.click()
        body = info.value.json()
        self.page.wait_for_timeout(800)
        return body

    @staticmethod
    def _dup_total(api_body: dict) -> int:
        data = api_body.get("data") if isinstance(api_body, dict) else None
        if not isinstance(data, dict):
            return 0
        for key in ("totalCount", "total"):
            try:
                return int(data.get(key) or 0)
            except (TypeError, ValueError):
                continue
        rows = data.get("data") or data.get("records") or data.get("list") or []
        return len(rows) if isinstance(rows, list) else 0

    @staticmethod
    def _dup_rows(api_body: dict) -> list[dict]:
        data = api_body.get("data") if isinstance(api_body, dict) else None
        if not isinstance(data, dict):
            return []
        rows = data.get("data") or data.get("records") or data.get("list") or []
        return rows if isinstance(rows, list) else []

    def assert_duplicate_check_hit(
        self, keyword: str = "", *, api_body: dict | None = None
    ) -> None:
        """查重命中：接口有数据 + 页面展示命中企业（非「未发现重复客户」空态）。"""
        assert api_body is not None, "查重命中断言需要 api_body"
        assert api_body.get("code") == 1000, f"查重接口失败: {api_body}"
        rows = self._dup_rows(api_body)
        assert self._dup_total(api_body) > 0 and rows, (
            f"查重应命中但无数据: {api_body}"
        )

        company = str(rows[0].get("companyName") or keyword or "").strip()
        assert company, "查重命中但无企业名称"

        # 命中场景绝不能出现无重复空态
        miss_title = self.page.get_by_text(re.compile(r"未发现重复客户"))
        if miss_title.count() > 0:
            assert not miss_title.first.is_visible(), (
                "查重接口已命中，但页面仍展示「未发现重复客户」"
            )

        # 结果区必须可见企业名（用户肉眼应能看到重复记录）
        company_loc = self.page.get_by_text(company, exact=False)
        assert company_loc.count() > 0, f"查重结果区未展示企业名: {company!r}"
        company_loc.first.scroll_into_view_if_needed(timeout=5000)
        expect(company_loc.first).to_be_visible(timeout=10000)

        # 命中列表应有数据行（表格或列表项）
        result_rows = self.page.locator(
            ".ant-table-tbody tr.ant-table-row, "
            ".ant-list-item, tr.ant-table-row"
        ).filter(has_text=company)
        assert result_rows.count() > 0, (
            f"查重命中但列表无企业行: {company!r}"
        )

        # 建议操作列：非公海展示「联系跟进人」（文案，不可点）；公海展示「去公海认领」
        if rows[0].get("isPublicSea") or rows[0].get("claimBtn"):
            action = self.page.get_by_text(re.compile(r"去公海认领"))
            assert action.count() > 0, "公海客户查重命中应展示「去公海认领」"
            expect(action.first).to_be_visible(timeout=5000)
        else:
            action = self.page.get_by_text(re.compile(r"联系跟进人"))
            assert action.count() > 0, (
                "查重命中应展示「联系跟进人」建议操作文案"
            )
            expect(action.first).to_be_visible(timeout=5000)

        follow = str(rows[0].get("followUserName") or "").strip()
        if follow:
            follow_loc = self.page.get_by_text(follow, exact=False)
            if follow_loc.count() > 0:
                expect(follow_loc.first).to_be_visible(timeout=5000)

    def assert_duplicate_check_miss(
        self, keyword: str = "", *, api_body: dict | None = None
    ) -> None:
        """查重无命中：接口 total=0 + 页面空态文案 + 可点「立即新建该客户」。"""
        assert api_body is not None, "查重无命中断言需要 api_body"
        assert api_body.get("code") == 1000, f"查重接口失败: {api_body}"
        assert self._dup_total(api_body) == 0, (
            f"查重应无命中但 total>0: {api_body}"
        )

        expect(
            self.page.get_by_text(re.compile(r"未发现重复客户")).first
        ).to_be_visible(timeout=10000)

        if keyword:
            # 文案示例：系统中目前不存在包含 “xxx” 的企业数据
            kw = re.escape(keyword)
            hint = self.page.locator("body").filter(
                has_text=re.compile(rf"不存在包含.*{kw}|{kw}")
            )
            assert hint.count() > 0, f"无重复空态未包含关键字: {keyword!r}"

        expect(
            self.page.get_by_text(re.compile(r"您可以放心创建")).first
        ).to_be_visible(timeout=5000)

        create_btn = self.page.locator(
            "button, a, span, div[role='button']"
        ).filter(has_text=re.compile(r"立即新建.*?客户|新建该客户|新建客户"))
        if create_btn.count() == 0:
            snippet = (self.page.locator("body").inner_text() or "").replace("\n", " | ")
            print(f"[dup-miss] 未找到新建按钮，页面片段: {snippet[:500]}", flush=True)
        assert create_btn.count() > 0, "无重复场景应展示「立即新建客户」按钮"
        expect(create_btn.first).to_be_visible(timeout=5000)

    def _dup_miss_create_trigger(self):
        return self.page.locator(
            "button, a, span, div[role='button']"
        ).filter(has_text=re.compile(r"立即新建.*?客户|新建该客户"))

    def open_create_from_dup_miss_dropdown(self, kind: str) -> None:
        """无重复空态：点「立即新建客户」下拉 → 选国内/国外 → 打开对应新建弹窗。"""
        if kind not in {"domestic", "overseas"}:
            raise AssertionError(f"不支持的客户类型: {kind}")
        trigger = self._dup_miss_create_trigger()
        assert trigger.count() > 0, "查重无命中页无「立即新建客户」入口"
        trigger.first.click()
        self.page.wait_for_timeout(500)
        self._click_create_kind_menu(kind)
        self.page.locator("#companyName").first.wait_for(
            state="visible", timeout=15000
        )
        self._ensure_customer_kind(kind, required=True)

    def assert_create_customer_modal(self, kind: str) -> None:
        """断言新建客户弹窗已打开且为国内/国外对应表单（不做保存）。"""
        expect(self.page.get_by_text(re.compile(r"新建客户")).first).to_be_visible(
            timeout=15000
        )
        expect(self.page.locator("#companyName").first).to_be_visible(timeout=10000)
        if kind == "domestic":
            expect(
                self.page.get_by_text(re.compile(r"工商信息查询")).first
            ).to_be_visible(timeout=5000)
            country = (self._read_select_display("#countryCode") or "").strip()
            if country:
                assert "中国" in country, f"国内客户默认国家应为「中国」: {country!r}"
        elif kind == "overseas":
            assert self.page.get_by_text(re.compile(r"工商信息查询")).count() == 0, (
                "国外客户表单不应出现「工商信息查询」"
            )
            country = (self._read_select_display("#countryCode") or "").strip()
            if country:
                assert "中国" not in country, (
                    f"国外客户默认国家不应为中国: {country!r}"
                )
        else:
            raise AssertionError(f"不支持的客户类型: {kind}")

    def cancel_create_customer_form(self) -> None:
        """新建客户弹窗：取消 → 确认放弃未保存（不实际创建）。"""
        cancel = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none']) button, "
            ".ant-drawer-open button"
        ).filter(has_text=re.compile(r"^取\s*消$|取\s*消"))
        assert cancel.count() > 0, "新建客户表单无「取消」按钮"
        cancel.first.click(timeout=5000)
        self.page.wait_for_timeout(400)
        leave = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none'])"
        ).filter(has_text=re.compile(r"未保存|是否取消|将失效"))
        if leave.count() > 0:
            confirm = leave.locator("button").filter(
                has_text=re.compile(r"确\s*定|确\s*认|离\s*开|不保存")
            )
            assert confirm.count() > 0, "点取消后应出现「未保存将失效」确认框"
            confirm.first.click(timeout=5000)
            self.page.wait_for_timeout(500)
        assert not self._is_customer_create_form_open(), (
            "取消新建后表单仍打开"
        )

    def update_company_and_inquiry(
        self, *, company_name: str, inquiry_remark: str
    ) -> None:
        self._fill_if_present("#companyName", company_name)
        self._fill_if_present("#inquiryRemark", inquiry_remark)
