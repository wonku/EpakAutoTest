# -*- coding: utf-8 -*-
from pathlib import Path

path = Path("pages/crm_customer_page.py")
text = path.read_text(encoding="utf-8")

old = '''                search = ant.locator("input.ant-select-selection-search-input")
                if search.count() == 0:
                    search = self.page.locator(selector)
                if kw:
                    search.first.fill("")
                    search.first.fill(kw)
                    self.page.wait_for_timeout(1200)
                    self._wait_and_pick_option(
                        prefer_texts=prefer_texts or [kw],
                        keyword=kw,
                    )
                else:
                    # 无关键字：点第一项
                    opt = self._visible_select_options()
                    if opt.count() == 0:
                        self.page.keyboard.press("ArrowDown")
                        self.page.wait_for_timeout(200)
                        self.page.keyboard.press("Enter")
                        self.page.wait_for_timeout(400)
                    else:
                        opt.first.click(force=True, timeout=8000)
                        self.page.wait_for_timeout(400)'''

# Match without relying on Chinese comment
import re
pat = re.compile(
    r'''                search = ant\.locator\("input\.ant-select-selection-search-input"\)
                if search\.count\(\) == 0:
                    search = self\.page\.locator\(selector\)
                if kw:
                    search\.first\.fill\(""\)
                    search\.first\.fill\(kw\)
                    self\.page\.wait_for_timeout\(1200\)
                    self\._wait_and_pick_option\(
                        prefer_texts=prefer_texts or \[kw\],
                        keyword=kw,
                    \)
                else:
                    .*?
                    opt = self\._visible_select_options\(\)
                    if opt\.count\(\) == 0:
                        self\.page\.keyboard\.press\("ArrowDown"\)
                        self\.page\.wait_for_timeout\(200\)
                        self\.page\.keyboard\.press\("Enter"\)
                        self\.page\.wait_for_timeout\(400\)
                    else:
                        opt\.first\.click\(force=True, timeout=8000\)
                        self\.page\.wait_for_timeout\(400\)''',
    re.S,
)

new = '''                search = ant.locator("input.ant-select-selection-search-input")
                if search.count() == 0:
                    search = self.page.locator(selector)
                can_type = False
                if search.count() > 0:
                    try:
                        # Ant Select often marks search input readonly/unselectable
                        ro = search.first.get_attribute("readonly")
                        unsel = search.first.get_attribute("unselectable")
                        disabled = search.first.is_disabled()
                        can_type = (ro is None) and (unsel != "on") and (not disabled)
                    except Exception:
                        can_type = False
                if kw and can_type:
                    search.first.fill("")
                    search.first.fill(kw)
                    self.page.wait_for_timeout(1200)
                    self._wait_and_pick_option(
                        prefer_texts=prefer_texts or [kw],
                        keyword=kw,
                    )
                elif kw:
                    # readonly combobox: click matching visible option by text
                    self.page.wait_for_timeout(400)
                    opts = self._visible_select_options()
                    end_t = time.time() + 8
                    while time.time() < end_t and opts.count() == 0:
                        self.page.wait_for_timeout(200)
                        opts = self._visible_select_options()
                    matched = opts.filter(has_text=re.compile(re.escape(kw)))
                    if matched.count() == 0:
                        matched = opts.filter(has_text=kw)
                    if matched.count() > 0:
                        matched.first.click(force=True, timeout=8000)
                    elif opts.count() > 0:
                        # fallback: scan titles
                        picked = False
                        for i in range(min(opts.count(), 40)):
                            t = (opts.nth(i).inner_text() or "").strip()
                            if kw in t:
                                opts.nth(i).click(force=True, timeout=8000)
                                picked = True
                                break
                        if not picked:
                            raise AssertionError(
                                f"option not found for {selector}: {kw!r}"
                            )
                    else:
                        raise AssertionError(f"no options for {selector}")
                    self.page.wait_for_timeout(400)
                else:
                    opt = self._visible_select_options()
                    if opt.count() == 0:
                        self.page.keyboard.press("ArrowDown")
                        self.page.wait_for_timeout(200)
                        self.page.keyboard.press("Enter")
                        self.page.wait_for_timeout(400)
                    else:
                        opt.first.click(force=True, timeout=8000)
                        self.page.wait_for_timeout(400)'''

m = pat.search(text)
print("match", bool(m))
if not m:
    # fallback: find by unique lines
    a = text.find('search = ant.locator("input.ant-select-selection-search-input")')
    # find within _type_select_keyword only
    ts = text.find("def _type_select_keyword")
    a = text.find('search = ant.locator("input.ant-select-selection-search-input")', ts)
    b = text.find("if multi:", a)
    print("a,b", a, b)
    print(repr(text[a:b][:200]))
else:
    text = pat.sub(new, text, count=1)
    path.write_text(text, encoding="utf-8")
    print("patched via regex")
