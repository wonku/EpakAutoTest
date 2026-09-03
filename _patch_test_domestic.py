# -*- coding: utf-8 -*-
from pathlib import Path
import re

path = Path("tests/test_crm_customer_smoke.py")
text = path.read_text(encoding="utf-8")

old = '''            company_name = cust.fill_create_domestic_basic(
                company_keyword=CRM_UI_CUSTOMER_DOMESTIC_KEYWORD,
                contact_name=contact_name,
                contact_phone=contact_phone,
                follow_user_keyword=CRM_UI_CUSTOMER_FOLLOW_KEYWORD,
                company_email=CRM_UI_CUSTOMER_COMPANY_EMAIL,
            )
            allure.attach(
                company_name,
                name="selected_company_name",
                attachment_type=allure.attachment_type.TEXT,
            )
            cust.confirm_customer_create_save()
            page.wait_for_timeout(1500)'''

new = '''            company_name = cust.fill_create_domestic_basic(
                company_keyword=CRM_UI_CUSTOMER_DOMESTIC_KEYWORD,
                contact_name=contact_name,
                contact_phone=contact_phone,
                follow_user_keyword=CRM_UI_CUSTOMER_FOLLOW_KEYWORD,
                company_email=CRM_UI_CUSTOMER_COMPANY_EMAIL,
                contact_position=CRM_UI_CUSTOMER_CONTACT_POSITION,
                business_type_l1=CRM_UI_CUSTOMER_BUSINESS_TYPE_L1,
                business_type_l2=CRM_UI_CUSTOMER_BUSINESS_TYPE_L2,
            )
            allure.attach(
                company_name,
                name="selected_company_name",
                attachment_type=allure.attachment_type.TEXT,
            )
            assert _SAMPLE_JPG.is_file(), f"missing upload sample: {_SAMPLE_JPG}"
            uploaded = cust.upload_required_create_attachments(_SAMPLE_JPG)
            # domestic may hide customs attachment; upload whatever is visible
            for label in (
                "\u5ba2\u6237\u80cc\u8c03\u62a5\u544a",
                "\u80cc\u8c03\u62a5\u544a",
                "\u5ba2\u6237\u540d\u7247",
                "\u5ba2\u6237\u62a5\u544a",
            ):
                if cust.page.locator(".ant-form-item-label", has_text=label).count() > 0:
                    cust.upload_by_field_label(label, _SAMPLE_JPG)
            allure.attach(
                str(uploaded),
                name="upload_count",
                attachment_type=allure.attachment_type.TEXT,
            )
            try:
                with page.expect_response(
                    lambda r: "customer/save" in (r.url or "")
                    and r.request.method == "POST",
                    timeout=25000,
                ) as save_info:
                    cust.confirm_customer_create_save()
                save_resp = save_info.value
            except Exception as exc:
                if "Timeout" not in type(exc).__name__ and "timeout" not in str(exc).lower():
                    raise
                errs = cust.collect_create_form_errors()
                # retry once after uploading any remaining attachments
                if _SAMPLE_JPG.is_file():
                    cust.upload_required_create_attachments(_SAMPLE_JPG)
                # refill region/required selects that still show errors
                if any("\u7ecf\u8425\u7c7b\u578b" in (e or "") for e in errs):
                    cust.select_business_type_cascade(
                        level1=CRM_UI_CUSTOMER_BUSINESS_TYPE_L1,
                        level2=CRM_UI_CUSTOMER_BUSINESS_TYPE_L2,
                    )
                if any("\u884c\u4e1a" in (e or "") for e in errs):
                    cust.select_cascader_levels(
                        "#industryCode", depth=2, required=True, field_name="\u884c\u4e1a"
                    )
                if any("\u5ba2\u6237\u7ea7\u522b" in (e or "") for e in errs):
                    if cust.page.locator("#customerLevelCode").count() > 0:
                        cust._ensure_select("#customerLevelCode", first=True, required=True)
                    else:
                        cust._ensure_select("#customerGradeCode", first=True, required=True)
                if any("\u516c\u53f8\u4eba\u6570" in (e or "") for e in errs):
                    cust._ensure_input("#companyPeopleNum", "100", required=True)
                if any("\u7701" in (e or "") or "\u57ce\u5e02" in (e or "") for e in errs):
                    cust.fill_domestic_region(province="\u6c5f\u82cf", city="\u82cf\u5dde", district="\u5434\u4e2d\u533a")
                if any("\u7ecf\u8425\u8303\u56f4" in (e or "") for e in errs):
                    cust._ensure_input(
                        "#businessScope",
                        "\u81ea\u52a8\u5316\u7ecf\u8425\u8303\u56f4\uff08\u6d4b\u8bd5\uff09",
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
                except Exception as exc2:
                    errs2 = cust.collect_create_form_errors()
                    raise AssertionError(
                        f"domestic create save failed; form errors={errs2 or errs}"
                    ) from exc2
            try:
                save_body = save_resp.json()
            except Exception:
                save_body = {"raw": save_resp.text()[:500]}
            allure.attach(
                str(save_body),
                name="customer_save_response",
                attachment_type=allure.attachment_type.TEXT,
            )
            assert save_resp.ok, f"customer/save HTTP failed: {save_resp.status}"
            assert save_body.get("code") == 1000, f"customer/save biz failed: {save_body}"
            page.wait_for_timeout(1500)'''

if old not in text:
    print("OLD BLOCK NOT FOUND")
    # show nearby
    i = text.find("fill_create_domestic_basic")
    print(repr(text[i:i+400]))
else:
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("test patched ok")
