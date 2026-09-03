# -*- coding: utf-8 -*-
from pathlib import Path
import re

page = Path("pages/crm_customer_page.py")
text = page.read_text(encoding="utf-8")

# 1) customerLevel required
text2, n = re.subn(
    r'(self\._ensure_select\("#customerLevelCode", first=True, required=)False(\))',
    r"\1True\2",
    text,
    count=1,
)
print("customerLevel patch", n)
text = text2

# 2) enterpriseNature required + fullCategory cascader after that block
old = 'self._ensure_select("#enterpriseNatureCode", first=True, required=False)'
new = '''self._ensure_select("#enterpriseNatureCode", first=True, required=True)
        elif self.page.locator("#enterpriseNature").count() > 0:
            self._ensure_select("#enterpriseNature", first=True, required=False)

        # standard industry cascader when present
        if self.page.locator("#fullCategoryId").count() > 0:
            self.select_cascader_levels(
                "#fullCategoryId",
                depth=3,
                required=False,
                field_name="\u6807\u51c6\u884c\u4e1a",
            )'''
if old in text:
    text = text.replace(old, new, 1)
    print("enterprise patch ok")
else:
    print("enterprise block not found")

# 3) upload targets: insert background report entries
needle = '            ("\u5ba2\u6237\u62a5\u544a", "#customerReportUrls"),\n'
insert = (
    needle
    + '            ("\u5ba2\u6237\u80cc\u8c03\u62a5\u544a", "#backgroundReportUrls"),\n'
    + '            ("\u80cc\u8c03\u62a5\u544a", "#backgroundReportUrls"),\n'
)
if needle in text and "#backgroundReportUrls" not in text:
    text = text.replace(needle, insert, 1)
    print("upload patch ok")
else:
    print("upload patch skip", needle in text, "#backgroundReportUrls" in text)

# 4) collect errors helper
if "def collect_create_form_errors" not in text:
    helper = '''    def collect_create_form_errors(self) -> list[str]:
        """Collect create-form validation / toast errors."""
        errs: list[str] = []
        try:
            locs = self.page.locator(
                ".ant-form-item-explain-error, .ant-message-error, "
                ".ant-notification-notice-description"
            )
            for i in range(min(locs.count(), 30)):
                t = (locs.nth(i).inner_text() or "").strip()
                if t and t not in errs:
                    errs.append(t)
        except Exception:
            pass
        return errs

'''
    marker = "    def confirm_customer_create_save"
    idx = text.find(marker)
    if idx >= 0:
        text = text[:idx] + helper + text[idx:]
        print("added collect_create_form_errors")
    else:
        print("confirm not found")

page.write_text(text, encoding="utf-8")
print("done page")
