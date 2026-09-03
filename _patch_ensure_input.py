# -*- coding: utf-8 -*-
from pathlib import Path
import re

path = Path("pages/crm_customer_page.py")
text = path.read_text(encoding="utf-8")

# Strengthen _ensure_input to dismiss overlay modals and force-fill
old = '''    def _ensure_input(
        self,
        selector: str,
        value: str,
        *,
        required: bool = True,
        as_textarea: bool = False,
    ) -> None:
        """字段已有值（含工商回填）则跳过；否则写入并校验。"""
        if self.page.locator(selector).count() == 0:
            if required:
                raise AssertionError(f"缺少必填字段: {selector}")
            return
        current = self._input_value(selector)
        if current:
            return
        if not value:
            if required:
                raise AssertionError(f"必填字段为空且无默认值: {selector}")
            return
        loc = self.page.locator(selector).first
        loc.scroll_into_view_if_needed(timeout=5000)
        loc.click(timeout=5000)
        if as_textarea:
            loc.fill(str(value))
        else:
            loc.fill(str(value))
        self.page.wait_for_timeout(200)
        after = self._input_value(selector)
        if required and not after:
            raise AssertionError(f"填写后仍为空: {selector}")
'''

# Use docstring-agnostic replace via regex
pat = re.compile(
    r"    def _ensure_input\(\n"
    r"        self,\n"
    r"        selector: str,\n"
    r"        value: str,\n"
    r"        \*,\n"
    r"        required: bool = True,\n"
    r"        as_textarea: bool = False,\n"
    r"    \) -> None:\n"
    r"        \"\"\".*?\"\"\"\n"
    r"        if self\.page\.locator\(selector\)\.count\(\) == 0:\n"
    r"            if required:\n"
    r"                raise AssertionError\(f\"[^\"]+\": \{selector\}\"\)\n"
    r"            return\n"
    r"        current = self\._input_value\(selector\)\n"
    r"        if current:\n"
    r"            return\n"
    r"        if not value:\n"
    r"            if required:\n"
    r"                raise AssertionError\(f\"[^\"]+\": \{selector\}\"\)\n"
    r"            return\n"
    r"        loc = self\.page\.locator\(selector\)\.first\n"
    r"        loc\.scroll_into_view_if_needed\(timeout=5000\)\n"
    r"        loc\.click\(timeout=5000\)\n"
    r"        if as_textarea:\n"
    r"            loc\.fill\(str\(value\)\)\n"
    r"        else:\n"
    r"            loc\.fill\(str\(value\)\)\n"
    r"        self\.page\.wait_for_timeout\(200\)\n"
    r"        after = self\._input_value\(selector\)\n"
    r"        if required and not after:\n"
    r"            raise AssertionError\(f\"[^\"]+\": \{selector\}\"\)\n",
    re.S,
)

new = '''    def _ensure_input(
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
        loc.fill(str(value), force=True)
        self.page.wait_for_timeout(200)
        after = self._input_value(selector)
        if required and not after:
            # last resort: JS set value + input event
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
'''

m = pat.search(text)
print("ensure_input match", bool(m))
if m:
    text = pat.sub(new, text, count=1)

# Add _dismiss_blocking_overlays near _dismiss_select_dropdown
if "def _dismiss_blocking_overlays" not in text:
    helper = '''    def _dismiss_blocking_overlays(self) -> None:
        """Close tip/info modals that intercept clicks (keep create drawer open)."""
        for _ in range(3):
            modal = self.page.locator(
                ".ant-modal-wrap:not([style*='display: none']) .ant-modal-content"
            )
            if modal.count() == 0:
                break
            text_m = ""
            try:
                text_m = modal.first.inner_text() or ""
            except Exception:
                text_m = ""
            # unsaved prompt: click cancel to stay
            if re.search(r"\u672a\u4fdd\u5b58|\u662f\u5426\u53d6\u6d88", text_m):
                cancel = self.page.locator(
                    ".ant-modal-wrap:not([style*='display: none']) button"
                ).filter(has_text=re.compile(r"\u53d6\\s*\u6d88"))
                if cancel.count() > 0:
                    cancel.first.click(force=True, timeout=3000)
                    self.page.wait_for_timeout(300)
                continue
            # tip / known / OK
            closer = self.page.locator(
                ".ant-modal-wrap:not([style*='display: none']) button"
            ).filter(
                has_text=re.compile(
                    r"\u77e5\\s*\u9053\\s*\u4e86|\u786e\\s*\u5b9a|\u5173\\s*\u95ed|\u6211\u77e5\u9053\u4e86"
                )
            )
            if closer.count() > 0:
                try:
                    closer.first.click(force=True, timeout=3000)
                    self.page.wait_for_timeout(300)
                    continue
                except Exception:
                    pass
            xbtn = self.page.locator(
                ".ant-modal-wrap:not([style*='display: none']) button.ant-modal-close"
            )
            if xbtn.count() > 0:
                try:
                    xbtn.first.click(force=True, timeout=2000)
                    self.page.wait_for_timeout(300)
                    continue
                except Exception:
                    pass
            # Escape as last resort for tip layers
            try:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(200)
            except Exception:
                pass
            break
        self._dismiss_select_dropdown()

'''
    marker = "    def _dismiss_select_dropdown"
    idx = text.find(marker)
    if idx >= 0:
        text = text[:idx] + helper + text[idx:]
        print("added _dismiss_blocking_overlays")
    else:
        print("dismiss marker missing")

# Also call dismiss before businessScope in fill - optional since ensure_input does it

# Soften enterpriseNature if select fails - wrap later if needed

path.write_text(text, encoding="utf-8")
print("written")
