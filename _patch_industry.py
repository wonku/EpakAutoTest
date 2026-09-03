# -*- coding: utf-8 -*-
from pathlib import Path

path = Path("pages/crm_customer_page.py")
text = path.read_text(encoding="utf-8")
start = text.find("def select_industry_cascade")
end = text.find("\n    def ", start + 5)
print("old len", end - start)
print(text[start:start+500])

new = '''    def select_industry_cascade(
        self,
        *,
        level1: str = "\u98df\u54c1\u884c\u4e1a",
        level2: str = "",
    ) -> None:
        """Industry cascader: pick L1 (default food) then L2 text or first visible."""
        levels = [x for x in (level1, level2) if x]
        # Prefer generic cascader helper (JS click, assert-after-select)
        self.select_cascader_levels(
            "#industryCode",
            levels=levels or None,
            depth=2 if not levels else max(len(levels), 1),
            required=True,
            field_name="\u884c\u4e1a",
        )
'''
text = text[:start] + new + text[end:]
path.write_text(text, encoding="utf-8")
print("replaced industry cascade with select_cascader_levels")
