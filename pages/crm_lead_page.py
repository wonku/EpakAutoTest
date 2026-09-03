from __future__ import annotations

import re
import time
from datetime import date
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from config.settings import (
    CRM_UI_CUSTOMER_BUSINESS_TYPE_L1,
    CRM_UI_CUSTOMER_BUSINESS_TYPE_L2,
    CRM_UI_CUSTOMER_CITY,
    CRM_UI_CUSTOMER_CONTACT_POSITION,
    CRM_UI_CUSTOMER_DISTRICT,
    CRM_UI_CUSTOMER_INDUSTRY_L1,
    CRM_UI_CUSTOMER_INDUSTRY_L2,
    CRM_UI_CUSTOMER_PROVINCE,
    CRM_UI_LEAD_COMPANY_OPTION,
)
from pages.crm_customer_page import CrmCustomerPage


class CrmLeadPage(CrmCustomerPage):
    """销售线索页（对齐录制 20260807-160515：新建 → 筛选 → 详情 → 删除回滚）。

    复用客户页已验证能力：工商选企、级联、附件等待上传、省市区。
    同公司重复弹窗走 continue_create_if_duplicate（继续创建）。
    """

    def open_create_form(self) -> None:
        self.close_overlays()
        create = self.page.get_by_role(
            "button", name=re.compile(r"新建线索|新增线索")
        )
        if create.count() == 0:
            create = self.page.locator("button.ant-btn-primary").filter(
                has_text=re.compile(r"新建线索|新增线索")
            )
        assert create.count() > 0, "未找到「新建线索」按钮"
        create.first.click()
        self.page.wait_for_timeout(800)
        try:
            self.page.locator("#name").first.wait_for(state="visible", timeout=15000)
        except PlaywrightTimeoutError as exc:
            raise AssertionError("打开新建线索表单后未出现 #name") from exc

    def _fill_if_present(self, selector: str, value: str) -> None:
        loc = self.page.locator(selector)
        if loc.count() == 0 or value is None:
            return
        loc.first.scroll_into_view_if_needed(timeout=3000)
        loc.first.fill(str(value))
        self.page.wait_for_timeout(200)

    def _select_if_present(
        self,
        selector: str,
        *,
        keyword: str = "",
        first: bool = False,
        multi: bool = False,
    ) -> None:
        if self.page.locator(selector).count() == 0:
            return
        if keyword:
            self.select_searchable(selector, keyword, multi=multi)
        elif first:
            self.select_plain_first(selector)

    def try_qichacha_backfill(self, company_keyword: str) -> str:
        """兼容旧名：走工商选企，优先点选 CRM_UI_LEAD_COMPANY_OPTION。"""
        return self.pick_company_via_qichacha(
            company_keyword,
            prefer_option=CRM_UI_LEAD_COMPANY_OPTION,
        )

    def _duplicate_modal(self):
        """定位「线索重复」弹窗（取最上层可见）。

        现网弹层带 CSS Modules：`repeat_wrapper___xxxx`，会挡住表单点击。
        """
        title_re = re.compile(r"线索\s*重复|可能重复|是否要创建")

        # 1) 专用查重壳
        for sel in ("[class*='repeat_wrapper']", ".ant-modal-wrap[class*='repeat']"):
            hosts = self.page.locator(sel)
            for i in range(hosts.count() - 1, -1, -1):
                m = hosts.nth(i)
                try:
                    if m.is_visible():
                        return m
                except Exception:
                    continue

        # 2) 普通 modal + 查重文案
        for sel in (".ant-modal-wrap", ".ant-modal-root", "[role='dialog']", ".ant-modal"):
            hosts = self.page.locator(sel).filter(has_text=title_re)
            for i in range(hosts.count() - 1, -1, -1):
                m = hosts.nth(i)
                try:
                    if m.is_visible():
                        return m
                except Exception:
                    continue
        return None

    def continue_create_if_duplicate(
        self,
        *,
        timeout_ms: int = 12000,
        allow_manual_sec: int = 60,
    ) -> bool:
        """同公司线索重复弹窗：点「继续创建」。

        工商回填/点保存都可能弹出；不点掉会挡住后续询盘、附件填写。
        自动点击失败时，会提示你在浏览器里手动点「继续创建」再继续跑。
        """
        cont_re = re.compile(r"继\s*续\s*创\s*建")
        deadline = time.time() + timeout_ms / 1000
        saw = False
        while time.time() < deadline:
            modal = self._duplicate_modal()
            if modal is None:
                self.page.wait_for_timeout(250)
                continue
            saw = True
            print("[lead] 发现「线索重复」弹窗，准备点「继续创建」", flush=True)

            # 优先：弹窗内主按钮（蓝色）
            candidates = [
                modal.locator("button.ant-btn-primary").filter(has_text=cont_re),
                modal.locator("button").filter(has_text=cont_re),
                modal.get_by_role("button", name=cont_re),
                self.page.locator("button.ant-btn-primary").filter(has_text=cont_re),
                self.page.get_by_role("button", name=cont_re),
            ]
            clicked = False
            for cand in candidates:
                try:
                    if cand.count() == 0:
                        continue
                    btn = cand.last
                    if not btn.is_visible():
                        continue
                    print(
                        f"[lead] 点击继续创建 text={(btn.inner_text() or '').strip()!r}",
                        flush=True,
                    )
                    try:
                        btn.click(timeout=3000)
                    except Exception:
                        try:
                            btn.click(force=True, timeout=3000)
                        except Exception:
                            btn.evaluate("el => el.click()")
                    clicked = True
                    break
                except Exception as exc:
                    print(f"[lead] 继续创建点击尝试失败: {exc}", flush=True)
                    continue

            self.page.wait_for_timeout(800)
            if self._duplicate_modal() is None:
                print("[lead] 「线索重复」已关闭", flush=True)
                return True
            if clicked:
                # 再强制点一次主按钮
                try:
                    modal2 = self._duplicate_modal()
                    if modal2 is not None:
                        primary = modal2.locator("button.ant-btn-primary")
                        if primary.count() > 0:
                            primary.last.evaluate("el => el.click()")
                            self.page.wait_for_timeout(800)
                except Exception:
                    pass
                if self._duplicate_modal() is None:
                    print("[lead] 「线索重复」已关闭", flush=True)
                    return True
            break  # 进入手动兜底

        if not saw and self._duplicate_modal() is None:
            return False

        if allow_manual_sec > 0 and self._duplicate_modal() is not None:
            print(
                f"[lead] 自动未点上「继续创建」，请在浏览器里手动点一下"
                f"（等待 {allow_manual_sec}s）…",
                flush=True,
            )
            end = time.time() + allow_manual_sec
            while time.time() < end:
                if self._duplicate_modal() is None:
                    print("[lead] 已检测到弹窗关闭（手动或自动）", flush=True)
                    return True
                self.page.wait_for_timeout(500)
            raise AssertionError(
                "「线索重复」弹窗仍在：自动点击失败且等待手动点击超时"
            )
        return saw and self._duplicate_modal() is None

    def _block_create_form_submit(self, block: bool) -> None:
        """填表阶段禁止表单 submit / 禁用页脚「确定」，避免 Enter 或误点触发查重。

        仅在 confirm_save 门禁通过后解除。
        """
        self.page.evaluate(
            """(block) => {
                const KEY = '__pyautotestBlockLeadSubmit';
                const disableFooter = (disabled) => {
                    const buttons = document.querySelectorAll(
                        '.ant-modal-footer button, .ant-drawer-footer button, .ant-pro-footer-bar button'
                    );
                    buttons.forEach((b) => {
                        const t = (b.innerText || '').replace(/\\s+/g, '');
                        if (!/确定|确认|保存|提交/.test(t)) return;
                        if (/继续|取消/.test(t)) return;
                        if (disabled) {
                            b.setAttribute('data-auto-disabled', '1');
                            b.setAttribute('disabled', 'true');
                            b.classList.add('ant-btn-disabled');
                        } else if (b.getAttribute('data-auto-disabled') === '1') {
                            b.removeAttribute('data-auto-disabled');
                            b.removeAttribute('disabled');
                            b.classList.remove('ant-btn-disabled');
                        }
                    });
                };
                if (block) {
                    if (!window[KEY]) {
                        window[KEY] = (e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.warn('[pyautotest] blocked lead form submit during fill');
                        };
                        document.addEventListener('submit', window[KEY], true);
                    }
                    disableFooter(true);
                } else {
                    if (window[KEY]) {
                        document.removeEventListener('submit', window[KEY], true);
                        window[KEY] = null;
                    }
                    disableFooter(false);
                }
            }""",
            block,
        )
        print(
            f"[lead] {'锁定' if block else '解锁'}新建表单提交（填表期防误点确定）",
            flush=True,
        )

    def cancel_create_if_duplicate(self, *, timeout_ms: int = 3000) -> bool:
        """若误点保存导致查重弹窗，点「取消创建」回到新建表单继续填。

        填表未完成时禁止点「继续创建」（会直接落库且询盘/附件未维护）。
        """
        deadline = time.time() + timeout_ms / 1000
        cancel_re = re.compile(r"取\s*消\s*创\s*建")
        while time.time() < deadline:
            modal = self._duplicate_modal()
            if modal is None:
                self.page.wait_for_timeout(200)
                continue
            print("[lead] 填表阶段出现查重弹窗，点「取消创建」回到表单", flush=True)
            btn = modal.locator("button").filter(has_text=cancel_re)
            if btn.count() == 0:
                btn = self.page.get_by_role("button", name=cancel_re)
            assert btn.count() > 0, "查重弹窗无「取消创建」"
            try:
                btn.last.click(timeout=5000)
            except Exception:
                btn.last.click(force=True, timeout=5000)
            self.page.wait_for_timeout(800)
            assert self._duplicate_modal() is None, "点「取消创建」后查重弹窗仍在"
            return True
        return False

    def _attachment_form_item(self):
        """定位「上传附件」表单项（避免点到其它 Upload）。"""
        item = self.page.locator(".ant-form-item").filter(
            has=self.page.locator(
                ".ant-form-item-label", has_text=re.compile(r"上传附件")
            )
        )
        if item.count() == 0:
            item = self.page.locator(".ant-form-item:has(#attachments)")
        return item

    def select_key_decision_maker(self, value: str = "是") -> None:
        """是否关键决策人：必须显式点选，不能停在默认「否」。"""
        text = (value or "是").strip() or "是"
        selectors = (
            "#isKeyDecisionMaker",
            "#keyDecisionMaker",
            "#decisionMakerFlag",
            "#isKeyDecision",
        )
        for sel in selectors:
            if self.page.locator(sel).count() == 0:
                continue
            print(f"[lead] 选择是否关键决策人 → {text!r} ({sel})", flush=True)
            self._dismiss_select_dropdown()
            # 枚举：打开后按文案点（是/否），禁止 select_plain_first 误停在默认否
            dropdown = self._open_select_dropdown(sel)
            option = self._dropdown_option_locator(dropdown)
            for _ in range(16):
                if option.count() > 0:
                    break
                self.page.wait_for_timeout(200)
                option = self._dropdown_option_locator(dropdown)
            assert option.count() > 0, f"是否关键决策人下拉无选项: {sel}"
            matched = option.filter(has_text=re.compile(rf"^{re.escape(text)}$"))
            if matched.count() == 0:
                matched = option.filter(has_text=text)
            assert matched.count() > 0, f"是否关键决策人未找到选项「{text}」"
            self._click_dropdown_option_node(matched.first)
            self.page.wait_for_timeout(400)
            self._dismiss_select_dropdown()
            shown = (self._ant_select_root(sel).inner_text() or "").replace("\n", " ").strip()
            assert text in shown, f"是否关键决策人未选中: expect={text!r} shown={shown!r}"
            print(f"[lead] 是否关键决策人已选: {shown!r}", flush=True)
            return

        # 按 label 兜底（Radio）
        label_item = self.page.locator(".ant-form-item").filter(
            has=self.page.locator(
                ".ant-form-item-label", has_text=re.compile(r"关键决策人")
            )
        )
        if label_item.count() == 0:
            print("[lead] 未找到是否关键决策人字段，跳过", flush=True)
            return
        radio = label_item.first.locator(".ant-radio-wrapper, label").filter(
            has_text=re.compile(rf"^{re.escape(text)}$|{re.escape(text)}")
        )
        if radio.count() > 0:
            radio.first.click(timeout=5000)
            self.page.wait_for_timeout(300)
            print(f"[lead] 是否关键决策人(radio)已点: {text!r}", flush=True)
            return
        raise AssertionError("未找到是否关键决策人可操作控件")

    def upload_attachment_if_present(self, file_path: Path) -> None:
        """上传附件到「上传附件」表单项，等 upload 接口 + done 态真实文件名。

        注意：仅列表短暂出现文件名不够；必须 `.ant-upload-list-item-done`，
        否则详情里仍可能是空的「上传附件」占位。
        """
        path = Path(file_path)
        assert path.is_file(), f"附件文件不存在: {path}"
        assert path.stat().st_size > 500, (
            f"附件过小疑似无效占位文件: {path} size={path.stat().st_size}"
        )
        self.cancel_create_if_duplicate(timeout_ms=1500)

        try:
            self.page.get_by_text(re.compile(r"^上传附件$")).first.scroll_into_view_if_needed(
                timeout=5000
            )
        except Exception:
            try:
                self.page.get_by_text(re.compile(r"上传附件")).first.scroll_into_view_if_needed(
                    timeout=5000
                )
            except Exception:
                pass

        item = self._attachment_form_item()
        assert item.count() > 0, "未找到「上传附件」表单项"
        host = item.first

        # 不要先点 Upload 触发原生对话框；直接对隐藏 input set_input_files（客户页同款）
        file_input = host.locator("input[type='file']")
        if file_input.count() == 0:
            file_input = self.page.locator(
                ".ant-form-item:has-text('上传附件') input[type='file']"
            )
        assert file_input.count() > 0, "上传附件区域无 file input"

        print(
            f"[lead] 开始上传真实文件: {path} size={path.stat().st_size}",
            flush=True,
        )
        upload_meta = {"url": "", "status": 0}

        def _is_upload(resp) -> bool:
            u = (resp.url or "").lower()
            return (
                resp.request.method == "POST"
                and resp.ok
                and (
                    "file/file/upload" in u
                    or "/file/upload" in u
                    or "uploadfile" in u
                )
            )

        try:
            with self.page.expect_response(_is_upload, timeout=30000) as info:
                file_input.first.set_input_files(str(path))
            resp = info.value
            upload_meta["status"] = resp.status
            try:
                body = resp.json()
                upload_meta["url"] = str(
                    body.get("data")
                    or (body.get("result") or {})
                    or body.get("url")
                    or ""
                )[:200]
            except Exception:
                upload_meta["url"] = (resp.url or "")[:120]
            print(
                f"[lead] upload 接口成功 status={upload_meta['status']} data={upload_meta['url']!r}",
                flush=True,
            )
        except Exception as exc:
            print(f"[lead] 严格 upload 等待失败 ({exc})，回退客户页封装", flush=True)
            ok = self._upload_form_item_file(host, path)
            if not ok:
                ok = self.upload_by_field_label("上传附件", path)
            assert ok, f"附件上传失败: {path.name}"

        # 必须出现 done 态；picture-card 可能只有缩略图无文件名文案
        end = time.time() + 30
        shown = ""
        while time.time() < end:
            # 作用域：表单项内；若 list 挂在外层，再扩到整页「上传附件」附近
            scopes = [host]
            page_att = self.page.locator(
                ".ant-form-item:has-text('上传附件'), "
                ".ant-upload-wrapper, .ant-upload-picture-card-wrapper"
            )
            if page_att.count() > 0:
                scopes.append(page_att.first)

            for scope in scopes:
                done_items = scope.locator(
                    ".ant-upload-list-item-done, .ant-upload-list-item-success"
                )
                if done_items.count() == 0:
                    # 上传中：有 list-item + img/url 也算进展
                    any_item = scope.locator(".ant-upload-list-item")
                    if any_item.count() > 0:
                        for i in range(min(any_item.count(), 6)):
                            node = any_item.nth(i)
                            cls = (node.get_attribute("class") or "")
                            if "error" in cls or "uploading" in cls:
                                continue
                            img = node.locator("img[src]")
                            href = node.locator("a[href]")
                            text = (node.inner_text() or "").strip().replace("\n", " ")
                            if img.count() > 0:
                                src = img.first.get_attribute("src") or ""
                                if src.startswith("http") or src.startswith("blob:") or "data:image" in src:
                                    shown = text or f"[img]{src[:80]}"
                                    break
                            if href.count() > 0:
                                h = href.first.get_attribute("href") or ""
                                if h.startswith("http"):
                                    shown = text or f"[a]{h[:80]}"
                                    break
                            if text and text not in {"上传文件", "点击上传", "上传附件"} and "请上传" not in text:
                                if path.name in text or path.stem in text or "." in text:
                                    shown = text
                                    break
                    if shown:
                        break
                    continue

                for i in range(min(done_items.count(), 6)):
                    node = done_items.nth(i)
                    text = (node.inner_text() or "").strip().replace("\n", " ")
                    name_el = node.locator(".ant-upload-list-item-name, a")
                    if name_el.count() > 0:
                        text = (name_el.first.inner_text() or text).strip()
                    img = node.locator("img[src]")
                    if img.count() > 0:
                        src = img.first.get_attribute("src") or ""
                        if src:
                            shown = text or f"[img]{src[:80]}"
                            break
                    if not text or text in {"上传文件", "点击上传", "上传附件"}:
                        # done 但无文案：仍算成功（picture-card）
                        shown = f"[done]#{i}"
                        break
                    if "请上传" in text:
                        continue
                    if path.name in text or path.stem in text or "." in text or len(text) >= 2:
                        shown = text
                        break
                if shown:
                    break
            if shown:
                break
            if host.locator(".ant-upload-list-item-error").count() > 0:
                raise AssertionError("附件上传失败（列表 error 态）")
            self.page.wait_for_timeout(400)

        if not shown:
            # 诊断：dump 上传区 HTML，便于确认是否 picture-card / 错误作用域
            try:
                html = host.inner_html(timeout=2000)[:1500]
            except Exception:
                html = "<unavailable>"
            print(f"[lead] 附件 DOM dump: {html!r}", flush=True)
        assert shown, (
            f"附件未进入 done 态或无缩略/文件名（详情会仍为空）。file={path.name} "
            f"upload={upload_meta}"
        )
        # 再等表单把 url 写入（客户页经验）
        self.page.wait_for_timeout(2000)
        print(f"[lead] 附件上传完成 done-list={shown!r}", flush=True)

    def assert_inquiry_and_attachment_ready(self, *, remark: str = "", require_attachment: bool = True) -> None:
        """保存前门禁：询盘/备注/附件都维护完，且没有挡着的查重弹窗。"""
        # 误触保存时先取消创建
        self.cancel_create_if_duplicate(timeout_ms=2000)
        assert self._duplicate_modal() is None, (
            "仍有「线索重复」弹窗挡住表单；填表未完成前应「取消创建」而非「继续创建」"
        )

        if self.page.locator("#inquiryKeywordCode").count() > 0:
            shown = (
                self._ant_select_root("#inquiryKeywordCode").inner_text() or ""
            ).replace("\n", " ").strip()
            assert shown and "请选择" not in shown, f"保存前询盘关键词未维护: {shown!r}"

        if remark and self.page.locator("#remark").count() > 0:
            try:
                cur = (self.page.locator("#remark").first.input_value(timeout=1500) or "").strip()
            except Exception:
                cur = (self.page.locator("#remark").first.inner_text() or "").strip()
            assert cur, f"保存前备注未维护: {cur!r}"

        if require_attachment:
            item = self._attachment_form_item()
            assert item.count() > 0, "保存前未找到上传附件表单项"
            done = item.first.locator(
                ".ant-upload-list-item-done, .ant-upload-list-item-success"
            )
            assert done.count() > 0 or self._upload_list_has_file(item.first), (
                "保存前附件未进入 done 态（详情会仍显示空上传框）"
            )
            assert self._upload_list_has_file(item.first), (
                "保存前附件列表无有效文件名/缩略图，请等待上传完成"
            )
        # 是否关键决策人：保存前必须是「是」，不能仍是默认「否」
        for sel in ("#isKeyDecisionMaker", "#keyDecisionMaker", "#decisionMakerFlag"):
            if self.page.locator(sel).count() == 0:
                continue
            shown = (self._ant_select_root(sel).inner_text() or "").replace("\n", " ").strip()
            assert re.search(r"(^|[^\u4e00-\u9fff])是([^\u4e00-\u9fff]|$)", shown) or shown == "是", (
                f"保存前关键决策人仍非「是」: {shown!r}"
            )
            assert not re.search(r"(^|[^\u4e00-\u9fff])否([^\u4e00-\u9fff]|$)", shown), (
                f"保存前关键决策人仍是「否」: {shown!r}"
            )
            break
        print("[lead] 保存前门禁通过：询盘/附件/关键决策人已就绪", flush=True)

    def confirm_save(self) -> None:
        """新建线索：询盘+附件就绪后再解锁并点「确定」；查重后再点「继续创建」。"""
        self._dismiss_select_dropdown()
        self._stay_on_form_if_discard_prompt()
        # 填表阶段若已误出查重，先取消创建
        self.cancel_create_if_duplicate(timeout_ms=3000)

        def _create_form_open() -> bool:
            try:
                return (
                    self.page.locator("#name").count() > 0
                    and self.page.locator("#name").first.is_visible()
                )
            except Exception:
                return False

        assert _create_form_open(), (
            "保存前新建表单已关闭，询盘/附件可能未维护完就被提交了"
        )
        # 门禁：询盘/附件未好绝不能点确定
        remark_val = ""
        try:
            if self.page.locator("#remark").count() > 0:
                remark_val = (
                    self.page.locator("#remark").first.input_value(timeout=1000) or ""
                ).strip()
        except Exception:
            remark_val = ""
        self.assert_inquiry_and_attachment_ready(
            remark=remark_val, require_attachment=True
        )
        # 门禁通过后再允许点击确定
        self._block_create_form_submit(False)

        pattern = re.compile(r"确\s*定|确\s*认|保\s*存|提\s*交|创\s*建")
        skip_btn = re.compile(r"继\s*续|取\s*消|查\s*询|重\s*置|新\s*建线索")
        create_host = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none']), "
            ".ant-drawer-open, "
            "[class*='modal']"
        ).filter(has_text=re.compile(r"新建线索|编辑线索|基础信息"))

        # 先滚到表单底部，露出页脚按钮
        try:
            if create_host.count() > 0:
                create_host.last.evaluate(
                    """el => {
                        const box = el.querySelector('.ant-modal-body, .ant-drawer-body, .ant-spin-container') || el;
                        box.scrollTop = box.scrollHeight;
                    }"""
                )
                self.page.wait_for_timeout(400)
        except Exception:
            pass

        candidates = []
        if create_host.count() > 0:
            host = create_host.last
            candidates.extend(
                [
                    host.locator(
                        ".ant-modal-footer button.ant-btn-primary, "
                        ".ant-drawer-footer button.ant-btn-primary, "
                        ".ant-pro-footer-bar button.ant-btn-primary"
                    ),
                    host.locator(
                        ".ant-modal-footer button, .ant-drawer-footer button, "
                        ".ant-pro-footer-bar button"
                    ),
                    host.locator("button.ant-btn-primary"),
                    host.get_by_role("button", name=pattern),
                ]
            )
        candidates.extend(
            [
                self.page.locator(
                    ".ant-modal-footer button.ant-btn-primary, "
                    ".ant-drawer-footer button.ant-btn-primary, "
                    ".ant-pro-footer-bar button.ant-btn-primary"
                ).filter(has_text=pattern),
                self.page.locator("button.ant-btn-primary").filter(has_text=pattern),
                self.page.get_by_role("button", name=pattern),
            ]
        )

        clicked = False
        for loc in candidates:
            try:
                n = loc.count()
            except Exception:
                continue
            if n == 0:
                continue
            for i in range(n - 1, -1, -1):
                item = loc.nth(i)
                try:
                    if not item.is_visible():
                        continue
                    text = (item.inner_text() or "").strip().replace("\n", "")
                    if skip_btn.search(text):
                        continue
                    if text and not pattern.search(text):
                        continue
                    # 跳过「线索重复」弹窗内按钮
                    in_modal = item.locator(
                        "xpath=ancestor::div[contains(@class,'ant-modal')][1]"
                    )
                    if in_modal.count() > 0:
                        modal_text = in_modal.inner_text() or ""
                        if re.search(r"线索\s*重复|继续创建|取消创建", modal_text):
                            continue
                    try:
                        item.scroll_into_view_if_needed(timeout=3000)
                    except Exception:
                        pass
                    print(f"[lead] 点击新建保存按钮 text={text!r}", flush=True)
                    try:
                        item.click(timeout=8000)
                    except Exception:
                        try:
                            item.click(force=True, timeout=5000)
                        except Exception:
                            item.evaluate("el => el.click()")
                    clicked = True
                    break
                except AssertionError:
                    raise
                except Exception:
                    continue
            if clicked:
                break

        if not clicked:
            # 打印可见按钮，方便对齐文案
            try:
                labels = []
                btns = self.page.locator("button:visible")
                for i in range(min(btns.count(), 25)):
                    t = (btns.nth(i).inner_text() or "").strip().replace("\n", " ")
                    if t:
                        labels.append(t)
                print(f"[lead] 当前可见按钮: {labels!r}", flush=True)
            except Exception:
                pass

            # 再试：Ant 常见「确 定」带空格 + 页脚任意主按钮（排除取消/继续）
            more = [
                self.page.get_by_role("button", name=re.compile(r"^确\s*定$")),
                self.page.locator(".ant-modal-footer button.ant-btn-primary"),
                self.page.locator(".ant-pro-footer-bar button.ant-btn-primary"),
                self.page.locator(
                    "div[class*='footer'] button.ant-btn-primary, "
                    "div[class*='Footer'] button.ant-btn-primary"
                ),
            ]
            for loc in more:
                try:
                    if loc.count() == 0:
                        continue
                    for i in range(loc.count() - 1, -1, -1):
                        item = loc.nth(i)
                        if not item.is_visible():
                            continue
                        text = (item.inner_text() or "").strip().replace("\n", "")
                        if skip_btn.search(text):
                            continue
                        print(f"[lead] 二次兜底点击 text={text!r}", flush=True)
                        try:
                            item.click(force=True, timeout=5000)
                        except Exception:
                            item.evaluate("el => el.click()")
                        clicked = True
                        break
                except Exception:
                    continue
                if clicked:
                    break

        if not clicked:
            print(
                "[lead] 自动未找到「确定」，请在浏览器手动点新建线索「确定」"
                "（等待 90s，表单关闭即继续）…",
                flush=True,
            )
            end = time.time() + 90
            while time.time() < end:
                # 新建表单消失 / 回到列表
                still = self.page.get_by_text(re.compile(r"新建线索"))
                dup = self._duplicate_modal()
                if dup is not None:
                    self.continue_create_if_duplicate(
                        timeout_ms=3000, allow_manual_sec=60
                    )
                try:
                    name_visible = (
                        self.page.locator("#name").count() > 0
                        and self.page.locator("#name").first.is_visible()
                    )
                except Exception:
                    name_visible = False
                if not name_visible:
                    print("[lead] 检测到新建表单已关闭（手动确定成功）", flush=True)
                    clicked = True
                    break
                self.page.wait_for_timeout(500)

        if not clicked:
            raise AssertionError("未找到新建线索「确定/保存」按钮")

        self.page.wait_for_timeout(1000)
        if self._stay_on_form_if_discard_prompt():
            raise AssertionError(
                "点击确定后出现「未保存将失效」，说明未真正触发保存"
            )
        # 同公司已有线索：必须点「继续创建」
        self.continue_create_if_duplicate(timeout_ms=25000, allow_manual_sec=90)

    def rollback_row_by_name(self, name: str) -> None:
        """UI 回滚造数线索：我的线索优先，找不到再扫公海池后删除。"""
        self.reset_lead_search()
        try:
            self.switch_lead_list_tab("我的线索")
        except AssertionError:
            pass
        self.search_leads(name=name)
        row = self.page.locator(".ant-table-tbody tr").filter(has_text=name)
        if row.count() == 0:
            self.search_public_sea_leads(name=name)
        self.delete_row_by_name(name)
        self.search_leads(name=name)
        self.assert_row_absent(name)

    def delete_row_by_name(self, name: str) -> None:
        """列表按姓名删除线索（行内删除 → 确认）。入口若与现网不一致再按录制对齐。"""
        row = self.page.locator(".ant-table-tbody tr").filter(has_text=name)
        assert row.count() > 0, f"删除前列表未找到线索: {name}"

        delete_btn = row.first.get_by_role("button", name=re.compile(r"删\s*除"))
        if delete_btn.count() == 0:
            delete_btn = row.first.locator("button, a, span").filter(
                has_text=re.compile(r"删\s*除")
            )
        if delete_btn.count() == 0:
            # 操作列常收在「更多」
            more = row.first.locator("button, a, span").filter(
                has_text=re.compile(r"更多|操作")
            )
            if more.count() == 0:
                more = row.first.locator(
                    ".ant-dropdown-trigger, .anticon-more, "
                    "[aria-label='more'], .ant-space-item button"
                )
            if more.count() > 0:
                more.first.click(timeout=5000)
                self.page.wait_for_timeout(400)
                delete_btn = self.page.locator(
                    ".ant-dropdown:not(.ant-dropdown-hidden) "
                    ".ant-dropdown-menu-item, "
                    ".ant-dropdown:not(.ant-dropdown-hidden) li"
                ).filter(has_text=re.compile(r"删\s*除"))
        assert delete_btn.count() > 0, (
            f"行内未找到删除入口: {name}（可录制删除操作后对齐选择器）"
        )
        delete_btn.first.click(timeout=8000)
        self.page.wait_for_timeout(500)

        confirm = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none']), "
            ".ant-popconfirm:not(.ant-popover-hidden)"
        ).filter(has_text=re.compile(r"删除|确认|是否"))
        ok = confirm.locator("button").filter(
            has_text=re.compile(r"确\s*定|确\s*认|删\s*除")
        )
        if ok.count() > 0:
            ok.last.click(timeout=8000)
        else:
            self.click_toolbar_button(r"确\s*认|确\s*定|删\s*除")
        self.page.wait_for_timeout(1200)

    def assert_row_exists(self, name: str) -> None:
        link = self.page.locator(".ant-table-tbody").get_by_text(name, exact=False)
        assert link.count() > 0, f"列表应存在线索: {name}"

    def assert_row_absent(self, name: str) -> None:
        self.page.wait_for_timeout(800)
        link = self.page.locator(".ant-table-tbody").get_by_text(name, exact=False)
        assert link.count() == 0, f"列表仍存在已删除线索: {name}"

    def row_by_name(self, name: str):
        row = self.page.locator(".ant-table-tbody tr").filter(has_text=name)
        assert row.count() > 0, f"列表未找到线索: {name}"
        return row.first

    def _visible_lead_scope_labels(self) -> list[str]:
        labels: list[str] = []
        loc = self.page.locator(
            ".ant-tabs-tab, [role='tab'], .ant-radio-button-wrapper, "
            ".ant-segmented-item, .ant-pro-table-list-toolbar button, "
            ".ant-layout-sider .ant-menu-item"
        )
        for i in range(min(loc.count(), 20)):
            try:
                node = loc.nth(i)
                if not node.is_visible():
                    continue
                text = (node.inner_text() or "").strip().replace("\n", " ")
                if text:
                    labels.append(text)
            except Exception:
                continue
        return labels

    def switch_lead_list_tab(self, tab_text: str) -> None:
        """切换线索列表范围（页内 Tab / 分段器 / 侧栏「线索公海」）。

        只点可见的 Tab/Radio/Segmented/侧栏菜单，禁止用裸 span 误点行内「移入公海」。
        """
        patterns = [tab_text]
        if tab_text in ("公海", "线索公海", "线索公海池"):
            patterns = ["线索公海池", "线索公海", "公海线索", "公海"]
        elif tab_text in ("全部", "全部线索"):
            patterns = ["全部线索", "全部"]
        elif tab_text in ("我的线索", "我的"):
            patterns = ["我的线索", "我的"]

        tab_sel = (
            ".ant-tabs-tab, [role='tab'], .ant-radio-button-wrapper, "
            ".ant-segmented-item, .ant-radio-wrapper"
        )
        last_error: Exception | None = None
        for label in patterns:
            loc = self.page.locator(tab_sel).filter(
                has_text=re.compile(rf"^\s*{re.escape(label)}\s*$")
            )
            if loc.count() == 0:
                loc = self.page.locator(tab_sel).filter(has_text=label)
            for i in range(min(loc.count(), 8)):
                node = loc.nth(i)
                try:
                    if not node.is_visible():
                        continue
                    text = (node.inner_text() or "").strip().replace("\n", "")
                    if "移入" in text or "放入" in text:
                        continue
                    if label not in text:
                        continue
                    node.click(timeout=5000)
                    self.page.wait_for_timeout(1200)
                    print(f"[lead] 已切列表范围: {text}", flush=True)
                    return
                except Exception as exc:
                    last_error = exc
                    continue
            # 改版后「我的线索/线索公海」可能不是 ant-tabs，按内容区精确文案点
            nodes = self.page.get_by_text(label, exact=True)
            for i in range(min(nodes.count(), 12)):
                node = nodes.nth(i)
                try:
                    if not node.is_visible():
                        continue
                    in_bad = node.evaluate(
                        """el => !!(el.closest(
                            '.ant-layout-sider, aside, .ant-table, '
                            + '.ant-modal, .ant-drawer, .ant-dropdown'
                        ))"""
                    )
                    if in_bad:
                        continue
                    node.click(timeout=5000)
                    self.page.wait_for_timeout(1200)
                    print(f"[lead] 已切列表范围: {label}", flush=True)
                    return
                except Exception as exc:
                    last_error = exc
                    continue
            menu = self.page.locator(
                ".ant-layout-sider .ant-menu-item, aside .ant-menu-item, "
                ".ant-menu-item"
            ).filter(has_text=re.compile(rf"^\s*{re.escape(label)}\s*$"))
            if menu.count() > 0:
                try:
                    menu.first.click(timeout=5000)
                    self.page.wait_for_timeout(1200)
                    print(f"[lead] 已切侧栏范围: {label}", flush=True)
                    return
                except Exception as exc:
                    last_error = exc
        hits: list[str] = []
        probe = self.page.locator("body").get_by_text(
            re.compile(r"我的线索|全部线索|线索公海|公海池|公海")
        )
        for i in range(min(probe.count(), 25)):
            node = probe.nth(i)
            try:
                if not node.is_visible():
                    continue
                text = (node.inner_text() or "").strip().replace("\n", " ")[:40]
                hits.append(text)
            except Exception:
                continue
        content = ""
        try:
            main = self.page.locator(
                ".ant-layout-content, .ant-pro-page-container, main"
            ).first
            content = (main.inner_text() or "")[:600].replace("\n", " | ")
        except Exception:
            pass
        raise AssertionError(
            f"未找到线索列表范围「{tab_text}」({last_error})；"
            f"可见项={self._visible_lead_scope_labels()}；"
            f"公海相关={hits}；内容区={content!r}"
        )

    def reset_lead_search(self) -> None:
        """重置列表筛选，避免残留手机号把目标线索滤没。"""
        btn = self.page.locator(
            "form button, .ant-pro-table-search button, .ant-form button"
        ).filter(has_text=re.compile(r"重\s*置"))
        if btn.count() == 0:
            return
        try:
            btn.first.click(timeout=3000)
            self.page.wait_for_timeout(600)
        except Exception:
            pass

    def search_public_sea_leads(self, *, name: str = "", phone: str = "") -> None:
        """先切到公海范围，再按姓名查询（禁止用错误手机号碰运气）。"""
        # 先清残留手机号，再切公海（重置可能把范围打回「我的线索」）
        self.reset_lead_search()
        self.switch_lead_list_tab("线索公海池")
        self.search_leads(name=name, phone="" if name else phone)
        if not name:
            return
        row = self.page.locator(".ant-table-tbody tr").filter(has_text=name)
        if row.count() > 0:
            return
        blob = ""
        try:
            blob = (self.page.locator(".ant-table").first.inner_text() or "")[:400]
        except Exception:
            pass
        raise AssertionError(
            f"公海列表未找到线索: {name}；当前表={blob!r}；"
            f"范围={self._visible_lead_scope_labels()}"
        )

    def _open_row_more_menu(self, name: str):
        """打开行内「更多」下拉，返回可见菜单项 locator。"""
        row = self.row_by_name(name)
        more = row.locator("button, a, span").filter(
            has_text=re.compile(r"更多|操作")
        )
        if more.count() == 0:
            more = row.locator(
                ".ant-dropdown-trigger, .anticon-more, "
                "[aria-label='more'], .ant-space-item button"
            )
        assert more.count() > 0, f"行内未找到更多/操作入口: {name}"
        more.first.click(timeout=5000)
        self.page.wait_for_timeout(400)
        menu = self.page.locator(
            ".ant-dropdown:not(.ant-dropdown-hidden) "
            ".ant-dropdown-menu-item, "
            ".ant-dropdown:not(.ant-dropdown-hidden) li, "
            ".ant-dropdown:not(.ant-dropdown-hidden) button"
        )
        if menu.count() == 0:
            menu = self.page.locator(
                ".ant-popover:not(.ant-popover-hidden) .ant-popover-inner, "
                ".ant-dropdown:not(.ant-dropdown-hidden)"
            )
        return menu

    def _click_row_action(self, name: str, action_pattern: str) -> None:
        """行内直接按钮，或「更多」菜单里的操作。"""
        row = self.row_by_name(name)
        pat = re.compile(action_pattern)
        btn = row.get_by_role("button", name=pat)
        if btn.count() == 0:
            btn = row.locator("button, a, span").filter(has_text=pat)
        if btn.count() > 0:
            btn.first.click(timeout=8000)
            self.page.wait_for_timeout(500)
            return
        menu = self._open_row_more_menu(name)
        item = menu.filter(has_text=pat)
        if item.count() == 0:
            item = self.page.locator(
                ".ant-dropdown:not(.ant-dropdown-hidden) "
                ".ant-dropdown-menu-item, "
                ".ant-dropdown:not(.ant-dropdown-hidden) li"
            ).filter(has_text=pat)
        assert item.count() > 0, f"未找到线索操作「{action_pattern}」: {name}"
        item.first.click(timeout=8000)
        self.page.wait_for_timeout(500)

    def _confirm_visible_dialog(self, *, ok_pattern: str = r"确\s*定|确\s*认") -> None:
        dialog = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none']), "
            ".ant-popconfirm:not(.ant-popover-hidden)"
        )
        assert dialog.count() > 0, "未出现确认弹窗"
        ok = dialog.locator("button").filter(has_text=re.compile(ok_pattern))
        assert ok.count() > 0, f"确认弹窗无按钮: {ok_pattern}"
        ok.last.click(timeout=8000)
        self.page.wait_for_timeout(1200)

    def claim_lead_by_name(self, name: str) -> None:
        """公海线索认领（行内/更多 → 确认）。"""
        self._click_row_action(name, r"认\s*领")
        confirm = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none']), "
            ".ant-popconfirm:not(.ant-popover-hidden)"
        ).filter(has_text=re.compile(r"认领|确认|是否"))
        if confirm.count() > 0:
            self._confirm_visible_dialog()
        print(f"[lead] 已认领: {name}", flush=True)

    def read_row_follow_user(self, name: str) -> str:
        """列表「线索跟进人」列（常见第 4 列）。"""
        text = (self.row_by_name(name).inner_text() or "").replace("\n", "\t")
        cols = [c.strip() for c in re.split(r"\t+", text) if c.strip()]
        if len(cols) >= 4:
            return cols[3]
        m = re.search(r"(甜甜[^\\t]*|公海|tinker\\d+|采购员)", text)
        return m.group(1) if m else (cols[3] if len(cols) > 3 else "")

    def assign_lead_by_name(
        self, name: str, follow_keyword: str, *, current_follow: str = ""
    ) -> None:
        """分配给与当前不同的跟进人；拦截「分配前后跟进人一致」。"""
        keyword = (follow_keyword or "").strip()
        assert keyword, "分配跟进人关键字不能为空"
        current = (current_follow or self.read_row_follow_user(name)).strip()
        current_key = re.sub(r"[（(].*", "", current).strip()
        target_key = re.sub(r"[（(].*", "", keyword).strip()
        assert target_key and target_key not in current and current_key not in keyword, (
            f"分配目标不能与当前跟进人相同: current={current!r} target={keyword!r}"
        )
        self._click_row_action(name, r"分\s*配|转分配")
        modal = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none'])"
        ).filter(has_text=re.compile(r"分配|跟进人"))
        assert modal.count() > 0, f"未出现分配弹窗: {name}"
        host = modal.first
        # 跟进人搜索：优先弹窗内 Select
        sel = host.locator(".ant-select")
        if sel.count() > 0:
            root = sel.first
            root.click(timeout=5000)
            self.page.wait_for_timeout(300)
            inp = root.locator("input")
            if inp.count() == 0:
                inp = host.locator("input.ant-select-selection-search-input, input")
            if inp.count() > 0:
                try:
                    inp.first.fill("")
                    inp.first.press_sequentially(keyword, delay=80)
                except Exception:
                    inp.first.fill(keyword)
            self.page.wait_for_timeout(800)
            dropdown = self.page.locator(
                ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
            )
            option = self._dropdown_option_locator(dropdown)
            for _ in range(16):
                if option.count() > 0:
                    break
                self.page.wait_for_timeout(200)
                option = self._dropdown_option_locator(dropdown)
            assert option.count() > 0, f"分配弹窗无跟进人选项 keyword={keyword!r}"
            picked = ""
            for i in range(min(option.count(), 20)):
                node = option.nth(i)
                label = (node.inner_text() or "").strip().replace("\n", " ")
                if not label or label == "系统分配":
                    continue
                if current_key and current_key in label:
                    continue
                if keyword in label or target_key in label:
                    self._click_dropdown_option_node(node)
                    picked = label
                    break
            if not picked:
                for i in range(min(option.count(), 20)):
                    node = option.nth(i)
                    label = (node.inner_text() or "").strip().replace("\n", " ")
                    if not label or "系统分配" in label:
                        continue
                    if current_key and current_key in label:
                        continue
                    self._click_dropdown_option_node(node)
                    picked = label
                    break
            assert picked, (
                f"分配弹窗未选到不同于当前跟进人的选项 current={current!r} keyword={keyword!r}"
            )
            self.page.wait_for_timeout(300)
        else:
            inp = host.locator("input").first
            inp.fill(keyword)
            self.page.wait_for_timeout(600)
            opt = self.page.locator(
                ".ant-select-item-option, .ant-select-dropdown li"
            ).filter(has_text=keyword)
            assert opt.count() > 0, f"分配弹窗搜索无结果: {keyword}"
            opt.first.click(timeout=5000)
            picked = keyword

        shown = (host.locator(".ant-select").first.inner_text() or "").replace("\n", " ")
        assert current_key not in shown or shown.strip() != current, (
            f"分配弹窗新跟进人仍是当前人: shown={shown!r} current={current!r}"
        )
        ok = host.locator("button").filter(has_text=re.compile(r"确\s*定|确\s*认"))
        assert ok.count() > 0, "分配弹窗无确定按钮"
        ok.last.click(timeout=8000)
        self.page.wait_for_timeout(800)
        toast = self.page.locator(".ant-message-error, .ant-notification-notice-error")
        if toast.count() > 0:
            msg = (toast.first.inner_text() or "").strip()
            if "一致" in msg or "请修改" in msg:
                raise AssertionError(f"分配被拒绝（跟进人未改）: {msg}")
        self.page.wait_for_timeout(400)
        print(f"[lead] 已分配: {name} {current!r} → {picked!r}", flush=True)

    def _public_sea_reason_selector(self, host) -> str:
        """定位「移入公海池原因」Select，返回可供 select_plain_first 使用的选择器。"""
        for sel in (
            "#publicSeaReasonCode",
            "#salesclue_form_publicSeaReasonCode",
            "[id*='publicSeaReason']",
            "[id*='PublicSeaReason']",
        ):
            if host.locator(sel).count() > 0 or self.page.locator(sel).count() > 0:
                return sel
        item = host.locator(".ant-form-item").filter(has_text=re.compile(r"原因"))
        if item.count() > 0:
            inp = item.first.locator("input[id], .ant-select input")
            if inp.count() > 0:
                attr_id = inp.first.get_attribute("id") or ""
                if attr_id:
                    return f"#{attr_id}"
        raise AssertionError("移入公海弹窗未找到原因字段")

    def _assert_public_sea_reason_selected(self, root_selector: str) -> str:
        ant = self._ant_select_root(root_selector)
        shown = (ant.inner_text() or "").replace("\n", " ").strip()
        selected = ant.locator(".ant-select-selection-item")
        placeholder = ("请选择" in shown) or ("请输入" in shown) or shown in ("", "*")
        if selected.count() == 0 or placeholder:
            raise AssertionError(f"移入公海原因未选上: shown={shown!r}")
        label = (selected.first.inner_text() or shown).strip()
        print(f"[lead] 已选移入公海原因: {label!r}", flush=True)
        return label

    def move_lead_to_public_sea(self, name: str) -> None:
        """移入公海：必须先选原因（复用 select_plain_first），断言回填后再确定。"""
        self._click_row_action(name, r"移入公海|放入公海|转公海")
        modal = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none'])"
        ).filter(has_text=re.compile(r"公海"))
        assert modal.count() > 0, f"未出现移入公海弹窗: {name}"
        host = modal.first
        reason_sel = self._public_sea_reason_selector(host)
        self.select_plain_first(reason_sel)
        self._assert_public_sea_reason_selected(reason_sel)
        remark = host.locator("textarea")
        if remark.count() > 0:
            try:
                remark.first.fill("自动化移入公海")
            except Exception:
                pass
        modal = self.page.locator(
            ".ant-modal-wrap:not([style*='display: none'])"
        ).filter(has_text=re.compile(r"公海"))
        assert modal.count() > 0, "移入公海弹窗在选原因后消失（勿用 Escape）"
        host = modal.first
        ok = host.locator("button.ant-btn-primary").filter(
            has_text=re.compile(r"确\s*定|确\s*认")
        )
        if ok.count() == 0:
            ok = host.locator("button").filter(has_text=re.compile(r"确\s*定|确\s*认"))
        assert ok.count() > 0, "移入公海弹窗无确定按钮"
        try:
            ok.last.click(timeout=5000)
        except Exception:
            ok.last.click(force=True, timeout=5000)
        self.page.wait_for_timeout(600)
        still_err = host.locator(".ant-form-item-explain-error").filter(
            has_text=re.compile(r"请输入|请选择")
        )
        if still_err.count() > 0:
            raise AssertionError(
                f"移入公海原因未选上，仍校验失败: {(still_err.first.inner_text() or '').strip()}"
            )
        self.page.wait_for_timeout(800)
        print(f"[lead] 已移入公海: {name}", flush=True)

    def assert_lead_row_follow_and_status(
        self,
        name: str,
        *,
        follow_contains: str = "",
        follow_not_contains: str = "",
        status_contains: str = "",
        public_sea: bool | None = None,
    ) -> str:
        """断言列表行跟进人/状态；返回行文案便于日志。"""
        row = self.row_by_name(name)
        try:
            row.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        text = (row.inner_text() or "").replace("\n", " ").strip()
        if follow_contains:
            assert follow_contains in text, (
                f"跟进人未包含 {follow_contains!r}: {text!r}"
            )
        if follow_not_contains:
            assert follow_not_contains not in text, (
                f"跟进人仍含 {follow_not_contains!r}: {text!r}"
            )
        if status_contains:
            assert status_contains in text, (
                f"状态未包含 {status_contains!r}: {text!r}"
            )
        if public_sea is True:
            # 跟进人列常见「公海」；勿把行内「移入公海」按钮当状态
            cols = re.split(r"\t+", text)
            follow_cell = cols[3] if len(cols) > 3 else text
            assert (
                "公海" in follow_cell
                or re.search(r"公海", text[:80])
            ), f"行应显示公海跟进人: {text!r}"
        if public_sea is False:
            cols = re.split(r"\t+", text)
            follow_cell = cols[3] if len(cols) > 3 else ""
            assert "公海" not in follow_cell, f"跟进人仍是公海: {text!r}"
        print(f"[lead] 行断言通过: {text[:160]!r}", flush=True)
        return text

    def read_detail_follow_and_status(self) -> dict[str, str]:
        """详情抽屉：读跟进人 / 状态文案。"""
        host = self.page.locator(
            ".ant-drawer-open, .ant-modal-wrap:not([style*='display: none'])"
        ).filter(has_text=re.compile(r"线索详情|基础信息"))
        root = host.first if host.count() > 0 else self.page
        blob = (root.inner_text() or "").replace("\n", " ")
        follow = ""
        status = ""
        m_f = re.search(r"线索跟进人\s*([^\s].{0,40}?)(?:\s{2,}|\t|邮箱|线索职务)", blob)
        if m_f:
            follow = m_f.group(1).strip()
        m_s = re.search(
            r"(待跟进|跟进中|已转化|公海|已作废|待认领)", blob
        )
        if m_s:
            status = m_s.group(1)
        return {"follow": follow, "status": status, "text": blob}

    def select_lead_position(self, position_text: str = "采购员") -> None:
        """线索职务：按文案点选（默认采购员），禁止点到「未知」。"""
        sel = "#positionCode"
        if self.page.locator(sel).count() == 0:
            return
        text = (position_text or CRM_UI_CUSTOMER_CONTACT_POSITION or "采购员").strip()
        self._dismiss_select_dropdown()
        # 本地枚举：打开后按精确文案点选
        dropdown = self._open_select_dropdown(sel)
        option = self._dropdown_option_locator(dropdown)
        for _ in range(20):
            if option.count() > 0:
                break
            self.page.wait_for_timeout(250)
            option = self._dropdown_option_locator(dropdown)
        assert option.count() > 0, f"线索职务下拉无选项: {sel}"
        matched = option.filter(has_text=re.compile(rf"^{re.escape(text)}$"))
        if matched.count() == 0:
            matched = option.filter(has_text=text)
        # 排除「未知」
        picked = None
        for i in range(min(matched.count(), 8)):
            node = matched.nth(i)
            label = (node.inner_text() or "").strip().replace("\n", " ")
            if not label or label == "未知":
                continue
            if text in label:
                self._click_dropdown_option_node(node)
                picked = label
                break
        if not picked:
            # 全文扫描含采购员的项
            for i in range(min(option.count(), 20)):
                node = option.nth(i)
                label = (node.inner_text() or "").strip().replace("\n", " ")
                if text in label and label != "未知":
                    self._click_dropdown_option_node(node)
                    picked = label
                    break
        assert picked, f"线索职务未找到「{text}」"
        self._dismiss_select_dropdown()
        shown = (self._ant_select_root(sel).inner_text() or "").strip()
        assert text in shown and "未知" not in shown, (
            f"线索职务未选中: expect={text} shown={shown!r}"
        )
        self._assert_create_form_still_open("线索职务")

    def _assign_follow_user(
        self,
        follow_user_keyword: str,
        *,
        prefer_text: str = "采购员",
    ) -> None:
        """线索跟进人：输入关键字后必须点选返回结果，不能停在空值/系统分配。"""
        sel = "#followUserAssignType"
        assert self.page.locator(sel).count() > 0, "未找到线索跟进人 #followUserAssignType"
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
                search.first.press("Control+A")
                search.first.fill(keyword)
                self.page.wait_for_timeout(1800)

                dropdowns = self.page.locator(
                    ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
                )
                try:
                    dropdowns.last.wait_for(state="visible", timeout=10000)
                except PlaywrightTimeoutError as exc:
                    raise AssertionError(
                        f"输入「{keyword}」后跟进人下拉未出现"
                    ) from exc

                dropdown = dropdowns.last
                for i in range(dropdowns.count() - 1, -1, -1):
                    cand = dropdowns.nth(i)
                    if self._dropdown_option_locator(cand).count() > 0 or cand.get_by_text(
                        re.compile(re.escape(keyword))
                    ).count() > 0:
                        dropdown = cand
                        break

                picked = ""
                for pattern in (
                    re.compile(rf"指定到个人\s*/\s*.*{re.escape(prefer_text)}"),
                    re.compile(rf".*{re.escape(prefer_text)}.*"),
                    re.compile(r"指定到个人\s*/\s*甜甜"),
                    re.compile(r"甜甜"),
                    re.compile(re.escape(keyword)),
                ):
                    by_text = dropdown.get_by_text(pattern)
                    if by_text.count() == 0:
                        continue
                    for i in range(min(by_text.count(), 6)):
                        node = by_text.nth(i)
                        label = (node.inner_text() or "").strip().replace("\n", " ")
                        if not label or label == "系统分配":
                            continue
                        self._click_dropdown_option_node(node)
                        picked = label
                        self.page.wait_for_timeout(500)
                        break
                    if picked:
                        break

                if not picked:
                    self._pick_dropdown_option(dropdown, keyword)
                    picked = keyword

                self._dismiss_select_dropdown()
                shown = (ant.inner_text() or "").strip().replace("\n", " ")
                if shown.strip() == "系统分配" or re.fullmatch(r"\s*系统分配\s*", shown):
                    raise AssertionError(
                        f"跟进人仍是系统分配，未点中下拉。picked={picked!r} shown={shown!r}"
                    )
                if not (
                    prefer_text in shown
                    or "甜甜" in shown
                    or "指定" in shown
                    or keyword in shown
                ):
                    raise AssertionError(
                        f"跟进人点选后未回填。picked={picked!r} shown={shown!r}"
                    )
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self._dismiss_select_dropdown()
                self.page.wait_for_timeout(400 * (attempt + 1))

        raise AssertionError(
            f"跟进人选择失败（需搜索「{keyword}」后点击返回结果）: {last_error}"
        ) from last_error

    def _select_exhibition_if_present(self, keyword: str = "") -> None:
        """来源=展会时必选「展会名称」；字段未出现则跳过，出现则必须选中回填。"""
        sel = "#crmExhibitionId"
        appeared = False
        for _ in range(24):
            if self.page.locator(sel).count() > 0:
                try:
                    if self.page.locator(sel).first.is_visible():
                        appeared = True
                        break
                except Exception:
                    pass
            self.page.wait_for_timeout(250)
        if not appeared:
            return

        keyword = (keyword or "").strip()
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                self._dismiss_select_dropdown()
                if keyword:
                    try:
                        self.select_searchable(sel, keyword)
                    except AssertionError:
                        # 关键字未命中时回退第一项，避免整单失败
                        self.select_plain_first(sel)
                else:
                    self.select_plain_first(sel)

                ant = self._ant_select_root(sel)
                shown = (ant.inner_text() or "").replace("\n", " ").strip()
                if (not shown) or ("请选择" in shown):
                    raise AssertionError(f"展会名称未回填: shown={shown!r}")
                self._assert_create_form_still_open("展会名称")
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self._dismiss_select_dropdown()
                self.page.wait_for_timeout(400 * (attempt + 1))

        raise AssertionError(f"展会名称选择失败: {last_error}") from last_error

    def fill_create_basic(
        self,
        *,
        name: str,
        phone: str,
        email: str,
        follow_user_keyword: str,
        channel_detail: str,
        company_keyword: str,
        remark: str,
        annual_purchase_amount: str = "1000",
        source_text: str = "",
        exhibition_keyword: str = "",
        qichacha_backfill: bool = True,
        attachment: Path | None = None,
    ) -> None:
        # 填表全程锁定页脚「确定」，防止 Enter/误点触发查重
        self._block_create_form_submit(True)
        try:
            self._fill_create_basic_body(
                name=name,
                phone=phone,
                email=email,
                follow_user_keyword=follow_user_keyword,
                channel_detail=channel_detail,
                company_keyword=company_keyword,
                remark=remark,
                annual_purchase_amount=annual_purchase_amount,
                source_text=source_text,
                exhibition_keyword=exhibition_keyword,
                qichacha_backfill=qichacha_backfill,
                attachment=attachment,
            )
        except Exception:
            # 失败也保持锁定，由 confirm_save 或下一次打开表单处理
            self.cancel_create_if_duplicate(timeout_ms=2000)
            raise

    def _fill_create_basic_body(
        self,
        *,
        name: str,
        phone: str,
        email: str,
        follow_user_keyword: str,
        channel_detail: str,
        company_keyword: str,
        remark: str,
        annual_purchase_amount: str = "1000",
        source_text: str = "",
        exhibition_keyword: str = "",
        qichacha_backfill: bool = True,
        attachment: Path | None = None,
    ) -> None:
        self._fill_if_present("#name", name)
        self._fill_if_present("#phone", phone)
        self._fill_if_present("#email", email)

        if source_text:
            self._select_if_present("#leadSourceCode", keyword=source_text)
        else:
            self._select_if_present("#leadSourceCode", first=True)

        # 来源=展会时展会名称必填，禁止 swallow 失败
        self._select_exhibition_if_present(exhibition_keyword)

        if follow_user_keyword and self.page.locator("#followUserAssignType").count() > 0:
            self._assign_follow_user(follow_user_keyword, prefer_text="采购员")

        self.select_lead_position(CRM_UI_CUSTOMER_CONTACT_POSITION or "采购员")
        self._select_if_present("#leadLevelCode", first=True)
        self._fill_if_present("#channelDetail", channel_detail)

        # 公司名称：键入关键字 → 断言并点选目标公司全称 → 再工商查询
        if qichacha_backfill and company_keyword:
            print("[lead] 填写公司名称…", flush=True)
            company_name = self.pick_company_via_qichacha(
                company_keyword,
                prefer_option=CRM_UI_LEAD_COMPANY_OPTION or "白象食品股份有限公司",
            )
            assert company_name and "请输入" not in company_name, (
                f"公司名称未选中: {company_name!r}"
            )
            print(f"[lead] 公司名称已选: {company_name}", flush=True)
        elif company_keyword:
            self._fill_if_present("#companyName", company_keyword)

        self.cancel_create_if_duplicate(timeout_ms=2000)
        self._block_create_form_submit(True)  # 工商后可能重绘页脚，再锁一次

        # 经营类型 / 行业
        if self.page.locator("#businessTypeCode").count() > 0:
            print("[lead] 填写经营类型…", flush=True)
            try:
                self.select_business_type_cascade(
                    level1=CRM_UI_CUSTOMER_BUSINESS_TYPE_L1 or "终端客户",
                    level2=CRM_UI_CUSTOMER_BUSINESS_TYPE_L2 or "品牌方",
                )
            except Exception as exc:
                print(f"[lead] 经营类型 cascade 失败 ({exc})，回退 levels", flush=True)
                self.select_cascader_levels(
                    "#businessTypeCode",
                    levels=None,
                    depth=2,
                    required=True,
                    field_name="经营类型",
                )

        if self.page.locator("#industryCode").count() > 0:
            print("[lead] 填写行业…", flush=True)
            self.select_industry_cascade(
                level1=CRM_UI_CUSTOMER_INDUSTRY_L1 or "食品行业",
                level2=CRM_UI_CUSTOMER_INDUSTRY_L2 or "",
            )

        try:
            if self.page.get_by_text(re.compile(r"省\s*/\s*州|省/州")).count() > 0 or (
                self.page.locator("#provinceCode, #province, #provinceName").count() > 0
            ):
                print("[lead] 填写省市区…", flush=True)
                self.fill_domestic_region(
                    province=CRM_UI_CUSTOMER_PROVINCE or "江苏",
                    city=CRM_UI_CUSTOMER_CITY or "苏州",
                    district=CRM_UI_CUSTOMER_DISTRICT or "姑苏区",
                )
        except AssertionError as exc:
            print(f"[lead] 省市区跳过: {exc}", flush=True)
            self._dismiss_select_dropdown()

        # —— 询盘 → 附件 →（此时仍锁定确定）——
        self.cancel_create_if_duplicate(timeout_ms=2500)
        self._block_create_form_submit(True)

        print("[lead] 滚动到询盘信息…", flush=True)
        try:
            self.page.get_by_text(re.compile(r"询盘信息")).first.scroll_into_view_if_needed(
                timeout=5000
            )
        except Exception:
            pass
        self.page.wait_for_timeout(300)

        print("[lead] 填写询盘信息…", flush=True)
        # 只维护询盘关键词 + 备注（冒烟必填）；其它枚举能填就填，失败不阻断
        if self.page.locator("#inquiryKeywordCode").count() > 0:
            self.select_plain_first("#inquiryKeywordCode")
            shown = (
                self._ant_select_root("#inquiryKeywordCode").inner_text() or ""
            ).replace("\n", " ").strip()
            assert shown and "请选择" not in shown, f"询盘关键词未选中: {shown!r}"
            print(f"[lead] 询盘关键词已选: {shown!r}", flush=True)

        if remark:
            if self.page.locator("#remark").count() > 0:
                self._ensure_input("#remark", remark, required=True, as_textarea=True)
            else:
                self._fill_if_present("#remark", remark)
            cur = ""
            try:
                cur = (self.page.locator("#remark").first.input_value(timeout=1500) or "").strip()
            except Exception:
                cur = ""
            assert cur, f"备注未写入: {cur!r}"
            print(f"[lead] 备注已填: {cur[:40]!r}", flush=True)

        for sel in ("#annualPurchaseUnitCode",):
            if self.page.locator(sel).count() > 0:
                try:
                    self.select_plain_first(sel)
                except AssertionError:
                    pass
        self._fill_if_present("#annualPurchaseAmount", annual_purchase_amount)

        # 产品需求等非关键字段：失败跳过（先于关键决策人，避免级联 dismiss 冲掉选择）
        self.cancel_create_if_duplicate(timeout_ms=1500)
        if self.page.locator("#productDemandId").count() > 0:
            try:
                self.select_cascader_levels(
                    "#productDemandId",
                    levels=None,
                    depth=3,
                    required=False,
                    field_name="产品需求",
                )
            except Exception as exc:
                print(f"[lead] 产品需求跳过: {exc}", flush=True)

        # 是否关键决策人：显式选「是」，不能停在默认「否」；放在询盘末尾、保存前再校验
        self.cancel_create_if_duplicate(timeout_ms=1500)
        self.select_key_decision_maker("是")

        assert attachment is not None, "线索冒烟必须上传附件"
        print(f"[lead] 上传附件: {attachment}", flush=True)
        self.cancel_create_if_duplicate(timeout_ms=2000)
        self._block_create_form_submit(True)
        self.upload_attachment_if_present(Path(attachment))
        print("[lead] 附件已上传并等待完成", flush=True)

        # 上传/滚动后偶发 UI 回显默认，保存前再确认一次关键决策人
        self.select_key_decision_maker("是")

        self.cancel_create_if_duplicate(timeout_ms=2000)
        self.assert_inquiry_and_attachment_ready(remark=remark, require_attachment=True)
        print("[lead] 表单字段填写结束（尚未保存/查重，确定仍锁定）", flush=True)

    def search_leads(
        self,
        *,
        name: str = "",
        company_name: str = "",
        phone: str = "",
        email: str = "",
        country: str = "",
        follow_keyword: str = "",
        create_time_start: str = "",
        create_time_end: str = "",
        pick_level_first: bool = False,
    ) -> None:
        self.close_overlays()
        # 按姓名查时清掉手机号，避免「手机号对不上任何线索」
        if name:
            for sel in (
                "#salesclue_form_phone",
                "input[placeholder*='手机']",
                "input[placeholder*='电话']",
            ):
                loc = self.page.locator(sel)
                if loc.count() == 0:
                    continue
                try:
                    loc.first.fill("")
                except Exception:
                    pass
            filled = False
            for sel in (
                "#salesclue_form_name",
                "#salesclue_form_leadName",
                "input[placeholder*='姓名']",
            ):
                loc = self.page.locator(sel)
                if loc.count() == 0:
                    continue
                try:
                    if not loc.first.is_visible():
                        continue
                except Exception:
                    pass
                self._fill_if_present(sel, name)
                filled = True
                break
            if not filled:
                self._fill_if_present("#salesclue_form_name", name)
        self._fill_if_present("#salesclue_form_companyName", company_name)
        if phone:
            self._fill_if_present("#salesclue_form_phone", phone)
        self._fill_if_present("#salesclue_form_email", email)

        if country and self.page.locator("#salesclue_form_countryCodeList").count() > 0:
            try:
                self.select_searchable(
                    "#salesclue_form_countryCodeList", country, multi=True
                )
            except AssertionError:
                pass

        if follow_keyword and self.page.locator("#salesclue_form_followId").count() > 0:
            try:
                self.select_searchable(
                    "#salesclue_form_followId", follow_keyword, multi=True
                )
            except AssertionError:
                pass

        if create_time_start or create_time_end:
            self._set_create_time_range(
                start=create_time_start or create_time_end,
                end=create_time_end or create_time_start,
            )

        if pick_level_first and self.page.locator("#salesclue_form_leadLevelCode").count() > 0:
            try:
                self.select_plain_first("#salesclue_form_leadLevelCode")
            except AssertionError:
                pass

        self.click_search()
        self.page.wait_for_timeout(1500)

    def _set_create_time_range(self, *, start: str, end: str) -> None:
        """创建时间 RangePicker：只读 input，复用基类日历点选。"""
        root = "#salesclue_form_time"
        if self.page.locator(root).count() == 0:
            return
        self.set_ant_range_picker(root, start=start, end=end)

    def open_row_by_name(self, name: str) -> None:
        link = self.page.get_by_role("link", name=name)
        if link.count() == 0:
            link = self.page.locator(".ant-table-tbody a").filter(has_text=name)
        assert link.count() > 0, f"列表未找到线索: {name}"
        link.first.click()
        self.page.wait_for_timeout(1200)

    @staticmethod
    def today_str() -> str:
        return date.today().isoformat()
