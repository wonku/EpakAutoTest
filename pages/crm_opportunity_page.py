from __future__ import annotations

import re
import time
from datetime import datetime

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from utils.base_page import BasePage


class CrmOpportunityPage(BasePage):
    """CRM UI 页面基类（机会页 + 线索/客户/联系人/活动/询价共用交互）。

    新建/编辑表单交互规范（后续页面必须复用，禁止再造一套）：
    - 收起下拉 / Cascader / 日期面板 → `_dismiss_select_dropdown()`
    - 误出「未保存将失效」→ `_stay_on_form_if_discard_prompt()`
    - 断言仍在表单 → `_assert_create_form_still_open(where)`
    - 点选下拉项 → `_click_dropdown_option_node()` / `_pick_dropdown_option()`
    - 经营类型/行业级联 → `select_business_type_cascade()` / `select_industry_cascade()` / `select_cascader_levels()`
    - 只读日期区间 → `set_ant_range_picker()`（禁止对 readonly input 直接 fill）
    - **禁止** `body.click(x=5,y=5)`、对打开中的新建表单盲目 `Escape`
      （会点到遮罩并唤起「取消保存」确认框）
    """

    def __init__(self, page: Page):
        super().__init__(page)

    # ---------- 通用按钮 / 遮罩 ----------

    def click_toolbar_button(self, text_pattern: str) -> None:
        """点击工具栏/表单按钮；兼容 Ant Design「查 询」「确 认」中间空格。"""
        pattern = re.compile(text_pattern)
        candidates = [
            self.page.get_by_role("button", name=pattern),
            self.page.locator("button").filter(has_text=pattern),
            self.page.locator("a").filter(has_text=pattern),
        ]
        last_error: Exception | None = None
        for loc in candidates:
            try:
                target = loc.first
                if target.count() == 0:
                    continue
                target.scroll_into_view_if_needed(timeout=3000)
                target.click(timeout=8000)
                self.page.wait_for_timeout(600)
                return
            except PlaywrightTimeoutError as exc:
                last_error = exc
                continue
        raise AssertionError(f"未找到可点击按钮: {text_pattern}（{last_error}）")

    # ---------- 表单浮层规范 API（全 CRM 模块统一调用） ----------

    def _stay_on_form_if_discard_prompt(self) -> bool:
        """若误出「未保存将失效」确认框，点「取消」留在表单。返回是否处理过。"""
        discard = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none'])"
        ).filter(has_text=re.compile(r"未保存|是否取消|将失效"))
        if discard.count() == 0:
            return False
        stay = discard.locator("button").filter(has_text=re.compile(r"取\s*消"))
        if stay.count() > 0:
            try:
                stay.first.click(timeout=3000)
            except Exception:
                stay.first.click(force=True, timeout=3000)
            self.page.wait_for_timeout(300)
        return True

    def _assert_create_form_still_open(self, where: str) -> None:
        """断言未因误操作弹出「取消保存」；若已弹出则点取消留在表单并失败提示。"""
        if self._stay_on_form_if_discard_prompt():
            raise AssertionError(
                f"{where}: 误触发了「取消保存」确认框（常见原因：body 空白点击 / "
                f"Escape / 点到页脚取消或抽屉关闭）。已点弹窗取消留在表单。"
            )

    def _dismiss_select_dropdown(self) -> None:
        """收起 Select / Cascader / DatePicker 浮层。

        只点表单标题或区块标题，**禁止** body 左上角空白点击（会触发遮罩关闭
        →「未保存信息将失效」）。客户/线索等模块已踩过坑，后续一律调本方法。
        """
        if self._stay_on_form_if_discard_prompt():
            return

        still_open = self.page.locator(
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden), "
            ".ant-cascader-dropdown:not(.ant-cascader-dropdown-hidden), "
            ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden)"
        )
        if still_open.count() == 0:
            return

        for sel in (
            ".ant-drawer-open .ant-drawer-title",
            ".ant-modal-wrap:not([style*='display: none']) .ant-modal-title",
            "text=基础信息",
            "text=公司信息",
            "text=询盘信息",
            "#name",
            "#companyName",
        ):
            loc = self.page.locator(sel)
            if loc.count() == 0:
                continue
            try:
                if loc.first.is_visible():
                    loc.first.click(timeout=2000)
                    self.page.wait_for_timeout(250)
                    self._stay_on_form_if_discard_prompt()
                    return
            except Exception:
                continue

        # 兜底：blur 当前焦点，不点页面遮罩
        try:
            self.page.evaluate(
                """() => {
                    const active = document.activeElement;
                    if (active && typeof active.blur === 'function') active.blur();
                }"""
            )
        except Exception:
            pass
        self.page.wait_for_timeout(200)
        self._stay_on_form_if_discard_prompt()

    def close_overlays(self) -> None:
        """关闭可能残留的 Modal / Drawer，避免挡住列表查询按钮。

        注意：若当前是「未保存将失效」确认框，点「取消」留在表单，不要点确认离开。
        新建/编辑主表单打开时只收起浮层，不关表单。
        """
        if self._stay_on_form_if_discard_prompt():
            self._dismiss_select_dropdown()
            return

        for _ in range(3):
            if self._stay_on_form_if_discard_prompt():
                return
            modal = self.page.locator(
                ".ant-modal-wrap:not([style*='display: none']) .ant-modal-content"
            )
            if modal.count() > 0 and modal.first.is_visible():
                # 新建/编辑主表单（含「新建线索」）不要在这里关掉
                titles = modal.locator(".ant-modal-title")
                title_text = ""
                if titles.count() > 0:
                    title_text = (titles.first.inner_text() or "").strip()
                if re.search(r"新建|编辑|新增", title_text):
                    self._dismiss_select_dropdown()
                    return

                ok = self.page.locator(
                    ".ant-modal-wrap:not([style*='display: none']) "
                    "button.ant-btn-primary"
                )
                if ok.count() > 0:
                    try:
                        ok.last.click(timeout=3000)
                        self.page.wait_for_timeout(500)
                        continue
                    except PlaywrightTimeoutError:
                        pass
                closer = self.page.locator(
                    ".ant-modal-wrap:not([style*='display: none']) "
                    "button.ant-modal-close"
                )
                if closer.count() > 0:
                    try:
                        closer.first.click(timeout=2000)
                        self.page.wait_for_timeout(400)
                        continue
                    except PlaywrightTimeoutError:
                        pass
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(400)
                self._stay_on_form_if_discard_prompt()
                continue
            break
        # 列表页收尾：勿对打开中的新建表单 Escape
        create_open = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none']) .ant-modal-title, "
            ".ant-drawer-open .ant-drawer-title"
        ).filter(has_text=re.compile(r"新建|编辑|新增"))
        if create_open.count() > 0:
            self._dismiss_select_dropdown()
            return
        self.close_drawer()
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)
        self._stay_on_form_if_discard_prompt()

    def confirm_save(self) -> None:
        scopes = [
            self.page.locator(".ant-drawer-open .ant-drawer-footer"),
            self.page.locator(
                ".ant-modal-wrap:not([style*='display: none']) .ant-modal-footer"
            ),
            self.page.locator("body"),
        ]
        pattern = re.compile(r"确\s*认|确\s*定|保\s*存|提\s*交")
        last_error: Exception | None = None
        for scope in scopes:
            if scope.count() == 0:
                continue
            btn = scope.locator("button.ant-btn-primary").filter(has_text=pattern)
            if btn.count() == 0:
                btn = scope.get_by_role("button", name=pattern)
            if btn.count() == 0:
                continue
            try:
                btn.last.scroll_into_view_if_needed(timeout=3000)
                btn.last.click(timeout=8000)
                self.page.wait_for_timeout(1500)
                self.close_overlays()
                return
            except PlaywrightTimeoutError as exc:
                last_error = exc
                try:
                    btn.last.click(force=True, timeout=3000)
                    self.page.wait_for_timeout(1500)
                    self.close_overlays()
                    return
                except PlaywrightTimeoutError as exc2:
                    last_error = exc2
        raise AssertionError(f"未找到保存/确认按钮（{last_error}）")

    def click_search(self) -> None:
        self.close_overlays()
        search = self.page.locator(
            "form button.ant-btn-primary, "
            ".ant-pro-table-search button.ant-btn-primary, "
            ".ant-form button.ant-btn-primary"
        ).filter(has_text=re.compile(r"查\s*询|搜\s*索"))
        if search.count() == 0:
            search = self.page.get_by_role("button", name=re.compile(r"查\s*询|搜\s*索"))
        assert search.count() > 0, "未找到列表查询按钮"
        try:
            search.first.click(timeout=8000)
        except PlaywrightTimeoutError:
            search.first.click(force=True, timeout=5000)
        self.page.wait_for_timeout(600)

    def filter_by_name(self, name: str) -> None:
        self.page.locator("#opportunity_form_name").fill(name)
        self.click_search()
        self.page.wait_for_timeout(1200)

    def filter_by_customer_keyword(self, keyword: str) -> None:
        self.select_searchable("#opportunity_form_customerIdList", keyword, multi=True)
        self.click_search()
        self.page.wait_for_timeout(1200)

    # ---------- Ant Select（核心：输入关键字 → 选返回项） ----------

    def _ant_select_root(self, root_selector: str) -> Locator:
        """定位 .ant-select 根节点（表单 id 常挂在内部 search input 上）。"""
        # 最稳：外层 ant-select 包含该 id/选择器
        by_has = self.page.locator(f"div.ant-select:has({root_selector})")
        if by_has.count() > 0:
            return by_has.first

        node = self.page.locator(root_selector).first
        assert node.count() > 0, f"未找到字段: {root_selector}"
        ant = node.locator(
            "xpath=./ancestor-or-self::div[contains(@class,'ant-select')][1]"
        )
        if ant.count() > 0:
            return ant.first

        wrapped = self.page.locator(
            f".ant-form-item:has({root_selector}) .ant-select"
        ).first
        if wrapped.count() > 0:
            return wrapped
        raise AssertionError(f"未解析到 ant-select 根节点: {root_selector}")

    def _open_select_dropdown(self, root_selector: str) -> Locator:
        ant = self._ant_select_root(root_selector)
        # 直接点当前 Select 展开即可（勿 Escape：会清空已选多选项）
        shell = ant.locator(".ant-select-selector")
        target = shell.first if shell.count() > 0 else ant
        try:
            target.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        try:
            target.click(timeout=3000)
        except PlaywrightTimeoutError:
            target.evaluate("el => el.click()")
        self.page.wait_for_timeout(400)

        dropdown = self.page.locator(
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
        )
        if dropdown.count() == 0:
            arrow = ant.locator(".ant-select-arrow")
            if arrow.count() > 0:
                arrow.first.evaluate("el => el.click()")
            else:
                target.evaluate("el => el.click()")
            self.page.wait_for_timeout(400)

        dropdown = self.page.locator(
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
        ).last
        try:
            dropdown.wait_for(state="visible", timeout=8000)
        except PlaywrightTimeoutError:
            # 远程下拉偶发不挂 DOM：键盘展开/选第一项，调用方再取选项
            self.page.keyboard.press("ArrowDown")
            self.page.wait_for_timeout(300)
            dropdown = self.page.locator(
                ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
            ).last
            try:
                dropdown.wait_for(state="visible", timeout=3000)
            except PlaywrightTimeoutError as exc:
                raise AssertionError(
                    f"Select 下拉未打开: {root_selector}"
                ) from exc
        return dropdown

    def _type_into_opened_select(self, root_selector: str, keyword: str) -> None:
        """向当前打开的可搜索 Select 输入关键字。"""
        ant = self._ant_select_root(root_selector)
        search = ant.locator("input.ant-select-selection-search-input")
        if search.count() == 0:
            search = self.page.locator(root_selector)
        assert search.count() > 0, f"Select 无搜索框: {root_selector}"

        # 多选 search input 常 opacity:0 + readonly，先点 selector 再改属性键盘输入
        shell = ant.locator(".ant-select-selector")
        if shell.count() > 0:
            shell.first.click(timeout=5000)
        search.evaluate(
            """el => {
                el.removeAttribute('readonly');
                el.removeAttribute('unselectable');
                el.style.opacity = '1';
                el.focus();
            }"""
        )
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Backspace")
        self.page.keyboard.type(keyword, delay=45)
        # 等远程搜索
        self.page.wait_for_timeout(1500)

    def _dropdown_option_locator(self, dropdown: Locator) -> Locator:
        """兼容 ant-select / role=option / 虚拟列表行（避免仅 :visible 导致误判无选项）。"""
        return dropdown.locator(
            ".ant-select-item-option:not(.ant-select-item-option-disabled), "
            ".ant-select-item:not(.ant-select-item-option-disabled), "
            "[role='option'], "
            ".rc-virtual-list-holder-inner > div"
        )

    def _click_dropdown_option_node(self, node: Locator) -> None:
        """点选下拉项：弹层/虚拟列表里常 outside viewport，force 不够时用 JS click。"""
        try:
            node.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        try:
            node.click(force=True, timeout=5000)
            return
        except Exception:
            pass
        try:
            node.evaluate("el => el.click()")
            return
        except Exception:
            pass
        # 最后：聚焦后回车（部分 ant-select 选项）
        try:
            node.evaluate(
                """el => {
                    el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                    el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                    el.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                }"""
            )
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(f"下拉项点击失败: {exc}") from exc

    def _pick_dropdown_option(self, dropdown: Locator, text: str | None = None) -> None:
        option = self._dropdown_option_locator(dropdown)
        try:
            option.first.wait_for(state="attached", timeout=10000)
        except PlaywrightTimeoutError as exc:
            raise AssertionError(f"下拉无可见选项: {exc}") from exc

        if text:
            # 优先按完整展示文案点选（如「指定到个人 / 甜甜 (采购员)」）
            for pattern in (
                re.compile(rf"指定到个人\s*/\s*.*{re.escape(text)}"),
                re.compile(rf".*{re.escape(text)}.*采购员.*"),
                re.compile(re.escape(text)),
            ):
                by_text = dropdown.get_by_text(pattern)
                for i in range(min(by_text.count(), 6)):
                    node = by_text.nth(i)
                    label = (node.inner_text() or "").strip().replace("\n", " ")
                    if not label or label == "系统分配":
                        continue
                    self._click_dropdown_option_node(node)
                    self.page.wait_for_timeout(500)
                    return

            by_title = dropdown.locator(
                f'.ant-select-item-option[title*="{text}"], '
                f'.ant-select-item-option[title*="{text[:8]}"]'
            )
            if by_title.count() > 0:
                self._click_dropdown_option_node(by_title.first)
                self.page.wait_for_timeout(500)
                return
            matched = option.filter(has_text=text)
            if matched.count() > 0:
                self._click_dropdown_option_node(matched.first)
                self.page.wait_for_timeout(500)
                return
            # 高亮项：优先 JS/鼠标点，避免裸 Enter 触发表单提交
            active = dropdown.locator(
                ".ant-select-item-option-active:not(.ant-select-item-option-disabled)"
            )
            if active.count() > 0:
                self._click_dropdown_option_node(active.first)
                self.page.wait_for_timeout(500)
                return

        # 跳过「系统分配」等占位项
        for i in range(min(option.count(), 10)):
            cand = option.nth(i)
            label = (cand.inner_text() or "").strip().replace("\n", " ")
            if not label or label == "系统分配":
                continue
            self._click_dropdown_option_node(cand)
            self.page.wait_for_timeout(500)
            return

        self._click_dropdown_option_node(option.first)
        self.page.wait_for_timeout(500)

    def _assert_select_has_value(self, root_selector: str, keyword: str) -> None:
        ant = self._ant_select_root(root_selector)
        self.page.wait_for_timeout(400)
        selected = ant.locator(
            ".ant-select-selection-item, "
            ".ant-select-selection-overflow-item .ant-select-selection-item"
        )
        shown = (ant.inner_text() or "").replace("\n", " ").strip()
        if "请选择" in shown and selected.count() == 0:
            raise AssertionError(
                f"选择后仍是占位文案: {root_selector} keyword={keyword} shown={shown!r}"
            )
        # 多选/单选：有 selection-item，或展示文案包含关键字片段
        ok = selected.count() > 0 or (keyword and keyword[:6] in shown)
        assert ok, (
            f"选择后未回填选中值: {root_selector} keyword={keyword} shown={shown!r}"
        )

    def select_searchable(
        self,
        root_selector: str,
        keyword: str,
        *,
        multi: bool = False,
    ) -> None:
        """可搜索 Select：点开 → 输入关键字 → 点匹配下拉项。"""
        assert keyword, f"关键字不能为空: {root_selector}"
        self._open_select_dropdown(root_selector)
        self._type_into_opened_select(root_selector, keyword)
        dropdown = self.page.locator(
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
        ).last
        try:
            dropdown.wait_for(state="visible", timeout=8000)
        except PlaywrightTimeoutError as exc:
            raise AssertionError(
                f"输入「{keyword}」后下拉未保持打开: {root_selector}"
            ) from exc

        options = self._dropdown_option_locator(dropdown)
        # 远程搜索偶发延迟：轮询等待选项出现
        for _ in range(20):
            if options.count() > 0:
                break
            self.page.wait_for_timeout(250)
            options = self._dropdown_option_locator(dropdown)
        if options.count() == 0:
            # 从后往前找真正带选项的下拉层（避免 .last 命中空层）
            dropdowns = self.page.locator(
                ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
            )
            picked_dropdown = None
            for i in range(dropdowns.count() - 1, -1, -1):
                cand = dropdowns.nth(i)
                if self._dropdown_option_locator(cand).count() > 0:
                    picked_dropdown = cand
                    break
            if picked_dropdown is None:
                raise AssertionError(
                    f"输入「{keyword}」后下拉无选项: {root_selector}"
                )
            dropdown = picked_dropdown

        self._pick_dropdown_option(dropdown, keyword)

        if multi:
            # 多选：点选后下拉常仍打开；用安全收起，禁止 body 空白点击
            self._dismiss_select_dropdown()
        else:
            still_open = self.page.locator(
                ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
            )
            if still_open.count() > 0 and still_open.last.is_visible():
                self._dismiss_select_dropdown()

        self._assert_select_has_value(root_selector, keyword)

    def select_plain_first(self, root_selector: str) -> None:
        """枚举/远程 Select：点开 → 等待选项出现 → 选第一项（含键盘兜底）。

        展会等远程下拉打开后选项可能延迟加载；禁止只对空的 `.last` 层立刻断言失败。
        """
        self._open_select_dropdown(root_selector)
        dropdown = None
        for _ in range(24):
            dropdowns = self.page.locator(
                ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
            )
            for i in range(dropdowns.count() - 1, -1, -1):
                cand = dropdowns.nth(i)
                if self._dropdown_option_locator(cand).count() > 0:
                    dropdown = cand
                    break
            if dropdown is not None:
                break
            self.page.wait_for_timeout(250)

        if dropdown is None:
            # 选项迟迟不挂 DOM：仅当确有可见下拉时才键盘选；禁止裸 Enter（会触发表单提交/查重）
            open_dd = self.page.locator(
                ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
            )
            if open_dd.count() > 0:
                try:
                    if open_dd.last.is_visible():
                        self.page.keyboard.press("ArrowDown")
                        self.page.wait_for_timeout(200)
                        self.page.keyboard.press("Enter")
                        self.page.wait_for_timeout(400)
                        self._dismiss_select_dropdown()
                        self._assert_select_has_value(root_selector, "")
                        return
                except Exception:
                    pass
            raise AssertionError(f"Select 下拉无选项且未打开，拒绝 Enter 提交: {root_selector}")

        self._pick_dropdown_option(dropdown, None)
        self._dismiss_select_dropdown()
        self._assert_select_has_value(root_selector, "")


    def set_ant_range_picker(self, root_selector: str, *, start: str, end: str = "") -> None:
        """Ant Design RangePicker（只读 input）：点开后点选日历格，禁止 fill。"""
        end = end or start
        if self.page.locator(root_selector).count() == 0:
            raise AssertionError(f"未找到日期控件 {root_selector}")
        picker = self.page.locator(
            f"div.ant-picker:has({root_selector}), .ant-form-item:has({root_selector}) .ant-picker"
        )
        target = picker.first if picker.count() > 0 else self.page.locator(root_selector).first
        target.scroll_into_view_if_needed(timeout=5000)
        target.click(timeout=5000)
        self.page.wait_for_timeout(400)
        panel = self.page.locator(
            ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden)"
        )
        assert panel.count() > 0, f"日期面板未打开: {root_selector}"

        self._picker_goto_month(panel.first, start)
        assert self._click_picker_day(panel.first, start), f"未能点选开始日期 {start}"
        self._picker_goto_month(panel.first, end)
        assert self._click_picker_day(panel.first, end), f"未能点选结束日期 {end}"
        self._dismiss_select_dropdown()
        self.page.wait_for_timeout(300)

    def _picker_goto_month(self, panel, day: str) -> None:
        """把可见面板切到目标年月：只点可见的 prev/next 月按钮。"""
        try:
            target = datetime.strptime(day[:10], "%Y-%m-%d")
        except ValueError as exc:
            raise AssertionError(f"日期格式须 YYYY-MM-DD: {day}") from exc

        for _ in range(48):
            if panel.locator(
                f"td.ant-picker-cell-in-view[title='{day[:10]}']"
            ).count() > 0:
                return

            header = panel.locator(".ant-picker-header-view").first
            text = ""
            try:
                text = (header.inner_text(timeout=1000) or "").replace("\n", "")
            except Exception:
                text = ""

            cur_year = target.year
            cur_month = target.month
            ym = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月", text)
            if ym:
                cur_year, cur_month = int(ym.group(1)), int(ym.group(2))
            else:
                y = re.search(r"(20\d{2})", text)
                m = re.search(r"(\d{1,2})\s*月", text)
                if y:
                    cur_year = int(y.group(1))
                if m:
                    cur_month = int(m.group(1))

            if (cur_year, cur_month) == (target.year, target.month):
                return

            if (cur_year, cur_month) > (target.year, target.month):
                btn = panel.locator("button.ant-picker-header-prev-btn")
            else:
                btn = panel.locator("button.ant-picker-header-next-btn")

            # 只点当前可见按钮（range picker 左右两栏可能有隐藏的 super 按钮）
            clicked = False
            for i in range(btn.count()):
                item = btn.nth(i)
                try:
                    if item.is_visible():
                        item.click(timeout=3000)
                        clicked = True
                        break
                except Exception:
                    continue
            if not clicked:
                # 跨年：尝试可见的超级按钮
                super_btn = (
                    panel.locator("button.ant-picker-header-super-prev-btn")
                    if (cur_year, cur_month) > (target.year, target.month)
                    else panel.locator("button.ant-picker-header-super-next-btn")
                )
                for i in range(super_btn.count()):
                    item = super_btn.nth(i)
                    try:
                        if item.is_visible():
                            item.click(timeout=3000)
                            clicked = True
                            break
                    except Exception:
                        continue
            if not clicked:
                raise AssertionError(
                    f"无法导航创建日期到 {target.year}-{target.month:02d}，当前头: {text!r}"
                )
            self.page.wait_for_timeout(180)

    def _click_picker_day(self, panel, day: str) -> bool:
        day = day[:10]
        cell = panel.locator(f"td.ant-picker-cell-in-view[title='{day}']")
        if cell.count() == 0:
            cell = panel.locator(
                "td.ant-picker-cell-in-view:not(.ant-picker-cell-disabled)"
            ).filter(has_text=re.compile(rf"^{int(day[-2:])}$"))
        if cell.count() == 0:
            return False
        try:
            cell.first.click(timeout=3000)
            self.page.wait_for_timeout(200)
            return True
        except Exception:
            return False

    # ---------- Cascader 规范 API（经营类型/行业等，线索与客户共用） ----------

    def select_cascader_levels(
        self,
        selector: str,
        *,
        levels: list[str] | None = None,
        depth: int = 2,
        required: bool = True,
        field_name: str = "级联",
    ) -> None:
        """通用 Cascader：按文案逐级点选，或逐级点第一可见项（JS click 兼容虚拟列表）。"""
        if self.page.locator(selector).count() == 0:
            if required:
                raise AssertionError(f"缺少{field_name}: {selector}")
            return
        try:
            shown0 = (self._ant_select_root(selector).inner_text() or "").strip()
        except Exception:
            shown0 = (self.page.locator(selector).inner_text() or "").strip()
        if shown0 and "请选择" not in shown0 and "请输入" not in shown0:
            return

        self._dismiss_select_dropdown()
        root = self.page.locator(
            f"div.ant-cascader:has({selector}), "
            f"div.ant-select:has({selector}), "
            f".ant-form-item:has({selector}) .ant-cascader, "
            f".ant-form-item:has({selector}) .ant-select"
        )
        target = root.first if root.count() > 0 else self.page.locator(selector).first
        target.scroll_into_view_if_needed(timeout=5000)
        target.click(timeout=8000)
        self.page.wait_for_timeout(600)

        want = [x for x in (levels or []) if x]
        steps = want if want else [""] * max(depth, 1)

        def _active_dropdown():
            return self.page.locator(
                ".ant-cascader-dropdown:not(.ant-cascader-dropdown-hidden), "
                ".ant-select-dropdown:not(.ant-select-dropdown-hidden):has(.ant-cascader-menu)"
            ).last

        for idx, label in enumerate(steps):
            dropdown = _active_dropdown()
            end_t = time.time() + 10
            while time.time() < end_t:
                try:
                    if dropdown.count() > 0 and dropdown.is_visible():
                        break
                except Exception:
                    pass
                self.page.wait_for_timeout(200)
                dropdown = _active_dropdown()
            assert dropdown.count() > 0, f"{field_name}下拉未打开 selector={selector}"

            menus = dropdown.locator(".ant-cascader-menu")
            if menus.count() == 0:
                # 非标准 cascader：点 select option
                opts = dropdown.locator(
                    ".ant-select-item-option:not(.ant-select-item-option-disabled)"
                )
                if label:
                    matched = opts.filter(has_text=label)
                    assert matched.count() > 0, f"{field_name}未找到「{label}」"
                    matched.first.click(timeout=8000)
                else:
                    assert opts.count() > 0, f"{field_name}无选项"
                    opts.first.click(timeout=8000)
                self.page.wait_for_timeout(400)
                continue

            col = menus.first if idx == 0 else menus.last
            # 在列内用 JS 找可点节点（避开虚拟列表不可见 first）
            clicked = col.evaluate(
                """(menu, wantLabel) => {
                    const items = Array.from(menu.querySelectorAll(
                        '.ant-cascader-menu-item:not(.ant-cascader-menu-item-disabled)'
                    ));
                    const isShown = (el) => {
                        const r = el.getBoundingClientRect();
                        return r.width > 0 && r.height > 0;
                    };
                    let target = null;
                    if (wantLabel) {
                        target = items.find(el => {
                            const t = (el.getAttribute('title') || el.textContent || '').trim();
                            return t === wantLabel || t.includes(wantLabel);
                        }) || null;
                    }
                    if (!target) {
                        target = items.find(isShown) || items[0] || null;
                    }
                    if (!target) return {ok: false, texts: []};
                    target.scrollIntoView({block: 'nearest', inline: 'nearest'});
                    target.click();
                    const texts = items.slice(0, 12).map(el =>
                        (el.getAttribute('title') || el.textContent || '').trim()
                    );
                    return {
                        ok: true,
                        picked: (target.getAttribute('title') || target.textContent || '').trim(),
                        texts
                    };
                }""",
                label or "",
            )
            if not clicked or not clicked.get("ok"):
                if required:
                    raise AssertionError(
                        f"{field_name}第{idx + 1}级无选项"
                        + (f"「{label}」" if label else "")
                        + f" texts={(clicked or {}).get('texts')}"
                    )
                break
            self.page.wait_for_timeout(500)

        self._dismiss_select_dropdown()
        try:
            shown = (self._ant_select_root(selector).inner_text() or "").strip()
        except Exception:
            shown = (self.page.locator(selector).inner_text() or "").strip()
        if required and (not shown or "请选择" in shown or "请输入" in shown):
            raise AssertionError(
                f"{field_name}未选中: selector={selector} levels={want} shown={shown!r}"
            )
        self._assert_create_form_still_open(field_name)

    def select_industry_cascade(
        self,
        *,
        level1: str = "食品行业",
        level2: str = "",
    ) -> None:
        """Industry cascader; prefer labeled path, else first visible L1/L2."""
        levels = [x for x in (level1, level2) if x]
        try:
            self.select_cascader_levels(
                "#industryCode",
                levels=levels or None,
                depth=2,
                required=True,
                field_name="行业",
            )
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
        # Fallback: ignore labels, pick first visible at each depth
        try:
            self.select_cascader_levels(
                "#industryCode",
                levels=None,
                depth=2,
                required=True,
                field_name="行业",
            )
            return
        except Exception as exc2:  # noqa: BLE001
            raise AssertionError(
                f"行业 cascader failed label={levels!r} err={last}; fallback={exc2}"
            ) from exc2


    def select_business_type_cascade(
        self,
        *,
        level1: str = "终端客户",
        level2: str = "品牌方",
    ) -> None:
        """经营类型：级联选择一级后再点二级（截图为左右双列）。"""
        sel = "#businessTypeCode"
        assert self.page.locator(sel).count() > 0, f"未找到经营类型 {sel}"
        assert level1 and level2, "经营类型一级/二级不能为空"
        self._dismiss_select_dropdown()

        # 打开控件（可能是 Select 或 Cascader）
        root = self.page.locator(
            f"div.ant-cascader:has({sel}), "
            f"div.ant-select:has({sel}), "
            f".ant-form-item:has({sel}) .ant-cascader, "
            f".ant-form-item:has({sel}) .ant-select"
        )
        target = root.first if root.count() > 0 else self.page.locator(sel).first
        target.scroll_into_view_if_needed(timeout=5000)
        target.click(timeout=8000)
        self.page.wait_for_timeout(500)

        # 一级：级联菜单项 / Select 选项
        l1 = self.page.locator(
            ".ant-cascader-dropdown:not(.ant-cascader-dropdown-hidden) "
            ".ant-cascader-menu-item:visible, "
            ".ant-cascader-menus:visible .ant-cascader-menu-item:visible, "
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden) "
            ".ant-select-item-option:not(.ant-select-item-option-disabled), "
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden) "
            "[class*='cascader'] [class*='menu-item'], "
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden) li"
        ).filter(has_text=re.compile(rf"{re.escape(level1)}"))
        # 优先精确匹配「终端客户」避免点到「非终端客户」
        exact_l1 = l1.filter(has_text=re.compile(rf"^{re.escape(level1)}$"))
        pick_l1 = exact_l1.first if exact_l1.count() > 0 else l1.first
        assert l1.count() > 0, f"经营类型一级未找到「{level1}」"
        pick_l1.click(timeout=8000)
        self.page.wait_for_timeout(500)

        # 二级：右侧子菜单
        l2 = self.page.locator(
            ".ant-cascader-dropdown:not(.ant-cascader-dropdown-hidden) "
            ".ant-cascader-menu-item:visible, "
            ".ant-cascader-menus:visible .ant-cascader-menu-item:visible, "
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden) "
            ".ant-select-item-option:not(.ant-select-item-option-disabled), "
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden) "
            "[class*='cascader'] [class*='menu-item'], "
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden) li"
        ).filter(has_text=re.compile(rf"{re.escape(level2)}"))
        exact_l2 = l2.filter(has_text=re.compile(rf"^{re.escape(level2)}$"))
        pick_l2 = exact_l2.first if exact_l2.count() > 0 else l2.first
        assert l2.count() > 0, (
            f"经营类型二级未找到「{level2}」（请先确认一级「{level1}」已展开）"
        )
        pick_l2.click(timeout=8000)
        self.page.wait_for_timeout(500)

        # 兼容：若仍有独立的二级字段
        if self.page.locator("#businessSubTypeCode").count() > 0:
            shown_sub = ""
            try:
                shown_sub = (
                    self._ant_select_root("#businessSubTypeCode").inner_text() or ""
                )
            except Exception:
                shown_sub = ""
            if level2 not in shown_sub and "请选择" in shown_sub:
                self._type_select_keyword(
                    "#businessSubTypeCode", level2, required=False
                )

        self._dismiss_select_dropdown()
        shown = ""
        try:
            shown = (self._ant_select_root(sel).inner_text() or "").strip()
        except Exception:
            shown = (self.page.locator(sel).inner_text() or "").strip()
        assert ("请选择" not in shown) and (
            level1[:2] in shown or level2 in shown or len(shown) > 0
        ), f"经营类型未选中二级: expect={level1}/{level2} shown={shown!r}"
        self._assert_create_form_still_open("经营类型级联")

    # ---------- 列表 / 详情 / 新建 ----------

    def open_row_by_name(self, name: str) -> None:
        link = self.page.get_by_role("link", name=name)
        if link.count() == 0:
            link = self.page.locator(".ant-table-tbody a").filter(has_text=name)
        assert link.count() > 0, f"列表未找到机会: {name}"
        link.first.click()
        self.page.wait_for_timeout(1200)

    def close_drawer(self) -> None:
        closer = self.page.locator("button.ant-drawer-close")
        if closer.count() > 0 and closer.first.is_visible():
            closer.first.click()
            self.page.wait_for_timeout(500)

    def open_create_form(self) -> None:
        self.close_overlays()
        create_entry = self.page.locator("button.ant-btn-default").filter(
            has_text=re.compile(r"新\s*建")
        )
        if create_entry.count() == 0:
            create_entry = self.page.get_by_role("button", name=re.compile(r"新\s*建"))
        assert create_entry.count() > 0, "未找到「新建」按钮"
        create_entry.first.click()
        self.page.wait_for_timeout(800)

        name_field = self.page.locator("#name")
        if name_field.count() > 0 and name_field.first.is_visible():
            return

        # 录制路径：新建 → 下拉/按钮「+新建销售机会」
        menu = self.page.locator(
            ".ant-dropdown:not(.ant-dropdown-hidden) .ant-dropdown-menu-item, "
            ".ant-dropdown:not(.ant-dropdown-hidden) li, "
            ".ant-dropdown:not(.ant-dropdown-hidden) button"
        ).filter(has_text=re.compile(r"新建销售机会"))
        if menu.count() > 0:
            menu.first.click(force=True)
            self.page.wait_for_timeout(1000)
        else:
            primary = self.page.locator("button.ant-btn-primary").filter(
                has_text=re.compile(r"新建销售机会")
            )
            if primary.count() > 0:
                primary.first.click(force=True)
                self.page.wait_for_timeout(1000)

        try:
            self.page.locator("#name").first.wait_for(state="visible", timeout=15000)
        except PlaywrightTimeoutError as exc:
            # 抽屉可能已开但字段 id 不同，附带可见文案便于排查
            drawer = self.page.locator(".ant-drawer-open")
            hint = drawer.inner_text()[:300] if drawer.count() > 0 else "(no drawer)"
            raise AssertionError(f"新建销售机会表单未打开（无 #name）。drawer={hint}") from exc

    def _pick_first_visible_day(self) -> None:
        day = self.page.locator(
            ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden) "
            "td.ant-picker-cell-in-view:not(.ant-picker-cell-disabled)"
        )
        if day.count() == 0:
            day = self.page.locator(
                "td.ant-picker-cell-in-view:not(.ant-picker-cell-disabled)"
            )
        assert day.count() > 0, "日期面板无可选日期"
        day.first.click()
        self.page.wait_for_timeout(400)

    def fill_create_basic(
        self,
        *,
        name: str,
        customer_keyword: str,
        amount: str,
    ) -> None:
        self.page.locator("#name").fill(name)

        # 客户：必须搜索后选返回项
        self.select_searchable("#customerId", customer_keyword)
        # 等客户下拉完全收起，避免挡住后续枚举 Select
        self.page.wait_for_timeout(500)
        self.page.locator("#name").click(force=True)
        self.page.wait_for_timeout(300)

        # 机会类型 / 阶段 / 币种：本地枚举，点选即可
        self.select_plain_first("#opportunityType")
        self.select_plain_first("#saleStage")

        if self.page.locator("#contactPersonId").count() > 0:
            # 联系人依赖客户，选项由接口返回；有搜索则走 searchable，否则点第一项
            contact_root = self._ant_select_root("#contactPersonId")
            has_search = (
                contact_root.locator("input.ant-select-selection-search-input").count()
                > 0
            )
            if has_search:
                # 联系人列表通常已按客户过滤，打开后选第一项即可
                dropdown = self._open_select_dropdown("#contactPersonId")
                self._pick_dropdown_option(dropdown, None)
            else:
                self.select_plain_first("#contactPersonId")

        self.page.locator("#expectedTransactionDate").click()
        self.page.wait_for_timeout(400)
        next_btn = self.page.locator(
            ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden) "
            "button.ant-picker-header-next-btn"
        )
        if next_btn.count() > 0:
            next_btn.first.click()
            self.page.wait_for_timeout(200)
        self._pick_first_visible_day()

        self.page.locator("#expectedTransactionAmount").fill(amount)

        if self.page.locator("#currency").count() > 0:
            self.select_plain_first("#currency")

    def add_generic_product(self, *, price: str, count: str) -> None:
        self.click_toolbar_button(r"\+?\s*添加通用商品|添加通用商品")
        self.page.wait_for_timeout(800)
        checkbox = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none']) input.ant-checkbox-input, "
            ".ant-drawer-open input.ant-checkbox-input"
        )
        if checkbox.count() == 0:
            checkbox = self.page.locator(".ant-table-tbody input.ant-checkbox-input")
        assert checkbox.count() > 0, "商品选择弹窗未找到可勾选商品"
        target = checkbox.nth(1) if checkbox.count() > 1 else checkbox.first
        target.check(force=True)
        self.page.wait_for_timeout(300)
        self.click_toolbar_button(r"确\s*认")
        self.page.wait_for_timeout(600)

        price_input = self.page.locator("#productList_0_salePrice")
        count_input = self.page.locator("#productList_0_saleCount")
        assert price_input.count() > 0, "未出现商品售价输入框"
        price_input.fill(price)
        count_input.fill(count)

    def click_edit(self) -> None:
        self.click_toolbar_button(r"编\s*辑")
        self.page.wait_for_timeout(800)

    def fill_remark(self, remark: str) -> None:
        remark_input = self.page.locator("#remark")
        assert remark_input.count() > 0, "编辑表单未找到备注字段"
        remark_input.fill(remark)

    def delete_row_by_name(self, name: str) -> None:
        row = self.page.locator(".ant-table-tbody tr").filter(has_text=name)
        assert row.count() > 0, f"删除前列表未找到机会: {name}"
        delete_btn = row.first.get_by_role("button", name=re.compile(r"删\s*除"))
        if delete_btn.count() == 0:
            delete_btn = row.first.locator("button, a").filter(
                has_text=re.compile(r"删\s*除")
            )
        assert delete_btn.count() > 0, f"行内未找到删除按钮: {name}"
        delete_btn.first.click()
        self.page.wait_for_timeout(500)
        self.click_toolbar_button(r"确\s*认|确\s*定")
        self.page.wait_for_timeout(1200)

    def assert_row_exists(self, name: str) -> None:
        link = self.page.locator(".ant-table-tbody").get_by_text(name, exact=False)
        assert link.count() > 0, f"列表应存在机会: {name}"

    def assert_row_absent(self, name: str) -> None:
        self.page.wait_for_timeout(800)
        link = self.page.locator(".ant-table-tbody").get_by_text(name, exact=False)
        assert link.count() == 0, f"列表仍存在已删除机会: {name}"
