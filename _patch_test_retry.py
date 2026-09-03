# -*- coding: utf-8 -*-
from pathlib import Path

path = Path("tests/test_crm_customer_smoke.py")
text = path.read_text(encoding="utf-8")

old = '''            except Exception as exc:
                if "Timeout" not in type(exc).__name__ and "timeout" not in str(exc).lower():
                    raise
                errs = []
                try:
                    errs = page.locator(
                        ".ant-form-item-explain-error, .ant-message-error"
                    ).all_inner_texts()
                except Exception:
                    errs = []
                if any("\u4e0a\u4f20" in (e or "") for e in errs) and _SAMPLE_JPG.is_file():
                    cust.upload_required_create_attachments(_SAMPLE_JPG)
                    with page.expect_response(
                        lambda r: "customer/save" in (r.url or "")
                        and r.request.method == "POST",
                        timeout=25000,
                    ):
                        cust.confirm_customer_create_save()
                else:
                    raise AssertionError(
                        f"\u56fd\u5185\u5ba2\u6237\u672a\u89e6\u53d1 customer/save\uff08\u8868\u5355/\u6821\u9a8c\uff09: {errs}"
                    ) from exc'''

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
                    cust.select_cascader_levels(
                        "#industryCode",
                        levels=[x for x in (CRM_UI_CUSTOMER_INDUSTRY_L1, CRM_UI_CUSTOMER_INDUSTRY_L2) if x] or None,
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
                if "\u7701" in joined or "\u57ce\u5e02" in joined:
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
                        f"\u56fd\u5185\u5ba2\u6237\u672a\u89e6\u53d1 customer/save\uff08\u8868\u5355/\u6821\u9a8c\uff09: {errs2 or errs}"
                    ) from exc2'''

if old not in text:
    print("except block not found exactly")
    # try find unique marker
    i = text.find("domestic_customer_save_response")
    print("marker", i)
    # dump bytes around except in domestic
    i = text.find("f\"\u56fd\u5185\u5ba2\u6237\u672a\u89e6\u53d1")
    print("cn marker", i)
    if i < 0:
        i = text.find("customer/save")
        # find second occurrence in domestic area
        print(repr(text[text.find('except Exception as exc'):text.find('except Exception as exc')+800]))
else:
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("retry block patched")
