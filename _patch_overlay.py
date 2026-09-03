# -*- coding: utf-8 -*-
from pathlib import Path

path = Path("pages/crm_customer_page.py")
text = path.read_text(encoding="utf-8")
start = text.find("    def _dismiss_blocking_overlays")
end = text.find("\n    def ", start + 5)
assert start > 0 and end > start, (start, end)

unsaved = "\u672a\u4fdd\u5b58|\u662f\u5426\u53d6\u6d88"
cancel = "\u53d6\\s*\u6d88"
ok = "\u77e5\\s*\u9053\\s*\u4e86|\u786e\\s*\u5b9a|\u5173\\s*\u95ed|\u6211\u77e5\u9053\u4e86"

new = f'''    def _dismiss_blocking_overlays(self) -> None:
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
            if re.search(r"{unsaved}", text_m):
                cancel_btn = modal.locator("button").filter(
                    has_text=re.compile(r"{cancel}")
                )
                if cancel_btn.count() > 0:
                    cancel_btn.first.click(force=True, timeout=3000)
                    self.page.wait_for_timeout(300)
                continue
            closer = modal.locator("button").filter(has_text=re.compile(r"{ok}"))
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
                    "el => {{ el.style.display='none'; "
                    "const wrap=el.closest('.ant-modal-wrap'); "
                    "if (wrap) wrap.style.display='none'; }}"
                )
            except Exception:
                pass
            break
        try:
            self._dismiss_select_dropdown()
        except Exception:
            pass
'''

text = text[:start] + new + text[end:]
path.write_text(text, encoding="utf-8")
print("overlays fixed")
# sanity: chinese present
t2 = path.read_text(encoding="utf-8")
assert "\u672a\u4fdd\u5b58" in t2
assert "\u77e5" in t2[t2.find("def _dismiss_blocking_overlays"):t2.find("def _dismiss_blocking_overlays")+800]
print("unicode ok")
