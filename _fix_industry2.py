# -*- coding: utf-8 -*-
from pathlib import Path
import re

path = Path("pages/crm_customer_page.py")
text = path.read_text(encoding="utf-8")

# Remove any broken nested / duplicate select_industry_cascade
text2 = re.sub(
    r"\n[ \t]*def select_industry_cascade\([\s\S]*?(?=\n    def )",
    "\n",
    text,
    count=2,
)
print("removed industry defs, delta", len(text) - len(text2))
text = text2

# Insert clean method before select_business_type_cascade
marker = "    def select_business_type_cascade("
idx = text.find(marker)
assert idx > 0
method = '''    def select_industry_cascade(
        self,
        *,
        level1: str = "\u98df\u54c1\u884c\u4e1a",
        level2: str = "",
    ) -> None:
        """Industry cascader via generic helper (assert-after-select)."""
        levels = [x for x in (level1, level2) if x]
        self.select_cascader_levels(
            "#industryCode",
            levels=levels or None,
            depth=2 if not levels else max(len(levels), 1),
            required=True,
            field_name="\u884c\u4e1a",
        )

'''
text = text[:idx] + method + text[idx:]
path.write_text(text, encoding="utf-8")
print("inserted clean industry method")
