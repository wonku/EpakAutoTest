"""CRM 客户 UI 冒烟（国内 / 海外拆分）。

来源:
  - recordings/20260803-142110：国内客户 + 工商信息查询
  - recordings/20260807-143309：海外客户新建

国内链路: 新建 → 保存 → 列表搜索 → 打开详情（主表+联系人Tab）断言与新建一致

运行:
  $env:HEADLESS="false"
  pytest tests/test_crm_customer_smoke.py -m crm_ui -v -s --tb=short
"""
from __future__ import annotations

import re
from datetime import datetime

import allure
import pytest
from playwright.sync_api import expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from config.settings import (
    APP_HOME_URL,
    CRM_CUSTOMER_ROLLBACK_ENABLED,
    CRM_DB_HOST,
    CRM_UI_CUSTOMER_BUSINESS_SCOPE,
    CRM_UI_CUSTOMER_BUSINESS_TYPE_L1,
    CRM_UI_CUSTOMER_BUSINESS_TYPE_L2,
    CRM_UI_CUSTOMER_CITY,
    CRM_UI_CUSTOMER_COMPANY_EMAIL,
    CRM_UI_CUSTOMER_COMPANY_PHONE,
    CRM_UI_CUSTOMER_CONTACT_DEPARTMENT,
    CRM_UI_CUSTOMER_CONTACT_POSITION,
    CRM_UI_CUSTOMER_COOPERATION_SUPPLIER,
    CRM_UI_CUSTOMER_COUNTRY,
    CRM_UI_CUSTOMER_DISTRICT,
    CRM_UI_CUSTOMER_DOMESTIC_FULL_NAME,
    CRM_UI_CUSTOMER_DOMESTIC_KEYWORD,
    CRM_UI_CUSTOMER_ESTABLISHMENT_TIME,
    CRM_UI_CUSTOMER_FOLLOW_KEYWORD,
    CRM_UI_CUSTOMER_INDUSTRY_L1,
    CRM_UI_CUSTOMER_INDUSTRY_L2,
    CRM_UI_CUSTOMER_INQUIRY_KEYWORD,
    CRM_UI_CUSTOMER_OFFICE_ADDRESS,
    CRM_UI_CUSTOMER_PEOPLE_NUM,
    CRM_UI_CUSTOMER_PREDICT_MARKET,
    CRM_UI_CUSTOMER_PROVINCE,
    CRM_UI_CUSTOMER_REGISTERED_CAPITAL,
    CRM_UI_CUSTOMER_REMARK,
    CRM_UI_CUSTOMER_REQUIREMENT_CLARITY,
    CRM_UI_CUSTOMER_SALES_MARKET,
    CRM_UI_CUSTOMER_STANDARD_INDUSTRY,
    CRM_UI_CUSTOMER_YEAR_PURCHASE_QTY,
    CRM_UI_PAUSE_ON_FAILURE,
    PLATFORM_BASE_URL,
    PROJECT_ROOT,
)
from pages.crm_customer_page import CrmCustomerPage
from pages.crm_page import CrmPage
from pages.home_page import HomePage
from utils.crm_data_rollback import (
    CreatedCustomerRef,
    db_config_ready,
    rollback_created_customers,
    rollback_customer_by_company_name,
)

pytestmark = pytest.mark.crm_ui

CUSTOMER_URL = f"{PLATFORM_BASE_URL}/memberCenter/crm2Ability/customer"
_SAMPLE_JPG = PROJECT_ROOT / "testdata" / "order" / "contract_sample.jpg"


@pytest.fixture
def created_customers():
    """登记本用例新建客户，teardown 强制按公司名回滚。"""
    refs: list[CreatedCustomerRef] = []
    yield refs
    for ref in reversed(refs):
        name = (ref.company_name or "").strip()
        if not name:
            continue
        try:
            rollback_customer_by_company_name(name, force=True)
        except Exception:
            # 保留批量入口兜底
            try:
                rollback_created_customers([ref])
            except Exception:
                pass


def _open_crm_customer(authenticated_page):
    page = authenticated_page
    page.goto(APP_HOME_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    assert "login" not in page.url.lower(), f"登录态注入失败: {page.url}"
    home = HomePage(page)
    crm_tab = home.open_crm_2()
    crm_tab.wait_for_timeout(2000)
    home.assert_crm_page_loaded(crm_tab)
    page = crm_tab
    crm = CrmPage(page)
    cust = CrmCustomerPage(page)
    page.set_default_timeout(25000)
    page.goto(CUSTOMER_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    if "customer" not in page.url.lower():
        crm.open_menu_path("客户")
    crm.assert_menu_reachable("客户")
    return page, crm, cust


def _register_created(
    refs: list[CreatedCustomerRef],
    *,
    company_name: str,
    crm_auth=None,
    crm_customer_service=None,
) -> CreatedCustomerRef:
    customer_id = None
    if crm_auth is not None and crm_customer_service is not None and company_name:
        try:
            customer_id = crm_customer_service.find_id_by_company_name(
                crm_auth, company_name
            )
        except Exception:
            customer_id = None
    ref = CreatedCustomerRef(company_name=company_name, customer_id=customer_id)
    refs.append(ref)
    return ref


@allure.feature("CRM UI 改版回归")
@allure.story("客户-国内新建")
@allure.title("新建国内客户：保存 → 搜索开详情 → 断言与新建一致")
def test_crm_customer_create_domestic_smoke(
    authenticated_page,
    created_customers,
    crm_auth,
    crm_customer_service,
):
    page = authenticated_page
    stamp = datetime.now().strftime("%m%d%H%M%S")
    contact_name = f"自动化联系人{stamp}"
    # 合法大陆手机号：1[3-9] + 9 位；禁止 "10..." 等无效号段
    contact_phone = f"138{stamp[-8:]}"[:11]
    company_name = ""
    register_address = (
        f"{CRM_UI_CUSTOMER_PROVINCE}{CRM_UI_CUSTOMER_CITY}自动化注册地址"
    )
    expected_saved: dict[str, str] = {}

    try:
        with allure.step("进入 CRM 客户列表"):
            page, crm, cust = _open_crm_customer(page)

        cleanup_name = (
            CRM_UI_CUSTOMER_DOMESTIC_FULL_NAME or "苏州糖烟酒有限公司"
        ).strip()
        with allure.step(f"创建前清重回滚: {cleanup_name}"):
            rolled = False
            roll_err = ""
            try:
                rolled = rollback_customer_by_company_name(cleanup_name, force=True)
            except Exception as exc:  # noqa: BLE001
                roll_err = str(exc)
            allure.attach(
                str(
                    {
                        "company": cleanup_name,
                        "rolled": rolled,
                        "db_ready": db_config_ready(),
                        "rollback_enabled": CRM_CUSTOMER_ROLLBACK_ENABLED,
                        "db_host": CRM_DB_HOST or "",
                        "error": roll_err,
                    }
                ),
                name="pre_create_rollback",
                attachment_type=allure.attachment_type.TEXT,
            )

        with allure.step(
            f"新建国内客户（工商关键字: {CRM_UI_CUSTOMER_DOMESTIC_KEYWORD}）"
        ):
            cust.open_create_form(kind="domestic")
            company_name = cust.fill_create_domestic_basic(
                company_keyword=CRM_UI_CUSTOMER_DOMESTIC_KEYWORD,
                contact_name=contact_name,
                contact_phone=contact_phone,
                follow_user_keyword=CRM_UI_CUSTOMER_FOLLOW_KEYWORD,
                company_email=CRM_UI_CUSTOMER_COMPANY_EMAIL,
                contact_position=CRM_UI_CUSTOMER_CONTACT_POSITION,
                contact_department=CRM_UI_CUSTOMER_CONTACT_DEPARTMENT,
                business_type_l1=CRM_UI_CUSTOMER_BUSINESS_TYPE_L1,
                business_type_l2=CRM_UI_CUSTOMER_BUSINESS_TYPE_L2,
                industry_l1=CRM_UI_CUSTOMER_INDUSTRY_L1,
                industry_l2=CRM_UI_CUSTOMER_INDUSTRY_L2,
                company_people_num=CRM_UI_CUSTOMER_PEOPLE_NUM,
                company_phone=CRM_UI_CUSTOMER_COMPANY_PHONE,
                registered_capital=CRM_UI_CUSTOMER_REGISTERED_CAPITAL,
                establishment_time=CRM_UI_CUSTOMER_ESTABLISHMENT_TIME,
                business_scope=CRM_UI_CUSTOMER_BUSINESS_SCOPE,
                standard_industry=CRM_UI_CUSTOMER_STANDARD_INDUSTRY,
                province=CRM_UI_CUSTOMER_PROVINCE,
                city=CRM_UI_CUSTOMER_CITY,
                district=CRM_UI_CUSTOMER_DISTRICT,
                office_address=CRM_UI_CUSTOMER_OFFICE_ADDRESS,
                register_address=register_address,
                cooperation_supplier=CRM_UI_CUSTOMER_COOPERATION_SUPPLIER,
                sales_market=CRM_UI_CUSTOMER_SALES_MARKET,
                predict_market=CRM_UI_CUSTOMER_PREDICT_MARKET,
                inquiry_keyword=CRM_UI_CUSTOMER_INQUIRY_KEYWORD,
                year_purchase_qty=CRM_UI_CUSTOMER_YEAR_PURCHASE_QTY,
                requirement_clarity=CRM_UI_CUSTOMER_REQUIREMENT_CLARITY,
                remark=CRM_UI_CUSTOMER_REMARK,
                attachment=_SAMPLE_JPG if _SAMPLE_JPG.is_file() else None,
            )
            expected_saved = {
                "company_name": company_name,
                "contact_name": contact_name,
                "contact_phone": contact_phone,
                "company_email": CRM_UI_CUSTOMER_COMPANY_EMAIL,
                "company_people_num": CRM_UI_CUSTOMER_PEOPLE_NUM,
                "annual_turnover": "1000",
                "office_address": CRM_UI_CUSTOMER_OFFICE_ADDRESS,
                "cooperation_supplier": CRM_UI_CUSTOMER_COOPERATION_SUPPLIER,
                "sales_market": CRM_UI_CUSTOMER_SALES_MARKET,
                "year_purchase_qty": CRM_UI_CUSTOMER_YEAR_PURCHASE_QTY,
                "remark": CRM_UI_CUSTOMER_REMARK,
                "contact_department": CRM_UI_CUSTOMER_CONTACT_DEPARTMENT,
                "province": CRM_UI_CUSTOMER_PROVINCE,
                "city": CRM_UI_CUSTOMER_CITY,
                "district": CRM_UI_CUSTOMER_DISTRICT,
                "business_type_l1": CRM_UI_CUSTOMER_BUSINESS_TYPE_L1,
                "business_type_l2": CRM_UI_CUSTOMER_BUSINESS_TYPE_L2,
                "industry_l1": CRM_UI_CUSTOMER_INDUSTRY_L1,
                "follow_user_keyword": CRM_UI_CUSTOMER_FOLLOW_KEYWORD,
                "contact_position": CRM_UI_CUSTOMER_CONTACT_POSITION,
            }
            allure.attach(
                company_name,
                name="selected_company_name",
                attachment_type=allure.attachment_type.TEXT,
            )
            # uploads already attempted inside fill_create_domestic_basic(attachment=...)
            if _SAMPLE_JPG.is_file():
                cust.upload_required_create_attachments(_SAMPLE_JPG)

            try:
                with page.expect_response(
                    lambda r: "customer/save" in (r.url or "")
                    and r.request.method == "POST",
                    timeout=25000,
                ) as save_info:
                    cust.confirm_customer_create_save()
                save_resp = save_info.value
                try:
                    body = save_resp.json()
                    allure.attach(
                        str(body),
                        name="domestic_customer_save_response",
                        attachment_type=allure.attachment_type.TEXT,
                    )
                    if re.search(r"重复|已存在", str(body)):
                        raise AssertionError(f"customer/save 返回重复: {body}")
                    code = body.get("code") if isinstance(body, dict) else None
                    msg = body.get("message") if isinstance(body, dict) else body
                    # CRM 成功码一般为 1000
                    if code not in (0, "0", 200, "200", 1000, "1000", None):
                        raise AssertionError(
                            f"customer/save 业务失败: code={code} message={msg}"
                        )
                except AssertionError:
                    raise
                except Exception:
                    pass
            except Exception as exc:
                dup_hit = cust.handle_customer_duplicate_modal() or (
                    "重复" in str(exc) or "已存在" in str(exc)
                )
                if dup_hit:
                    dup_name = company_name or cleanup_name
                    try:
                        rollback_customer_by_company_name(
                            dup_name, force=True
                        )
                    except Exception as rb_exc:  # noqa: BLE001
                        allure.attach(
                            str(rb_exc),
                            name="duplicate_rollback_error",
                            attachment_type=allure.attachment_type.TEXT,
                        )
                    page.wait_for_timeout(800)
                    cust.handle_customer_duplicate_modal()
                    cust.open_create_form(kind="domestic")
                    company_name = cust.fill_create_domestic_basic(
                        company_keyword=CRM_UI_CUSTOMER_DOMESTIC_KEYWORD,
                        contact_name=contact_name,
                        contact_phone=contact_phone,
                        follow_user_keyword=CRM_UI_CUSTOMER_FOLLOW_KEYWORD,
                        company_email=CRM_UI_CUSTOMER_COMPANY_EMAIL,
                        contact_position=CRM_UI_CUSTOMER_CONTACT_POSITION,
                        contact_department=CRM_UI_CUSTOMER_CONTACT_DEPARTMENT,
                        business_type_l1=CRM_UI_CUSTOMER_BUSINESS_TYPE_L1,
                        business_type_l2=CRM_UI_CUSTOMER_BUSINESS_TYPE_L2,
                        industry_l1=CRM_UI_CUSTOMER_INDUSTRY_L1,
                        industry_l2=CRM_UI_CUSTOMER_INDUSTRY_L2,
                        company_people_num=CRM_UI_CUSTOMER_PEOPLE_NUM,
                        company_phone=CRM_UI_CUSTOMER_COMPANY_PHONE,
                        registered_capital=CRM_UI_CUSTOMER_REGISTERED_CAPITAL,
                        establishment_time=CRM_UI_CUSTOMER_ESTABLISHMENT_TIME,
                        business_scope=CRM_UI_CUSTOMER_BUSINESS_SCOPE,
                        standard_industry=CRM_UI_CUSTOMER_STANDARD_INDUSTRY,
                        province=CRM_UI_CUSTOMER_PROVINCE,
                        city=CRM_UI_CUSTOMER_CITY,
                        district=CRM_UI_CUSTOMER_DISTRICT,
                        office_address=CRM_UI_CUSTOMER_OFFICE_ADDRESS,
                        register_address=register_address,
                        cooperation_supplier=CRM_UI_CUSTOMER_COOPERATION_SUPPLIER,
                        sales_market=CRM_UI_CUSTOMER_SALES_MARKET,
                        predict_market=CRM_UI_CUSTOMER_PREDICT_MARKET,
                        inquiry_keyword=CRM_UI_CUSTOMER_INQUIRY_KEYWORD,
                        year_purchase_qty=CRM_UI_CUSTOMER_YEAR_PURCHASE_QTY,
                        requirement_clarity=CRM_UI_CUSTOMER_REQUIREMENT_CLARITY,
                        remark=CRM_UI_CUSTOMER_REMARK,
                        attachment=_SAMPLE_JPG if _SAMPLE_JPG.is_file() else None,
                    )
                    expected_saved["company_name"] = company_name
                    if _SAMPLE_JPG.is_file():
                        cust.upload_required_create_attachments(_SAMPLE_JPG)
                        cust.upload_by_field_label("客户背调报告", _SAMPLE_JPG)
                    with page.expect_response(
                        lambda r: "customer/save" in (r.url or "")
                        and r.request.method == "POST",
                        timeout=25000,
                    ) as save_info_dup:
                        cust.confirm_customer_create_save()
                    save_resp = save_info_dup.value
                elif (
                    "Timeout" not in type(exc).__name__
                    and "timeout" not in str(exc).lower()
                ):
                    raise
                else:
                    errs = cust.collect_create_form_errors()
                    cust._dismiss_blocking_overlays()
                    try:
                        cust.fill_domestic_region(
                            province=CRM_UI_CUSTOMER_PROVINCE,
                            city=CRM_UI_CUSTOMER_CITY,
                            district=CRM_UI_CUSTOMER_DISTRICT,
                        )
                        cust._ensure_input(
                            "#officeAddress",
                            CRM_UI_CUSTOMER_OFFICE_ADDRESS,
                            required=True,
                        )
                        cust._ensure_input(
                            "#registerAddress",
                            f"{CRM_UI_CUSTOMER_PROVINCE}{CRM_UI_CUSTOMER_CITY}自动化注册地址",
                            required=True,
                        )
                    except Exception:
                        pass
                    if _SAMPLE_JPG.is_file():
                        cust.upload_required_create_attachments(_SAMPLE_JPG)
                        for label in (
                            "客户背调报告",
                            "背调报告",
                            "客户名片",
                            "客户报告",
                        ):
                            if page.locator(
                                ".ant-form-item-label", has_text=label
                            ).count() > 0:
                                cust.upload_by_field_label(label, _SAMPLE_JPG)
                    joined = "\n".join(errs)
                    if "经营类型" in joined:
                        cust.select_business_type_cascade(
                            level1=CRM_UI_CUSTOMER_BUSINESS_TYPE_L1,
                            level2=CRM_UI_CUSTOMER_BUSINESS_TYPE_L2,
                        )
                    if "行业" in joined:
                        cust.select_industry_cascade(
                            level1=CRM_UI_CUSTOMER_INDUSTRY_L1 or "食品行业",
                            level2=CRM_UI_CUSTOMER_INDUSTRY_L2 or "",
                        )
                    if ("省" in joined) or ("城市" in joined) or ("区" in joined):
                        cust.fill_domestic_region(
                            province=CRM_UI_CUSTOMER_PROVINCE,
                            city=CRM_UI_CUSTOMER_CITY,
                            district=CRM_UI_CUSTOMER_DISTRICT,
                        )
                    if "办公地址" in joined:
                        cust._ensure_input(
                            "#officeAddress",
                            CRM_UI_CUSTOMER_OFFICE_ADDRESS,
                            required=True,
                        )
                    if "注册地址" in joined:
                        cust._ensure_input(
                            "#registerAddress",
                            f"{CRM_UI_CUSTOMER_PROVINCE}{CRM_UI_CUSTOMER_CITY}自动化注册地址",
                            required=True,
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
                        if cust.handle_customer_duplicate_modal():
                            raise AssertionError(
                                f"客户重复且需配置 CRM_DB_* 清重: company={company_name or cleanup_name}; "
                                f"db_ready={db_config_ready()}"
                            ) from exc2
                        errs2 = cust.collect_create_form_errors()
                        raise AssertionError(
                            f"domestic create missed customer/save; form errors: {errs2 or errs}"
                        ) from exc2
            page.wait_for_timeout(1500)

        with allure.step("登记回滚引用并列表确认"):
            ref = _register_created(
                created_customers,
                company_name=company_name,
                crm_auth=crm_auth,
                crm_customer_service=crm_customer_service,
            )
            api_id = None
            try:
                api_id = crm_customer_service.find_id_by_company_name(
                    crm_auth, company_name
                )
            except Exception:
                api_id = None
            if api_id:
                ref.customer_id = api_id
            cust.search_by_company_name(company_name)
            row = page.locator(".ant-table-tbody a").filter(has_text=company_name)
            if row.count() > 0:
                expect(row.first).to_be_visible(timeout=20000)
            else:
                assert api_id, (
                    f"国内客户保存后列表与接口均未找到: {company_name}"
                )

        with allure.step("打开详情：主表断言 + 联系人Tab断言"):
            expected_saved["company_name"] = company_name
            allure.attach(
                str(expected_saved),
                name="expected_saved_fields",
                attachment_type=allure.attachment_type.TEXT,
            )
            # 列表已搜过则直接开详情；若无行则再搜一次
            row = page.locator(".ant-table-tbody a").filter(has_text=company_name)
            if row.count() == 0:
                cust.search_by_company_name(company_name)
            cust.open_row_by_company(company_name)
            actual = cust.assert_domestic_saved_matches(expected_saved, via_edit=True)
            allure.attach(
                str(actual),
                name="actual_detail_snapshot",
                attachment_type=allure.attachment_type.TEXT,
            )

        with allure.step("校验未掉回登录页"):
            expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=10000)
            crm.assert_not_kicked_to_login()
    except Exception:
        if company_name:
            _register_created(
                created_customers,
                company_name=company_name,
                crm_auth=crm_auth,
                crm_customer_service=crm_customer_service,
            )
        try:
            png = page.screenshot(full_page=True, timeout=10000)
            allure.attach(
                png, name="customer_domestic_failed", attachment_type=allure.attachment_type.PNG
            )
        except Exception:
            pass
        if CRM_UI_PAUSE_ON_FAILURE:
            page.pause()
        raise


@allure.feature("CRM UI 改版回归")
@allure.story("客户-国外新建")
@allure.title("新建国外客户 → 保存 → 列表可见")
def test_crm_customer_create_overseas_smoke(
    authenticated_page,
    created_customers,
    crm_auth,
    crm_customer_service,
):
    page = authenticated_page
    stamp = datetime.now().strftime("%m%d%H%M%S")
    # 国外客户不走工商校验：随机企业名 + 点选下拉填入
    company_name = f"AutoOverseas{stamp}"
    contact_name = f"AutoContact{stamp}"
    contact_phone = f"138{stamp[-8:]}"[:11]
    contact_email = f"auto{stamp}@qq.com"

    try:
        with allure.step("进入 CRM 客户列表"):
            page, crm, cust = _open_crm_customer(page)

        with allure.step(f"新建国外客户: {company_name}"):
            cust.open_create_form(kind="overseas")
            company_name = cust.fill_create_overseas_basic(
                company_name=company_name,
                contact_name=contact_name,
                contact_phone=contact_phone,
                contact_email=contact_email,
                country=CRM_UI_CUSTOMER_COUNTRY,
                follow_user_keyword=CRM_UI_CUSTOMER_FOLLOW_KEYWORD,
                company_email=CRM_UI_CUSTOMER_COMPANY_EMAIL,
                main_product="主营商品自动化",
                main_business="主营业务自动化",
                annual_turnover="1000",
                company_people_num="100",
                overseas_address="自动化详细地址",
                remark="自动化基础备注",
                inquiry_remark=f"自动化询盘备注{stamp}",
                import_country="日本",
                target_market=CRM_UI_CUSTOMER_COUNTRY,
                business_type_l1=CRM_UI_CUSTOMER_BUSINESS_TYPE_L1,
                business_type_l2=CRM_UI_CUSTOMER_BUSINESS_TYPE_L2,
                contact_position=CRM_UI_CUSTOMER_CONTACT_POSITION,
            )
            allure.attach(
                company_name,
                name="selected_overseas_company_name",
                attachment_type=allure.attachment_type.TEXT,
            )
            assert _SAMPLE_JPG.is_file(), f"缺少上传样例文件: {_SAMPLE_JPG}"
            uploaded = cust.upload_required_create_attachments(_SAMPLE_JPG)
            assert uploaded >= 3, (
                f"客户名片/客户报告/海关记录附件上传不足（成功 {uploaded} 处），"
                f"请检查上传控件"
            )
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
                errs = []
                try:
                    errs = page.locator(
                        ".ant-form-item-explain-error, .ant-message-error"
                    ).all_inner_texts()
                except Exception:
                    errs = []
                # 校验「请上传」时再补传一次并重试保存
                if any("上传" in (e or "") for e in errs) and _SAMPLE_JPG.is_file():
                    cust.upload_required_create_attachments(_SAMPLE_JPG)
                    with page.expect_response(
                        lambda r: "customer/save" in (r.url or "")
                        and r.request.method == "POST",
                        timeout=25000,
                    ) as save_info2:
                        cust.confirm_customer_create_save()
                    save_resp = save_info2.value
                else:
                    raise AssertionError(
                        f"未触发 customer/save（多为表单校验/按钮未点到）: {errs}"
                    ) from exc
            try:
                save_body = save_resp.json()
            except Exception:
                save_body = {"raw": save_resp.text()[:500]}
            allure.attach(
                str(save_body),
                name="customer_save_response",
                attachment_type=allure.attachment_type.TEXT,
            )
            assert save_resp.ok, f"customer/save HTTP 失败: {save_resp.status}"
            assert save_body.get("code") == 1000, f"customer/save 业务失败: {save_body}"
            page.wait_for_timeout(1000)

        with allure.step("登记回滚引用并列表查询"):
            ref = _register_created(
                created_customers,
                company_name=company_name,
                crm_auth=crm_auth,
                crm_customer_service=crm_customer_service,
            )
            # 优先用接口确认已落库
            api_id = crm_customer_service.find_id_by_company_name(crm_auth, company_name)
            if api_id:
                ref.customer_id = api_id
            cust.search_by_company_name(company_name)
            row = page.locator(".ant-table-tbody a").filter(has_text=company_name)
            if row.count() == 0:
                row = page.locator(".ant-table-tbody a").filter(has_text=stamp)
            if row.count() == 0 and api_id:
                # 接口已有数据则 UI 列表仅告警式放宽：再查一次空过滤是否可见
                cust.search_by_company_name("")
                page.wait_for_timeout(800)
                row = page.locator(".ant-table-tbody a").filter(has_text=stamp)
            expect(row.first).to_be_visible(timeout=20000)
            assert api_id or row.count() > 0, (
                f"海外客户保存成功但列表/接口均未找到: {company_name}"
            )

        with allure.step("校验未掉回登录页"):
            expect(page).not_to_have_url(re.compile(r"/user/login"), timeout=10000)
            crm.assert_not_kicked_to_login()
    except Exception:
        _register_created(
            created_customers,
            company_name=company_name,
            crm_auth=crm_auth,
            crm_customer_service=crm_customer_service,
        )
        try:
            png = page.screenshot(full_page=True, timeout=10000)
            allure.attach(
                png, name="customer_overseas_failed", attachment_type=allure.attachment_type.PNG
            )
        except Exception:
            pass
        if CRM_UI_PAUSE_ON_FAILURE:
            page.pause()
        raise
