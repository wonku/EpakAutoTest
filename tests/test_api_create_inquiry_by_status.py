"""CRM 询价单按状态造数（数据准备）。

覆盖：创建入口（CRM / 内部询价单）、中英文商城/表单、定制品/通用品不同流转、多子单。
已接线：CRM 草稿+提交；内部询价为一次 submitOrUpdate。
定制品提交后→待技术方案；通用品提交后→待出厂报价。

运行:
  pytest tests/test_api_create_inquiry_by_status.py -m inquiry_seed -v -s
  python scripts/create_inquiry.py --source internal --mall cn --form cn --status 待提交技术方案
"""
from __future__ import annotations

import json

import allure
import pytest

from api.services.crm_inquiry_status import (
    CUSTOM_PIPELINE,
    GENERAL_PIPELINE,
    InquiryAskPriceType,
    InquiryCreateSource,
    InquiryStatus,
    InquirySubSpec,
    default_inquiry_form,
    parse_ask_price_type,
    parse_create_source,
    parse_inquiry_form,
    parse_inquiry_mall,
    parse_inquiry_status,
    pipeline_for,
)
from config.settings import (
    CRM_INQUIRY_ASK_PRICE_TYPE,
    CRM_INQUIRY_CREATE_SOURCE,
    CRM_INQUIRY_FORM,
    CRM_INQUIRY_MALL,
    CRM_INQUIRY_SEED_STATUSES,
    CRM_INQUIRY_SUBS_JSON,
)

pytestmark = [pytest.mark.api, pytest.mark.inquiry_seed]


def _default_source() -> InquiryCreateSource:
    return parse_create_source(CRM_INQUIRY_CREATE_SOURCE)


def _default_ask_type() -> InquiryAskPriceType:
    return parse_ask_price_type(CRM_INQUIRY_ASK_PRICE_TYPE)


def _default_mall():
    return parse_inquiry_mall(CRM_INQUIRY_MALL)


def _default_form():
    if CRM_INQUIRY_FORM:
        return parse_inquiry_form(CRM_INQUIRY_FORM)
    return default_inquiry_form(mall=_default_mall(), source=_default_source())


def _seed_cases() -> list[tuple]:
    """(source, ask_type, target) 或由 CRM_INQUIRY_SEED_STATUSES / SUBS_JSON 覆盖。"""
    source = _default_source()
    if CRM_INQUIRY_SUBS_JSON:
        # 多子单场景：只跑一组，目标取环境默认或首条
        ask = _default_ask_type()
        raw_status = CRM_INQUIRY_SEED_STATUSES.split(",")[0].strip() if CRM_INQUIRY_SEED_STATUSES else ""
        if raw_status:
            target = parse_inquiry_status(raw_status)
        else:
            target = (
                InquiryStatus.PENDING_TECH
                if ask == InquiryAskPriceType.CUSTOM
                else InquiryStatus.PENDING_FACTORY_QUOTE
            )
        return [(source, ask, target, json.loads(CRM_INQUIRY_SUBS_JSON))]

    if CRM_INQUIRY_SEED_STATUSES:
        ask = _default_ask_type()
        return [
            (source, ask, parse_inquiry_status(item.strip()), None)
            for item in CRM_INQUIRY_SEED_STATUSES.split(",")
            if item.strip()
        ]

    cases: list[tuple] = []
    for ask, pipe in (
        (InquiryAskPriceType.CUSTOM, CUSTOM_PIPELINE),
        (InquiryAskPriceType.GENERAL, GENERAL_PIPELINE),
    ):
        for step in pipe:
            cases.append((source, ask, step.to_status, None))
    return cases


def _case_id(case: tuple) -> str:
    source, ask, target, subs = case
    suffix = "+multi" if subs else ""
    return f"{source.value}-{ask.code}{ask.name}-{target.code}-{target.label}{suffix}"


@allure.feature("CRM 询价单")
@allure.story("按状态造数")
@pytest.mark.parametrize("case", _seed_cases(), ids=_case_id)
def test_create_inquiry_to_status(crm_auth, crm_inquiry_service, inquiry_role_auths, case):
    source, ask_type, target_status, subs = case
    mall = _default_mall()
    form = _default_form()
    missing = crm_inquiry_service.missing_seed_requirement(
        target_status,
        inquiry_role_auths,
        ask_price_type=ask_type,
        source=source,
        mall=mall,
        form=form,
        subs=subs,
    )
    if missing:
        pytest.skip(missing)

    result = crm_inquiry_service.create_inquiry_to_status(
        crm_auth,
        target_status,
        role_auths=inquiry_role_auths,
        ask_price_type=ask_type,
        source=source,
        mall=mall,
        form=form,
        subs=subs,
    )
    allure.dynamic.title(
        f"[{source.label}/{mall.label}/{form.label}][{ask_type.label}] "
        f"造数到「{target_status.label}」"
        + ("（多子单）" if subs else "")
    )
    payload = {
        "source": result.source.value,
        "mall": result.mall.label if result.mall else None,
        "form": result.form.label if result.form else None,
        "main_id": result.main_id,
        "main_number": result.main_number,
        "subs": [
            {
                "sub_id": s.sub_id,
                "ask_price_type": s.ask_price_type,
                "ask_price_type_name": s.ask_price_type_name,
                "status": s.status,
                "status_name": s.status_name,
                "target": s.target.label if s.target else None,
            }
            for s in result.subs
        ],
    }
    allure.attach(
        json.dumps(payload, ensure_ascii=False, indent=2),
        name="inquiry_seed_result",
        attachment_type=allure.attachment_type.JSON,
    )
    assert result.subs, "未返回子单结果"
    for sub in result.subs:
        expected = (
            parse_inquiry_status(sub.target)
            if sub.target is not None
            else target_status
        )
        # 多子单时每条可用自己的 target
        assert sub.status == expected.code, (
            f"子单 {sub.sub_id} 期望 {expected.label}，实际 {sub.status_name}"
        )


@allure.feature("CRM 询价单")
@allure.story("按状态造数")
@allure.title("一笔主单同时创建定制品+通用品子单（仅草稿）")
def test_create_mixed_subs_draft(crm_auth, crm_inquiry_service, inquiry_role_auths):
    source = _default_source()
    mall = _default_mall()
    form = _default_form()
    subs = [
        InquirySubSpec(ask_price_type="定制品", target_status="新建草稿"),
        InquirySubSpec(ask_price_type="通用品", target_status="新建草稿"),
    ]
    missing = crm_inquiry_service.missing_seed_requirement(
        InquiryStatus.DRAFT,
        inquiry_role_auths,
        source=source,
        mall=mall,
        form=form,
        subs=subs,
    )
    if missing:
        pytest.skip(missing)

    result = crm_inquiry_service.create_inquiry_to_status(
        crm_auth,
        InquiryStatus.DRAFT,
        role_auths=inquiry_role_auths,
        source=source,
        mall=mall,
        form=form,
        subs=subs,
    )
    allure.attach(
        json.dumps(
            {
                "main_id": result.main_id,
                "subs": [
                    {
                        "sub_id": s.sub_id,
                        "type": s.ask_price_type_name,
                        "status": s.status_name,
                    }
                    for s in result.subs
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        name="mixed_subs_draft",
        attachment_type=allure.attachment_type.JSON,
    )
    assert len(result.subs) == 2
    types = {s.ask_price_type for s in result.subs}
    assert types == {1, 2}
    assert all(s.status == InquiryStatus.DRAFT.code for s in result.subs)


@allure.feature("CRM 询价单")
@allure.story("流水线元数据")
@allure.title("定制品与通用品流水线节点不同")
def test_pipeline_differs_by_ask_price_type():
    custom_codes = [s.to_status.code for s in pipeline_for("定制品")]
    general_codes = [s.to_status.code for s in pipeline_for("通用品")]
    assert InquiryStatus.PENDING_TECH.code in custom_codes
    assert InquiryStatus.PENDING_TECH.code not in general_codes
    assert InquiryStatus.PENDING_FACTORY_QUOTE.code in general_codes


@allure.feature("CRM 询价单")
@allure.story("按状态造数")
@allure.title("一笔主单同时提交定制品+通用品子单（按子单各自流转）")
def test_create_mixed_subs_submit(crm_auth, crm_inquiry_service, inquiry_role_auths):
    source = _default_source()
    mall = _default_mall()
    form = _default_form()
    subs = [
        InquirySubSpec(ask_price_type="定制品", target_status="待提交技术方案"),
        InquirySubSpec(ask_price_type="通用品", target_status="待出厂报价"),
    ]
    missing = crm_inquiry_service.missing_seed_requirement(
        InquiryStatus.PENDING_TECH,
        inquiry_role_auths,
        source=source,
        mall=mall,
        form=form,
        subs=subs,
    )
    if missing:
        pytest.skip(missing)

    result = crm_inquiry_service.create_inquiry_to_status(
        crm_auth,
        InquiryStatus.PENDING_TECH,
        role_auths=inquiry_role_auths,
        source=source,
        mall=mall,
        form=form,
        subs=subs,
    )
    allure.attach(
        json.dumps(
            {
                "source": result.source.value,
                "mall": result.mall.label if result.mall else None,
                "form": result.form.label if result.form else None,
                "main_id": result.main_id,
                "subs": [
                    {
                        "sub_id": s.sub_id,
                        "type": s.ask_price_type_name,
                        "status": s.status_name,
                    }
                    for s in result.subs
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        name="mixed_subs_submit",
        attachment_type=allure.attachment_type.JSON,
    )
    assert len(result.subs) == 2
    by_type = {s.ask_price_type: s for s in result.subs}
    assert by_type[2].status == InquiryStatus.PENDING_TECH.code
    assert by_type[1].status == InquiryStatus.PENDING_FACTORY_QUOTE.code
