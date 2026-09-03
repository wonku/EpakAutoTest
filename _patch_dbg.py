# -*- coding: utf-8 -*-
from pathlib import Path

path = Path("pages/crm_customer_page.py")
text = path.read_text(encoding="utf-8")
if "DBG_DOMESTIC" not in text:
    # inject prints in fill_create_domestic_basic key steps
    replacements = [
        (
            "company_name = self.pick_company_via_qichacha(company_keyword)",
            'print("DBG_DOMESTIC: qichacha", flush=True)\n        company_name = self.pick_company_via_qichacha(company_keyword)\n        print("DBG_DOMESTIC: company", company_name, flush=True)',
        ),
        (
            "self.select_business_type_cascade(\n            level1=business_type_l1, level2=business_type_l2\n        )",
            'print("DBG_DOMESTIC: business_type", flush=True)\n        self.select_business_type_cascade(\n            level1=business_type_l1, level2=business_type_l2\n        )\n        print("DBG_DOMESTIC: business_type done", flush=True)',
        ),
        (
            "self.select_industry_cascade(",
            'print("DBG_DOMESTIC: industry", flush=True)\n        self.select_industry_cascade(',
        ),
        (
            "self.fill_domestic_region(\n            province=province, city=city, district=district\n        )",
            'print("DBG_DOMESTIC: region", flush=True)\n        self.fill_domestic_region(\n            province=province, city=city, district=district\n        )\n        print("DBG_DOMESTIC: region done", flush=True)',
        ),
        (
            "if attachment is not None and Path(attachment).is_file():",
            'print("DBG_DOMESTIC: before attachment", flush=True)\n        if attachment is not None and Path(attachment).is_file():',
        ),
        (
            "return company_name\n",
            'print("DBG_DOMESTIC: fill done", flush=True)\n        return company_name\n',
        ),
    ]
    # only apply within domestic method once
    start = text.find("def fill_create_domestic_basic")
    end = text.find("\n    def ", start + 5)
    body = text[start:end]
    for a, b in replacements:
        if a in body:
            body = body.replace(a, b, 1)
            print("patched", a[:40])
        else:
            print("miss", a[:40])
    text = text[:start] + body + text[end:]
    # confirm print
    cstart = text.find("def confirm_customer_create_save")
    cend = text.find("\n    def ", cstart + 5)
    cbody = text[cstart:cend]
    if "DBG_CONFIRM" not in cbody:
        cbody = cbody.replace(
            "def confirm_customer_create_save(self) -> None:",
            'def confirm_customer_create_save(self) -> None:\n        print("DBG_CONFIRM: start", flush=True)',
            1,
        )
        cbody = cbody.replace(
            'raise AssertionError("\u672a\u627e\u5230\u65b0\u5efa\u5ba2\u6237\u300c\u786e\u5b9a/\u4fdd\u5b58\u300d\u6309\u94ae")',
            'print("DBG_CONFIRM: no button", flush=True)\n        raise AssertionError("\u672a\u627e\u5230\u65b0\u5efa\u5ba2\u6237\u300c\u786e\u5b9a/\u4fdd\u5b58\u300d\u6309\u94ae")',
            1,
        )
        # before return after click
        cbody = cbody.replace(
            "self.page.wait_for_timeout(1200)\n                    discard2",
            'print("DBG_CONFIRM: clicked", flush=True)\n                    self.page.wait_for_timeout(1200)\n                    discard2',
            1,
        )
        text = text[:cstart] + cbody + text[cend:]
        print("confirm dbg added")
    path.write_text(text, encoding="utf-8")
    print("dbg injected")
else:
    print("dbg already present")
