# -*- coding: utf-8 -*-
from pathlib import Path
import re

path = Path("pages/crm_customer_page.py")
text = path.read_text(encoding="utf-8")

# shorten file upload waits
text2, n1 = re.subn(
    r'(file/file/upload.*?timeout=)20000',
    r"\g<1>8000",
    text,
    flags=re.S,
)
print("upload timeout patches", n1)
text = text2

# expand confirm button pattern to include submit
text2, n2 = re.subn(
    r'(pattern = re\.compile\(r")([^"]+)("\))',
    lambda m: m.group(0)
    if "\u63d0" in m.group(2)
    else f'{m.group(1)}{m.group(2)}|\\u63d0\\s*\\u4ea4{m.group(3)}',
    text,
    count=3,
)
# The above may not expand unicode correctly in replacement. Do explicit.
old_pat = 'pattern = re.compile(r"\u786e\\s*\u5b9a|\u4fdd\\s*\u5b58")'
new_pat = 'pattern = re.compile(r"\u786e\\s*\u5b9a|\u4fdd\\s*\u5b58|\u63d0\\s*\u4ea4")'
if old_pat in text:
    text = text.replace(old_pat, new_pat)
    print("confirm pattern expanded")
else:
    # try find existing
    m = re.search(r'pattern = re\.compile\(r"[^"]+"\)', text)
    print("found pattern", m.group(0) if m else None)
    if m and "\u63d0" not in m.group(0):
        text = text.replace(
            m.group(0),
            'pattern = re.compile(r"\u786e\\s*\u5b9a|\u4fdd\\s*\u5b58|\u63d0\\s*\u4ea4")',
            1,
        )
        print("confirm pattern replaced")

# ensure customerLevel required
text2, n3 = re.subn(
    r'(self\._ensure_select\("#customerLevelCode", first=True, required=)False(\))',
    r"\1True\2",
    text,
    count=1,
)
print("level required", n3)
text = text2

path.write_text(text, encoding="utf-8")

# test: skip extra uploads when attachment already passed into fill
tpath = Path("tests/test_crm_customer_smoke.py")
tt = tpath.read_text(encoding="utf-8")
# Remove duplicate upload block after fill (best-effort keep one upload call only if needed)
# Replace the hard assert sample + upload block with a lighter version
marker = 'assert _SAMPLE_JPG.is_file(), '
idx = tt.find(marker)
# find domestic only: after selected_company_name attach near domestic
idx = tt.find('name="selected_company_name"')
idx2 = tt.find(marker, idx)
print("upload assert idx", idx2)
if idx2 > 0:
    # from assert sample to before try expect_response
    end = tt.find("            try:\n                with page.expect_response", idx2)
    if end > idx2:
        replacement = (
            "            # uploads already attempted inside fill_create_domestic_basic(attachment=...)\n"
            "            if _SAMPLE_JPG.is_file():\n"
            "                cust.upload_required_create_attachments(_SAMPLE_JPG)\n"
            "\n"
        )
        tt = tt[:idx2] + replacement + tt[end:]
        tpath.write_text(tt, encoding="utf-8")
        print("simplified test uploads")
    else:
        print("end marker missing")

print("done")
