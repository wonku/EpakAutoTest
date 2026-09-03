"""内部询价创建路由：中文商城中文单 / 中文商城英文单 / 英文商城。离线断言，不打接口。"""
from __future__ import annotations

from api.client import ApiClient
from api.services.crm_inquiry_service import CrmInquiryService
from api.services.crm_inquiry_status import (
    InquiryCreateSource,
    InquiryForm,
    InquiryMall,
    InquiryStatus,
    default_inquiry_form,
)
from config.settings import (
    CRM_INQUIRY_EN_BUYER_MEMBER_ID,
    CRM_INQUIRY_EN_SUBMIT_API_URL,
    CRM_INQUIRY_SUBMIT_API_URL,
    CRM_INQUIRY_TX_SUBMIT_API_URL,
    EPAK_PLATFORM_BASE_URL,
    PLATFORM_BASE_URL,
)


def _svc() -> CrmInquiryService:
    return CrmInquiryService(ApiClient())


def test_internal_cn_mall_cn_form_uses_transaction_submit():
    route = _svc().resolve_route(source="internal", mall="cn", form="cn")
    assert route.submit_url == CRM_INQUIRY_TX_SUBMIT_API_URL
    assert route.origin == PLATFORM_BASE_URL.rstrip("/")
    assert route.referer_path.endswith("internalInquiry/add?mallType=1")
    assert route.query_params == {}
    assert route.submit_creates is True
    assert route.supports_draft is False


def test_internal_cn_mall_en_form_uses_crm_submit_with_source_mall_type_2():
    route = _svc().resolve_route(source="internal", mall="cn", form="en")
    assert route.submit_url == CRM_INQUIRY_SUBMIT_API_URL
    assert route.origin == PLATFORM_BASE_URL.rstrip("/")
    assert route.referer_path.endswith("internalInquiry/add?mallType=2")
    assert route.query_params == {"sourceMallType": 2}
    assert route.submit_creates is True
    assert route.supports_draft is False


def test_internal_en_mall_uses_epak_en_submit():
    route = _svc().resolve_route(source="internal", mall="en", form="cn")
    assert route.form == InquiryForm.EN
    assert route.submit_url == CRM_INQUIRY_EN_SUBMIT_API_URL
    assert route.origin == EPAK_PLATFORM_BASE_URL.rstrip("/")
    assert route.referer_path.endswith("internalInquiry/add")
    assert "mallType" not in route.referer_path
    assert route.query_params == {}
    assert route.submit_creates is True


def test_crm_customer_cn_form_keeps_draft_then_submit():
    route = _svc().resolve_route(source="crm", mall="cn", form="cn")
    assert route.source == InquiryCreateSource.CRM_CUSTOMER
    assert route.submit_url == CRM_INQUIRY_SUBMIT_API_URL
    assert route.query_params == {"sourceMallType": 1}
    assert route.submit_creates is False
    assert route.supports_draft is True


def test_describe_create_routes_covers_three_internal_entries():
    rows = CrmInquiryService.describe_create_routes()
    keys = {(r["source"], r["mall"], r["form"], r.get("operate_via")) for r in rows}
    assert ("internal", "中文商城", "中文询价单", "en") in keys
    assert ("internal", "中文商城", "英文询价单", "en") in keys
    assert ("internal", "英文商城", "英文询价单", "en") in keys
    assert ("internal", "英文商城", "英文询价单", "cn") in keys


def test_en_mall_operate_via_cn_uses_crm_offline_save():
    route = _svc().resolve_route(
        source="internal", mall="en", form="en", operate_via="cn"
    )
    assert route.mall == InquiryMall.EN
    assert route.operate_via.value == "cn"
    assert route.origin == PLATFORM_BASE_URL.rstrip("/")
    assert route.query_params == {"sourceMallType": 2}
    assert "mallType=2" in route.referer_path
    assert route.submit_url.endswith("/api/crm/customer/iqrMain/submitOrUpdate")
    urls = CrmInquiryService.en_operation_urls(route)
    assert urls.offline_quote.endswith(
        "/api/crm/customer/iqrOfflineQuote/save"
    )
    assert urls.query.endswith("/api/crm/customer/iqrMain/pageList")
    assert "sourceMallType" not in urls.offline_quote


def test_en_mall_operate_via_en_keeps_epak_transaction_urls():
    route = _svc().resolve_route(
        source="internal", mall="en", form="en", operate_via="en"
    )
    assert route.operate_via.value == "en"
    assert route.origin == EPAK_PLATFORM_BASE_URL.rstrip("/")
    assert route.query_params == {}
    urls = CrmInquiryService.en_operation_urls(route)
    assert "/api/transaction/iqrOfflineQuote/platform/save" in urls.offline_quote
    assert urls.offline_quote.startswith(EPAK_PLATFORM_BASE_URL.rstrip("/"))


def test_role_login_accounts_operate_via_cn_uses_cn_endpoint():
    roles = {
        r.role: r.endpoint
        for r in CrmInquiryService.role_login_accounts("en", operate_via="cn")
    }
    assert roles["tech"] == "cn"
    assert roles["purchaser"] == "cn"
    assert roles["support"] == "cn"
    assert roles["supplier"] == "supplier"


def test_cn_operate_blocks_transfer_to_completed():
    from api.services.crm_inquiry_status import (
        GENERAL_PIPELINE,
        InquiryStatus,
        cn_operate_transfer_blocked_message,
        is_transition_wired,
    )

    transfer = next(s for s in GENERAL_PIPELINE if s.handler == "transfer_to_order")
    assert is_transition_wired(transfer, mall=InquiryMall.EN, operate_via="en")
    assert not is_transition_wired(transfer, mall=InquiryMall.EN, operate_via="cn")
    msg = _svc().missing_seed_requirement(
        InquiryStatus.COMPLETED,
        {
            "sales": object(),
            "purchaser": object(),
            "support": object(),
            "supplier": object(),
        },
        source="internal",
        mall="en",
        form="en",
        operate_via="cn",
        ask_price_type="通用品",
    )
    assert msg == cn_operate_transfer_blocked_message()
    assert "待转单" in msg


def test_reconcile_same_member_sessions_keeps_role_tokens():
    from api.auth_context import AuthContext

    sales = AuthContext(member_id=6, user_id=2, token="token-sales")
    purchaser = AuthContext(member_id=6, user_id=1741, token="token-purchaser")
    out = CrmInquiryService.reconcile_same_member_sessions(
        {"sales": sales, "purchaser": purchaser}
    )
    assert out["sales"].token == "token-sales"
    assert out["purchaser"].token == "token-purchaser"


def test_cn_payload_has_address_en_payload_has_company_fields():
    svc = _svc()
    cn = svc.build_create_payload(form="cn", ask_price_type="定制品")
    en = svc.build_create_payload(form="en", ask_price_type="定制品")
    assert "countryCode" in cn
    assert "address" in cn
    assert "companyInfoRemark" not in cn
    assert cn["subs"][0]["askPriceType"] == 2
    assert "sealStyle" in cn["subs"][0]
    assert "companyInfoRemark" in en
    assert "consumeHabitRemark" in en
    assert "countryCode" not in en
    assert en["buyerMemberId"] == CRM_INQUIRY_EN_BUYER_MEMBER_ID
    assert "relationMainInfo" in en["subs"][0]
    assert "productName" in en["subs"][0]
    assert "specificationModel" not in en["subs"][0]


def test_same_main_can_mix_general_and_custom_on_one_form():
    payload = _svc().build_create_payload(
        form="cn",
        subs=[{"ask_price_type": "通用品"}, {"ask_price_type": "定制品"}],
    )
    types = [sub["askPriceType"] for sub in payload["subs"]]
    assert types == [1, 2]
    assert "sealStyle" not in payload["subs"][0]
    assert "sealStyle" in payload["subs"][1]


def test_form_is_main_level_not_per_sub():
    payload = _svc().build_create_payload(
        form="en",
        subs=[{"ask_price_type": "通用品"}, {"ask_price_type": "定制品"}],
    )
    assert "companyInfoRemark" in payload
    assert all("relationMainInfo" in sub for sub in payload["subs"])
    assert all("countryCode" not in sub for sub in payload["subs"])


def test_internal_draft_is_blocked():
    msg = _svc().missing_seed_requirement(
        InquiryStatus.DRAFT,
        {"sales": object()},
        source="internal",
        mall="cn",
        form="cn",
    )
    assert msg is not None
    assert "不支持单独保存草稿" in msg


def test_internal_submit_targets_are_wired():
    svc = _svc()
    roles = {"sales": object()}
    assert (
        svc.missing_seed_requirement(
            "待提交技术方案",
            roles,
            ask_price_type="定制品",
            source="internal",
            mall="cn",
            form="cn",
        )
        is None
    )
    assert (
        svc.missing_seed_requirement(
            "待出厂报价",
            roles,
            ask_price_type="通用品",
            source="internal",
            mall="cn",
            form="en",
        )
        is None
    )


def test_en_mall_defaults_to_en_form():
    assert default_inquiry_form(mall=InquiryMall.EN, source=InquiryCreateSource.INTERNAL) == InquiryForm.EN
    assert default_inquiry_form(mall=InquiryMall.CN, source=InquiryCreateSource.INTERNAL) == InquiryForm.CN


def test_query_payload_uses_en_buyer_and_skips_crm_customer_id_for_internal():
    svc = _svc()
    en_route = svc.resolve_route(source="internal", mall="cn", form="en")
    payload = svc.build_query_payload_for_route(en_route)
    assert payload["buyerMemberId"] == CRM_INQUIRY_EN_BUYER_MEMBER_ID
    assert "id" not in payload


def test_en_mall_custom_factory_quote_is_wired_when_tech_present():
    svc = _svc()
    missing_role = svc.missing_seed_requirement(
        "待出厂报价",
        {"sales": object()},
        ask_price_type="定制品",
        source="internal",
        mall="en",
        form="en",
    )
    assert missing_role is not None
    assert "tech" in missing_role
    assert (
        svc.missing_seed_requirement(
            "待出厂报价",
            {"sales": object(), "tech": object()},
            ask_price_type="定制品",
            source="internal",
            mall="en",
            form="en",
        )
        is None
    )


def test_cn_mall_custom_factory_quote_still_unwired():
    msg = _svc().missing_seed_requirement(
        "待出厂报价",
        {"sales": object(), "tech": object()},
        ask_price_type="定制品",
        source="internal",
        mall="cn",
        form="cn",
    )
    assert msg is not None
    assert "未接线" in msg or "inquiry_submit_tech" in msg


def test_en_tech_program_payload_and_referer():
    from config.settings import CRM_INQUIRY_EN_SUBMIT_TECH_API_URL

    payload = CrmInquiryService.build_en_tech_program_payload(sub_id=173)
    assert payload["iqrSubId"] == "173"
    assert payload["submitFlag"] is True
    assert payload["techProgram"]
    assert payload["techProgramFiles"][0]["url"]
    referer = CrmInquiryService.en_tech_edit_referer(sub_id=173, ask_price_type=2)
    assert "id=173" in referer
    assert "askPriceType=2" in referer
    assert "status=2" in referer
    assert "submitTechProgram" in CRM_INQUIRY_EN_SUBMIT_TECH_API_URL


def test_en_role_login_includes_tech_and_purchaser_and_supplier():
    from config.settings import (
        CRM_INQUIRY_SUPPLIER_ACCOUNT,
        EPAK_INQUIRY_PURCHASER_ACCOUNT,
        EPAK_INQUIRY_SUPPORT_ACCOUNT,
        EPAK_INQUIRY_TECH_ACCOUNT,
    )

    specs = {item.role: item for item in CrmInquiryService.role_login_accounts("en")}
    assert specs["tech"].account == EPAK_INQUIRY_TECH_ACCOUNT
    assert specs["tech"].endpoint == "en"
    assert specs["purchaser"].account == EPAK_INQUIRY_PURCHASER_ACCOUNT
    assert specs["purchaser"].endpoint == "en"
    assert specs["support"].account == EPAK_INQUIRY_SUPPORT_ACCOUNT
    assert specs["support"].endpoint == "en"
    assert specs["supplier"].account == CRM_INQUIRY_SUPPLIER_ACCOUNT
    assert specs["supplier"].endpoint == "supplier"


def test_en_cn_operate_role_login_uses_cn_endpoint():
    from config.settings import (
        EPAK_INQUIRY_PURCHASER_ACCOUNT,
        EPAK_INQUIRY_SUPPORT_ACCOUNT,
        EPAK_INQUIRY_TECH_ACCOUNT,
    )

    specs = {
        item.role: item
        for item in CrmInquiryService.role_login_accounts("en", operate_via="cn")
    }
    assert specs["tech"].endpoint == "cn"
    assert specs["purchaser"].endpoint == "cn"
    assert specs["support"].endpoint == "cn"
    assert specs["tech"].account == EPAK_INQUIRY_TECH_ACCOUNT
    assert specs["purchaser"].account == EPAK_INQUIRY_PURCHASER_ACCOUNT
    # 未配 CRM_INQUIRY_SUPPORT 时仍用 EPAK support（登录失败由 CLI 兜底）
    assert specs["support"].account == EPAK_INQUIRY_SUPPORT_ACCOUNT
    assert specs["supplier"].endpoint == "supplier"


def test_en_mall_platform_quote_requires_supplier_and_is_wired():
    svc = _svc()
    roles_base = {
        "sales": object(),
        "purchaser": object(),
        "supplier": object(),
    }
    channels = CrmInquiryService.parse_en_quote_channels()
    missing = svc.missing_seed_requirement(
        "待平台报价",
        {"sales": object(), "purchaser": object()},
        ask_price_type="通用品",
        source="internal",
        mall="en",
        form="en",
    )
    if "online" in channels:
        assert missing is not None
        assert "supplier" in missing
    else:
        assert missing is None
    assert (
        svc.missing_seed_requirement(
            "待平台报价",
            roles_base,
            ask_price_type="通用品",
            source="internal",
            mall="en",
            form="en",
        )
        is None
    )
    missing_support = svc.missing_seed_requirement(
        "待发起上架申请",
        roles_base,
        ask_price_type="通用品",
        source="internal",
        mall="en",
        form="en",
    )
    assert missing_support is not None
    assert "support" in missing_support
    assert (
        svc.missing_seed_requirement(
            "待发起上架申请",
            {**roles_base, "support": object()},
            ask_price_type="通用品",
            source="internal",
            mall="en",
            form="en",
        )
        is None
    )
    missing_support_2 = svc.missing_seed_requirement(
        InquiryStatus.PENDING_ASSOCIATE_PRODUCT,
        {**roles_base, "support": object()},
        ask_price_type="通用品",
        source="internal",
        mall="en",
        form="en",
    )
    assert missing_support_2 is None
    assert (
        svc.missing_seed_requirement(
            InquiryStatus.PENDING_TRANSFER,
            {**roles_base, "support": object()},
            ask_price_type="通用品",
            source="internal",
            mall="en",
            form="en",
        )
        is None
    )
    completed_missing = svc.missing_seed_requirement(
        InquiryStatus.COMPLETED,
        {**roles_base, "support": object()},
        ask_price_type="通用品",
        source="internal",
        mall="en",
        form="en",
    )
    assert completed_missing is None


def test_cn_mall_factory_quote_still_unwired():
    msg = _svc().missing_seed_requirement(
        "待平台报价",
        {"sales": object(), "purchaser": object(), "supplier": object()},
        ask_price_type="通用品",
        source="internal",
        mall="cn",
        form="cn",
    )
    assert msg is not None
    assert "未接线" in msg or "inquiry_factory_quote" in msg


def test_en_quote_channel_default_is_both():
    assert CrmInquiryService.parse_en_quote_channels("both") == {"online", "offline"}
    assert CrmInquiryService.parse_en_quote_channels("线上") == {"online"}
    assert CrmInquiryService.parse_en_quote_channels("offline") == {"offline"}


def test_en_factory_payloads_include_online_and_offline_shapes():
    from config.settings import (
        CRM_INQUIRY_EN_CONFIRM_PRICE_API_URL,
        CRM_INQUIRY_EN_PLATFORM_PRICE_TYPE,
        CRM_INQUIRY_EN_PLATFORM_UNIT_PRICE,
        CRM_INQUIRY_EN_RELATION_PRODUCT_API_URL,
        CRM_INQUIRY_EN_RELATION_SKU_IDS,
        CRM_INQUIRY_EN_SUBMIT_CUSTOM_ORDER_API_URL,
        CRM_INQUIRY_EN_SUBMIT_PLATFORM_API_URL,
        EPAK_INQUIRY_SUPPLIER_MEMBER_ID,
    )

    push = CrmInquiryService.build_en_push_supplier_payload(sub_id=172)
    assert push["iqrSubId"] == "172"
    assert push["supplierList"][0]["supplierMemberId"] == EPAK_INQUIRY_SUPPLIER_MEMBER_ID
    offline = CrmInquiryService.build_en_offline_quote_payload(
        sub_id=172, packaging_type=1, is_pallet=1
    )
    assert offline["sourceMall"] == 2
    assert offline["supplier"]["supplierMemberId"] == EPAK_INQUIRY_SUPPLIER_MEMBER_ID
    assert offline["supplier"]["packagingType"] == 1
    assert offline["supplier"]["isPallet"] == 1
    assert offline["supplier"]["cartonSize"] == "37*55*45"
    assert offline["supplier"]["cartonSizeLong"] == 37
    assert offline["supplier"]["boxPcs"] == 5
    assert offline["supplier"]["palletTotalCount"] == 345
    carton_no_pallet = CrmInquiryService.build_en_packaging_fields(
        packaging_type=1, is_pallet=0
    )
    assert carton_no_pallet == {
        "packagingType": 1,
        "isPallet": 0,
        "boxPcs": 5,
        "cartonSize": "37*55*45",
        "cartonSizeLong": 37,
        "cartonSizeWide": 55,
        "cartonSizeHigh": 45,
        "cartonSizeUnit": 2,
        "cartonWeight": 78.34,
    }
    assert "palletTotalCount" not in carton_no_pallet
    assert "palletBoxs" not in carton_no_pallet
    assert "gp20Plts" not in carton_no_pallet
    assert "gp40Plts" not in carton_no_pallet
    roll_pallet = CrmInquiryService.build_en_packaging_fields(
        packaging_type=2, is_pallet=1
    )
    assert roll_pallet["packagingType"] == 2
    assert roll_pallet["isPallet"] == 1
    assert roll_pallet["rollWeightKg"] == 45.34
    assert roll_pallet["totalRolls"] == 578
    assert roll_pallet["palletRolls"] == 5
    assert roll_pallet["gp20RollPlts"] == 45
    assert roll_pallet["gp40RollPlts"] == 23
    assert "palletBoxs" not in roll_pallet
    assert "rollDiameterMm" not in roll_pallet
    roll_no_pallet = CrmInquiryService.build_en_packaging_fields(
        packaging_type=2, is_pallet=0
    )
    assert roll_no_pallet == {
        "packagingType": 2,
        "isPallet": 0,
        "rollWeightKg": 45.34,
        "rollPackagingMethod": "卷类包装方式111",
        "totalRolls": 666,
        "rollDiameterMm": 232.1,
        "rollHeightMm": 46.89,
    }
    assert "palletRolls" not in roll_no_pallet
    assert "gp20RollPlts" not in roll_no_pallet
    other = CrmInquiryService.build_en_packaging_fields(packaging_type=3, is_pallet=1)
    assert other["isPallet"] == 0
    assert other["packagingTypeOther"] == "包装方式其他"
    assert other["packageProductQty"] == 567
    assert other["totalPackages"] == 7891
    assert "packagePcs" not in other
    quote = CrmInquiryService.build_cn_supplier_quote_payload(
        quote_id=227, packaging_type=1, is_pallet=1
    )
    assert quote["id"] == 227
    assert quote["sourceMall"] == 2
    assert quote["spec"] == "12*23*34"
    assert quote["specLong"] == 12
    assert quote["specWide"] == 23
    assert quote["specHigh"] == 34
    assert quote["specUnit"] == 3
    assert quote["cartonSize"] == "37*55*45"
    assert quote["packagingType"] == 1
    assert quote["isPallet"] == 1
    roll_online = CrmInquiryService.build_cn_supplier_quote_payload(
        quote_id=301, packaging_type=2, is_pallet=1
    )
    assert roll_online["specLong"] == 12
    assert roll_online["packagingType"] == 2
    assert roll_online["isPallet"] == 1
    assert roll_online["rollWeightKg"] == 45.34
    assert roll_online["totalRolls"] == 578
    assert roll_online["palletRolls"] == 5
    assert roll_online["gp20RollPlts"] == 45
    assert roll_online["gp40RollPlts"] == 23
    assert roll_online["palletTotalCount"] == 56
    assert "boxPcs" not in roll_online
    factory = CrmInquiryService.build_en_factory_price_payload(
        sub_id=172,
        quote_row={"giqrNo": "GIQRe00000090-1-1"},
        supplier_quote=quote,
        factory_source=1,
    )
    assert factory["factorySource"] == 1
    assert factory["factorySourceNo"] == "GIQRe00000090-1-1"
    assert factory["supplyMemberId"] == EPAK_INQUIRY_SUPPLIER_MEMBER_ID
    assert factory["factoryCity"] == "伯明翰"
    assert factory["packingMethod"] == "纸箱包装"
    assert factory["isPallet"] == 1
    assert factory["cartonQtyPerCtn"] == 5
    assert factory["cartonSizeCm"] == "37*55*45"
    assert factory["cartonSizeLong"] == 37
    assert factory["cartonSizeWide"] == 55
    assert factory["cartonSizeHigh"] == 45
    assert factory["cartonSizeUnit"] == 2
    assert factory["cartonGrossWeightKg"] == 78.34
    assert factory["cartonCtnPerPlt"] == 31
    assert factory["carton20gpPlts"] == 56
    assert factory["carton40hqPlts"] == 45
    assert factory["palletTotalCount"] == 345
    assert factory["comparePriceRemark"] == "自动化比价小结"
    assert factory["compareFiles"]
    assert factory["compareFiles"][0]["url"]
    assert "packingMethodOther" not in factory
    roll_offline = CrmInquiryService.build_en_offline_quote_payload(
        sub_id=236, packaging_type=2, is_pallet=1
    )["supplier"]
    roll_factory = CrmInquiryService.build_en_factory_price_payload(
        sub_id=236,
        quote_row={"offNo": "OFFe00000130-1-2"},
        supplier_quote=roll_offline,
        factory_source=2,
    )
    assert roll_factory["factorySource"] == 2
    assert roll_factory["factorySourceNo"] == "OFFe00000130-1-2"
    assert roll_factory["packingMethod"] == "卷类包装"
    assert roll_factory["isPallet"] == 1
    assert roll_factory["factoryDesc"] == "自动化线下询价备注"
    assert roll_factory["rollWeightKg"] == 45.34
    assert roll_factory["totalRolls"] == 578
    assert roll_factory["rollPackingMethod"] == "卷类包装方式111"
    assert roll_factory["rollQtyPerPlt"] == 5
    assert roll_factory["roll20gpPlts"] == 45
    assert roll_factory["roll40hqPlts"] == 23
    assert roll_factory["palletTotalCount"] == 56
    assert roll_factory["palletWeightKg"] == 34.23
    assert roll_factory["palletVolumeM3"] == 45.98
    assert roll_factory["factoryCity"] == "伯明翰"
    other_offline = CrmInquiryService.build_en_offline_quote_payload(
        sub_id=236, packaging_type=3, is_pallet=1
    )["supplier"]
    other_factory = CrmInquiryService.build_en_factory_price_payload(
        sub_id=236,
        quote_row={"offNo": "OFFe00000130-1-3"},
        supplier_quote=other_offline,
        factory_source=2,
    )
    assert other_factory["packingMethod"] == "其他"
    assert other_factory["isPallet"] == 0
    assert other_factory["packageProductQty"] == 567
    assert other_factory["totalPackages"] == 7891
    assert "packingMethodOther" not in other_factory
    assert "cartonQtyPerCtn" not in other_factory
    assert "rollWeightKg" not in other_factory
    carton_no_pallet_factory = CrmInquiryService.build_en_factory_price_payload(
        sub_id=236,
        quote_row={"offNo": "OFFe00000130-1-4"},
        supplier_quote=CrmInquiryService.build_en_offline_quote_payload(
            sub_id=236, packaging_type=1, is_pallet=0
        )["supplier"],
        factory_source=2,
    )
    assert carton_no_pallet_factory["isPallet"] == 0
    assert carton_no_pallet_factory["cartonSizeLong"] == 37
    assert "cartonCtnPerPlt" not in carton_no_pallet_factory
    assert "palletTotalCount" not in carton_no_pallet_factory
    adopted = CrmInquiryService.normalize_quote_record_for_factory(
        {
            "id": 276,
            "offlineNumber": "OFFe00000135-1-1",
            "isAdopted": 1,
            "price": "1344",
            "remark": "自动化线下询价备注",
            "packagingType": 2,
            "isPallet": 1,
            "rollWeightKg": 45.34,
            "totalRolls": 578,
            "rollPackagingMethod": "卷类包装方式111",
            "palletRolls": 5,
            "gp20RollPlts": 45,
            "gp40RollPlts": 23,
            "palletTotalCount": 56,
            "palletWeightKg": 34.23,
            "palletVolumeM3": 45.98,
            "specLong": 34,
            "specWide": 23,
            "specHigh": 35,
        }
    )
    assert adopted["price"] == 1344.0
    assert adopted["supplierRemark"] == "自动化线下询价备注"
    assert adopted["spec"] == "34*23*35"
    assert CrmInquiryService.extract_quote_number(adopted) == "OFFe00000135-1-1"
    assert CrmInquiryService.pick_quote_record(
        [{"id": 1, "isAdopted": 0}, {"id": 276, "isAdopted": 1}],
        prefer_adopted=True,
    )["id"] == 276
    assert CrmInquiryService.resolve_en_factory_adopt_source({"online", "offline"}) == (
        "offline"
    )
    assert CrmInquiryService.resolve_en_factory_adopt_source(
        {"online", "offline"}, value="online"
    ) == "online"
    assert CrmInquiryService.resolve_en_factory_adopt_source({"online"}) == "online"
    assert CrmInquiryService.en_factory_desc_from_packaging(
        packaging_type=2, is_pallet=1
    ) == "卷装打托"
    assert CrmInquiryService.build_en_offline_factory_source_no(
        main_number="IQRe00000130", quote_index=2
    ) == "OFFe00000130-1-2"
    assert CrmInquiryService.extract_quote_number({"offNo": True}) is None
    assert CrmInquiryService.extract_quote_number({"offNo": "OFFe00000130-1-2"}) == (
        "OFFe00000130-1-2"
    )
    platform = CrmInquiryService.build_en_platform_price_payload(sub_id=172)
    assert platform["iqrSubId"] == "172"
    assert platform["platformUnitPrice"] == CRM_INQUIRY_EN_PLATFORM_UNIT_PRICE
    assert platform["platformPriceType"] == CRM_INQUIRY_EN_PLATFORM_PRICE_TYPE
    assert platform["logisticsFiles"]
    referer = CrmInquiryService.en_platform_edit_referer(sub_id=172, ask_price_type=1)
    assert "status=7" in referer
    assert "inquirySteps=4" in referer
    assert "submitPlatformPrice" in CRM_INQUIRY_EN_SUBMIT_PLATFORM_API_URL
    confirm = CrmInquiryService.build_en_confirm_price_payload(sub_id=172)
    assert confirm == {"iqrSubId": "172", "isLaunch": 1}
    listing_referer = CrmInquiryService.en_listing_edit_referer(sub_id=172, ask_price_type=1)
    assert "status=9" in listing_referer
    assert "inquirySteps=5" in listing_referer
    assert "confirmPrice" in CRM_INQUIRY_EN_CONFIRM_PRICE_API_URL
    relation = CrmInquiryService.build_en_relation_product_payload(sub_id=172)
    assert relation == {"iqrSubId": 172, "skuId": CRM_INQUIRY_EN_RELATION_SKU_IDS}
    submit_custom = CrmInquiryService.build_en_submit_custom_order_payload(sub_id=172)
    assert submit_custom == {"id": "172"}
    associate_referer = CrmInquiryService.en_associate_edit_referer(
        sub_id=172, ask_price_type=1
    )
    assert "status=11" in associate_referer
    assert "inquirySteps=6" in associate_referer
    assert "relationProduct" in CRM_INQUIRY_EN_RELATION_PRODUCT_API_URL
    assert "submitCustomOrder" in CRM_INQUIRY_EN_SUBMIT_CUSTOM_ORDER_API_URL
    referer = CrmInquiryService.en_transfer_order_referer(sub_id=172)
    assert referer == "/memberCenter/orderAbility/saleOrder/agentOrder?iqrSubId=172"
    assert CrmInquiryService.resolve_sub_quantity(None, ask_price_type=1) == 1999
    assert CrmInquiryService.resolve_sub_quantity({"sub": {"qty": 1809}}) == 1809


def test_epak_login_targets_auth_epakgroup_cn():
    from api.services.auth_service import AuthService
    from config.settings import EPAK_PLATFORM_AUTH_API_URL, EPAK_PLATFORM_AUTH_ORIGIN

    spec = AuthService.resolve_login_endpoint("en")
    headers = AuthService.build_login_headers("en")
    assert spec["api_url"] == EPAK_PLATFORM_AUTH_API_URL
    assert spec["origin"] == EPAK_PLATFORM_AUTH_ORIGIN.rstrip("/")
    assert headers["Origin"] == EPAK_PLATFORM_AUTH_ORIGIN.rstrip("/")
    assert headers["Referer"].startswith(f"{EPAK_PLATFORM_AUTH_ORIGIN.rstrip('/')}/user/login")
    assert headers["Accept-Language"] == "en-US"
    assert headers["Cookie"] == "LX_LANG=ZW4tVVM="


def test_en_internal_query_defaults_to_page_list():
    from config.settings import CRM_INQUIRY_EN_QUERY_API_URL, EPAK_PLATFORM_BASE_URL

    assert "pageList" in CRM_INQUIRY_EN_QUERY_API_URL
    assert CRM_INQUIRY_EN_QUERY_API_URL.startswith(EPAK_PLATFORM_BASE_URL.rstrip("/"))


def test_cn_login_still_targets_test_auth_ysbpack():
    from api.services.auth_service import AuthService
    from config.settings import AUTH_API_URL

    spec = AuthService.resolve_login_endpoint("cn")
    headers = AuthService.build_login_headers("cn")
    assert spec["api_url"] == AUTH_API_URL
    assert "/api/member/login" in AUTH_API_URL
    assert headers["Referer"].endswith("/user/login")
    assert "Accept-Language" not in headers
    assert "Cookie" not in headers


def test_supplier_login_uses_inquiry_supplier_auth_settings():
    from api.services.auth_service import AuthService
    from config.settings import (
        CRM_INQUIRY_SUPPLIER_AUTH_API_URL,
        CRM_INQUIRY_SUPPLIER_AUTH_ORIGIN,
    )

    spec = AuthService.resolve_login_endpoint("supplier")
    headers = AuthService.build_login_headers("supplier")
    assert spec["endpoint"] == "supplier"
    assert spec["api_url"] == CRM_INQUIRY_SUPPLIER_AUTH_API_URL
    assert spec["origin"] == CRM_INQUIRY_SUPPLIER_AUTH_ORIGIN.rstrip("/")
    assert headers["Origin"] == spec["origin"]
    assert headers["Referer"].startswith(f"{spec['origin']}/user/login")


def test_normalize_sub_specs_quote_and_packaging_options():
    from api.services.crm_inquiry_status import InquiryAskPriceType

    specs = CrmInquiryService.normalize_sub_specs(
        [
            {
                "ask_price_type": "通用品",
                "target_status": "待平台报价",
                "quote_channels": "offline",
                "adopt_source": "offline",
                "packaging_type": "卷类",
                "is_pallet": "是",
            },
            {
                "askPriceType": 2,
                "targetStatus": "待出厂报价",
                "channels": "both",
                "adoptSource": "online",
                "packagingType": 1,
                "isPallet": 0,
            },
        ],
        default_ask_price_type=InquiryAskPriceType.GENERAL,
        default_target=InquiryStatus.PENDING_FACTORY_QUOTE,
    )
    assert len(specs) == 2
    assert specs[0].resolved_type().code == 1
    assert specs[0].resolved_target() == InquiryStatus.PENDING_PLATFORM_QUOTE
    assert specs[0].quote_channels == "offline"
    assert specs[0].adopt_source == "offline"
    assert CrmInquiryService.parse_packaging_type(specs[0].packaging_type) == 2
    assert CrmInquiryService.parse_is_pallet(specs[0].is_pallet) == 1
    assert specs[1].resolved_type().code == 2
    assert specs[1].quote_channels == "both"
    assert specs[1].adopt_source == "online"
    assert CrmInquiryService.parse_packaging_type(specs[1].packaging_type) == 1
    assert CrmInquiryService.parse_is_pallet(specs[1].is_pallet) == 0
    assert CrmInquiryService.parse_en_quote_channels(specs[0].quote_channels) == {
        "offline"
    }
    offline = CrmInquiryService.build_en_offline_quote_payload(
        sub_id=1,
        packaging_type=CrmInquiryService.parse_packaging_type(specs[0].packaging_type),
        is_pallet=CrmInquiryService.parse_is_pallet(specs[0].is_pallet),
    )["supplier"]
    assert offline["packagingType"] == 2
    assert offline["isPallet"] == 1
    assert offline["rollWeightKg"] == 45.34
