# -*- coding: utf-8 -*-
from pathlib import Path

path = Path("pages/crm_customer_page.py")
text = path.read_text(encoding="utf-8")
start = text.find("    def _ensure_input(")
end = text.find("\n    def ", start + 5)
assert start > 0 and end > start
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
'''
text = text[:start] + new + text[end:]
# also dismiss overlays before region / at start of later domestic fills
needle = "        # \u7ecf\u8425\u8303\u56f4"
# use ascii marker near businessScope ensure
marker = 'self._ensure_input(\n            "#businessScope"'
idx = text.find(marker)
if idx > 0 and "self._dismiss_blocking_overlays()" not in text[idx-80:idx]:
    text = text[:idx] + "self._dismiss_blocking_overlays()\n        " + text[idx:]
    print("pre-dismiss before businessScope")
path.write_text(text, encoding="utf-8")
print("ensure_input replaced", start, end)
