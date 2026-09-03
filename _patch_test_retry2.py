# -*- coding: utf-8 -*-
from pathlib import Path

path = Path("tests/test_crm_customer_smoke.py")
text = path.read_text(encoding="utf-8")

start = text.find("            except Exception as exc:\n                if \"Timeout\" not in type(exc).__name__")
# only first occurrence should be domestic (overseas may also have it)
# find domestic by looking after domestic_customer_save_response
anchor = text.find('name="domestic_customer_save_response"')
assert anchor > 0
start = text.find("            except Exception as exc:", anchor)
end = text.find("            page.wait_for_timeout(1500)", start)
assert start > 0 and end > start, (start, end)
print("replace range", start, end)

new = '''            except Exception as exc:
                if "Timeout" not in type(exc).__name__ and "timeout" not in str(exc).lower():
                    raise
                errs = cust.collect_create_form_errors()
                if _SAMPLE_JPG.is_file():
                    cust.upload_required_create_attachments(_SAMPLE_JPG)
                    for label in (
                        "\u5ba2\u6237\u80cc\u8c03\u62a5\u544a",
                        "\u80cc\u8c03\u62a5\u544a",
                        "\u5ba2\u6237\u540d\u7247",
                        "\u5ba2\u6237\u62a5\u544a",
                    ):
                        if page.locator(".ant-form-item-label", has_text=label).count() > 0:
                            cust.upload_by_field_label(label, _SAMPLE_JPG)
                joined = "\\n".join(errs)
                if "\u7ecf\u8425\u7c7b\u578b" in joined:
                    cust.select_business_type_cascade(
                        level1=CRM_UI_CUSTOMER_BUSINESS_TYPE_L1,
                        level2=CRM_UI_CUSTOMER_BUSINESS_TYPE_L2,
                    )
                if "\u884c\u4e1a" in joined:
                    levels = [x for x in (CRM_UI_CUSTOMER_INDUSTRY_L1, CRM_UI_CUSTOMER_INDUSTRY_L2) if x]
                    cust.select_cascader_levels(
                        "#industryCode",
                        levels=levels or None,
                        depth=2,
                        required=True,
                        field_name="\u884c\u4e1a",
                    )
                if "\u5ba2\u6237\u7ea7\u522b" in joined:
                    if page.locator("#customerLevelCode").count() > 0:
                        cust._ensure_select("#customerLevelCode", first=True, required=True)
                    else:
                        cust._ensure_select("#customerGradeCode", first=True, required=True)
                if "\u516c\u53f8\u4eba\u6570" in joined:
                    cust._ensure_input("#companyPeopleNum", CRM_UI_CUSTOMER_PEOPLE_NUM, required=True)
                if ("\u7701" in joined) or ("\u57ce\u5e02" in joined):
                    cust.fill_domestic_region(
                        province=CRM_UI_CUSTOMER_PROVINCE,
                        city=CRM_UI_CUSTOMER_CITY,
                        district=CRM_UI_CUSTOMER_DISTRICT,
                    )
                if "\u7ecf\u8425\u8303\u56f4" in joined:
                    cust._ensure_input(
                        "#businessScope",
                        CRM_UI_CUSTOMER_BUSINESS_SCOPE,
                        required=True,
                        as_textarea=True,
                    )
                try:
                    with page.expect_response(
                        lambda r: "customer/save" in (r.url or "")
                        and r.request.method == "POST",
                        timeout=25000,
                    ) as save_info2:
                        cust.confirm_customer_create_save()
                    save_resp = save_info2.value
                    try:
                        allure.attach(
                            str(save_resp.json()),
                            name="domestic_customer_save_response_retry",
                            attachment_type=allure.attachment_type.TEXT,
                        )
                    except Exception:
                        pass
                except Exception as exc2:
                    errs2 = cust.collect_create_form_errors()
                    raise AssertionError(
                        f"domestic create missed customer/save; form errors: {errs2 or errs}"
                    ) from exc2
'''

text = text[:start] + new + text[end:]
path.write_text(text, encoding="utf-8")
print("patched ok")
