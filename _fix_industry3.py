# -*- coding: utf-8 -*-
from pathlib import Path
import re

path = Path("pages/crm_customer_page.py")
text = path.read_text(encoding="utf-8")
start = text.find("    def select_industry_cascade(")
end = text.find("\n    def ", start + 5)
new = '''    def select_industry_cascade(
        self,
        *,
        level1: str = "\u98df\u54c1\u884c\u4e1a",
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
                field_name="\u884c\u4e1a",
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
                field_name="\u884c\u4e1a",
            )
            return
        except Exception as exc2:  # noqa: BLE001
            raise AssertionError(
                f"\u884c\u4e1a cascader failed label={levels!r} err={last}; fallback={exc2}"
            ) from exc2

'''
text = text[:start] + new + text[end:]
path.write_text(text, encoding="utf-8")
print("industry fallback ok")
