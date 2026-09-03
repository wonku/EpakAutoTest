from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InquiryStatus(Enum):
    """询价子单状态（现网 iqrSub.status / statusName）。"""

    DRAFT = 14
    PENDING_SUBMIT = 0
    PENDING_TECH = 2
    PENDING_FACTORY_QUOTE = 5
    PENDING_PLATFORM_QUOTE = 7
    PENDING_LISTING = 9
    PENDING_ASSOCIATE_PRODUCT = 11
    PENDING_TRANSFER = 12
    COMPLETED = 13
    CLOSED = -1

    @property
    def code(self) -> int:
        return int(self.value)

    @property
    def label(self) -> str:
        return _STATUS_LABELS[self]


class InquiryAskPriceType(Enum):
    """询价类型（现网 askPriceType）。流转按子单类型走，不按主单。"""

    GENERAL = 1  # 通用品内部询价：提交后直接待出厂报价
    CUSTOM = 2  # 定制品内部询价：提交后待提交技术方案

    @property
    def code(self) -> int:
        return int(self.value)

    @property
    def label(self) -> str:
        return _ASK_TYPE_LABELS[self]


class InquiryCreateSource(Enum):
    """创建入口。接口 URL 可能相同，但 Referer / 菜单权限不同。"""

    CRM_CUSTOMER = "crm_customer"  # CRM 客户详情 → 发起内部询价单
    INTERNAL = "internal"  # 交易能力 → 内部询价单

    @property
    def label(self) -> str:
        return _SOURCE_LABELS[self]

    @property
    def referer_path(self) -> str:
        return _SOURCE_REFERERS[self]

    @property
    def recording_title(self) -> str:
        return _SOURCE_RECORDING[self]


class InquiryMall(Enum):
    """操作所在商城/平台。中文商城改版后可同时创建英文询价单。"""

    CN = 1  # 中文商城 test-platform.ysbpack.com
    EN = 2  # 英文商城测试平台 platform.epakgroup.cn / auth.epakgroup.cn

    @property
    def code(self) -> int:
        return int(self.value)

    @property
    def label(self) -> str:
        return _MALL_LABELS[self]


class InquiryForm(Enum):
    """询价单表单语种（内部询价 add?mallType=）。"""

    CN = 1  # 中文询价单：地址/规格型号等
    EN = 2  # 英文询价单：公司信息/消费习惯/合规字段等

    @property
    def code(self) -> int:
        return int(self.value)

    @property
    def label(self) -> str:
        return _FORM_LABELS[self]


class InquiryOperateVia(Enum):
    """英文询价单的操作站点：默认英文站；可选中文站（CRM + sourceMallType=2）。"""

    EN = "en"
    CN = "cn"

    @property
    def label(self) -> str:
        return _OPERATE_VIA_LABELS[self]


_STATUS_LABELS: dict[InquiryStatus, str] = {
    InquiryStatus.DRAFT: "新建草稿",
    InquiryStatus.PENDING_SUBMIT: "待提交",
    InquiryStatus.PENDING_TECH: "待提交技术方案",
    InquiryStatus.PENDING_FACTORY_QUOTE: "待出厂报价",
    InquiryStatus.PENDING_PLATFORM_QUOTE: "待平台报价",
    InquiryStatus.PENDING_LISTING: "待发起上架申请",
    InquiryStatus.PENDING_ASSOCIATE_PRODUCT: "待关联报价商品",
    InquiryStatus.PENDING_TRANSFER: "待转单",
    InquiryStatus.COMPLETED: "已完成",
    InquiryStatus.CLOSED: "已关闭",
}

_ASK_TYPE_LABELS: dict[InquiryAskPriceType, str] = {
    InquiryAskPriceType.GENERAL: "通用品内部询价",
    InquiryAskPriceType.CUSTOM: "定制品内部询价",
}

_SOURCE_LABELS: dict[InquiryCreateSource, str] = {
    InquiryCreateSource.CRM_CUSTOMER: "CRM客户详情发起",
    InquiryCreateSource.INTERNAL: "交易能力-内部询价单",
}

_SOURCE_REFERERS: dict[InquiryCreateSource, str] = {
    InquiryCreateSource.CRM_CUSTOMER: "/memberCenter/crm2Ability/customer",
    InquiryCreateSource.INTERNAL: (
        "/memberCenter/transactionAbility/inquiryOffer/internalInquiry"
    ),
}

_SOURCE_RECORDING: dict[InquiryCreateSource, str] = {
    InquiryCreateSource.CRM_CUSTOMER: "inquiry_create_crm_customer",
    InquiryCreateSource.INTERNAL: "inquiry_create_internal",
}

_MALL_LABELS: dict[InquiryMall, str] = {
    InquiryMall.CN: "中文商城",
    InquiryMall.EN: "英文商城",
}

_FORM_LABELS: dict[InquiryForm, str] = {
    InquiryForm.CN: "中文询价单",
    InquiryForm.EN: "英文询价单",
}

_OPERATE_VIA_LABELS: dict[InquiryOperateVia, str] = {
    InquiryOperateVia.EN: "英文站操作",
    InquiryOperateVia.CN: "中文站操作英文单",
}

_STATUS_ALIASES: dict[str, InquiryStatus] = {
    "草稿": InquiryStatus.DRAFT,
    "draft": InquiryStatus.DRAFT,
    "新建草稿": InquiryStatus.DRAFT,
    "待提交": InquiryStatus.PENDING_SUBMIT,
    "待提交技术方案": InquiryStatus.PENDING_TECH,
    "待出厂报价": InquiryStatus.PENDING_FACTORY_QUOTE,
    "待平台报价": InquiryStatus.PENDING_PLATFORM_QUOTE,
    "待发起上架申请": InquiryStatus.PENDING_LISTING,
    "待关联报价商品": InquiryStatus.PENDING_ASSOCIATE_PRODUCT,
    "待转单": InquiryStatus.PENDING_TRANSFER,
    "已完成": InquiryStatus.COMPLETED,
    "已关闭": InquiryStatus.CLOSED,
    "已取消": InquiryStatus.CLOSED,
}
for _status in InquiryStatus:
    _STATUS_ALIASES[_status.name.lower()] = _status
    _STATUS_ALIASES[_status.name] = _status
    _STATUS_ALIASES[str(_status.code)] = _status
    _STATUS_ALIASES[_status.label] = _status

_ASK_TYPE_ALIASES: dict[str, InquiryAskPriceType] = {
    "1": InquiryAskPriceType.GENERAL,
    "通用": InquiryAskPriceType.GENERAL,
    "通用品": InquiryAskPriceType.GENERAL,
    "通用品内部询价": InquiryAskPriceType.GENERAL,
    "general": InquiryAskPriceType.GENERAL,
    "2": InquiryAskPriceType.CUSTOM,
    "定制": InquiryAskPriceType.CUSTOM,
    "定制品": InquiryAskPriceType.CUSTOM,
    "定制品内部询价": InquiryAskPriceType.CUSTOM,
    "custom": InquiryAskPriceType.CUSTOM,
}
for _ask in InquiryAskPriceType:
    _ASK_TYPE_ALIASES[_ask.name.lower()] = _ask
    _ASK_TYPE_ALIASES[_ask.name] = _ask
    _ASK_TYPE_ALIASES[str(_ask.code)] = _ask
    _ASK_TYPE_ALIASES[_ask.label] = _ask

_SOURCE_ALIASES: dict[str, InquiryCreateSource] = {
    "crm": InquiryCreateSource.CRM_CUSTOMER,
    "crm_customer": InquiryCreateSource.CRM_CUSTOMER,
    "customer": InquiryCreateSource.CRM_CUSTOMER,
    "客户": InquiryCreateSource.CRM_CUSTOMER,
    "客户详情": InquiryCreateSource.CRM_CUSTOMER,
    "CRM客户详情发起": InquiryCreateSource.CRM_CUSTOMER,
    "internal": InquiryCreateSource.INTERNAL,
    "内部": InquiryCreateSource.INTERNAL,
    "内部询价单": InquiryCreateSource.INTERNAL,
    "交易能力": InquiryCreateSource.INTERNAL,
    "交易能力-内部询价单": InquiryCreateSource.INTERNAL,
}
for _src in InquiryCreateSource:
    _SOURCE_ALIASES[_src.name.lower()] = _src
    _SOURCE_ALIASES[_src.name] = _src
    _SOURCE_ALIASES[_src.value] = _src
    _SOURCE_ALIASES[_src.label] = _src

_MALL_ALIASES: dict[str, InquiryMall] = {
    "1": InquiryMall.CN,
    "cn": InquiryMall.CN,
    "zh": InquiryMall.CN,
    "中文": InquiryMall.CN,
    "中文商城": InquiryMall.CN,
    "esbao": InquiryMall.CN,
    "ysb": InquiryMall.CN,
    "2": InquiryMall.EN,
    "en": InquiryMall.EN,
    "英文": InquiryMall.EN,
    "英文商城": InquiryMall.EN,
    "epak": InquiryMall.EN,
}
for _mall in InquiryMall:
    _MALL_ALIASES[_mall.name.lower()] = _mall
    _MALL_ALIASES[_mall.name] = _mall
    _MALL_ALIASES[str(_mall.code)] = _mall
    _MALL_ALIASES[_mall.label] = _mall

_FORM_ALIASES: dict[str, InquiryForm] = {
    "1": InquiryForm.CN,
    "cn": InquiryForm.CN,
    "zh": InquiryForm.CN,
    "中文": InquiryForm.CN,
    "中文询价单": InquiryForm.CN,
    "2": InquiryForm.EN,
    "en": InquiryForm.EN,
    "英文": InquiryForm.EN,
    "英文询价单": InquiryForm.EN,
}
for _form in InquiryForm:
    _FORM_ALIASES[_form.name.lower()] = _form
    _FORM_ALIASES[_form.name] = _form
    _FORM_ALIASES[str(_form.code)] = _form
    _FORM_ALIASES[_form.label] = _form

_OPERATE_VIA_ALIASES: dict[str, InquiryOperateVia] = {
    "en": InquiryOperateVia.EN,
    "english": InquiryOperateVia.EN,
    "epak": InquiryOperateVia.EN,
    "英文站": InquiryOperateVia.EN,
    "英文站操作": InquiryOperateVia.EN,
    "cn": InquiryOperateVia.CN,
    "chinese": InquiryOperateVia.CN,
    "中文站": InquiryOperateVia.CN,
    "中文站操作": InquiryOperateVia.CN,
    "中文站操作英文单": InquiryOperateVia.CN,
}
for _via in InquiryOperateVia:
    _OPERATE_VIA_ALIASES[_via.name.lower()] = _via
    _OPERATE_VIA_ALIASES[_via.name] = _via
    _OPERATE_VIA_ALIASES[_via.value] = _via
    _OPERATE_VIA_ALIASES[_via.label] = _via


def parse_inquiry_status(value: InquiryStatus | int | str) -> InquiryStatus:
    if isinstance(value, InquiryStatus):
        return value
    if isinstance(value, int):
        for item in InquiryStatus:
            if item.code == value:
                return item
        raise ValueError(f"未知询价状态码: {value}")
    text = str(value).strip()
    if not text:
        raise ValueError("询价状态不能为空")
    found = _STATUS_ALIASES.get(text) or _STATUS_ALIASES.get(text.lower())
    if found is None:
        names = "、".join(item.label for item in InquiryStatus)
        raise ValueError(f"未知询价状态 {value!r}，可选: {names}")
    return found


def parse_ask_price_type(value: InquiryAskPriceType | int | str) -> InquiryAskPriceType:
    if isinstance(value, InquiryAskPriceType):
        return value
    if isinstance(value, int):
        for item in InquiryAskPriceType:
            if item.code == value:
                return item
        raise ValueError(f"未知询价类型码: {value}")
    text = str(value).strip()
    if not text:
        raise ValueError("询价类型不能为空")
    found = _ASK_TYPE_ALIASES.get(text) or _ASK_TYPE_ALIASES.get(text.lower())
    if found is None:
        names = "、".join(f"{item.label}({item.code})" for item in InquiryAskPriceType)
        raise ValueError(f"未知询价类型 {value!r}，可选: {names}")
    return found


def parse_create_source(value: InquiryCreateSource | str) -> InquiryCreateSource:
    if isinstance(value, InquiryCreateSource):
        return value
    text = str(value).strip()
    if not text:
        raise ValueError("创建入口不能为空")
    found = _SOURCE_ALIASES.get(text) or _SOURCE_ALIASES.get(text.lower())
    if found is None:
        names = "、".join(f"{item.label}({item.value})" for item in InquiryCreateSource)
        raise ValueError(f"未知创建入口 {value!r}，可选: {names}")
    return found


def parse_inquiry_mall(value: InquiryMall | int | str) -> InquiryMall:
    if isinstance(value, InquiryMall):
        return value
    if isinstance(value, int):
        for item in InquiryMall:
            if item.code == value:
                return item
        raise ValueError(f"未知商城码: {value}")
    text = str(value).strip()
    if not text:
        raise ValueError("商城不能为空")
    found = _MALL_ALIASES.get(text) or _MALL_ALIASES.get(text.lower())
    if found is None:
        names = "、".join(f"{item.label}({item.code})" for item in InquiryMall)
        raise ValueError(f"未知商城 {value!r}，可选: {names}")
    return found


def parse_inquiry_form(value: InquiryForm | int | str) -> InquiryForm:
    if isinstance(value, InquiryForm):
        return value
    if isinstance(value, int):
        for item in InquiryForm:
            if item.code == value:
                return item
        raise ValueError(f"未知询价单语种码: {value}")
    text = str(value).strip()
    if not text:
        raise ValueError("询价单语种不能为空")
    found = _FORM_ALIASES.get(text) or _FORM_ALIASES.get(text.lower())
    if found is None:
        names = "、".join(f"{item.label}({item.code})" for item in InquiryForm)
        raise ValueError(f"未知询价单语种 {value!r}，可选: {names}")
    return found


def parse_operate_via(value: InquiryOperateVia | str | None = None) -> InquiryOperateVia:
    """英文单操作站点：en=英文站（默认），cn=中文站操作英文单。"""
    if value is None or value == "":
        return InquiryOperateVia.EN
    if isinstance(value, InquiryOperateVia):
        return value
    text = str(value).strip()
    if not text:
        return InquiryOperateVia.EN
    found = _OPERATE_VIA_ALIASES.get(text) or _OPERATE_VIA_ALIASES.get(text.lower())
    if found is None:
        names = "、".join(f"{item.label}({item.value})" for item in InquiryOperateVia)
        raise ValueError(f"未知操作站点 {value!r}，可选: {names}")
    return found


def default_inquiry_form(*, mall: InquiryMall, source: InquiryCreateSource) -> InquiryForm:
    if mall == InquiryMall.EN:
        return InquiryForm.EN
    return InquiryForm.CN


@dataclass(frozen=True)
class InquiryRoleLogin:
    role: str
    account: str
    password: str
    endpoint: str = "cn"


@dataclass(frozen=True)
class InquiryCreateRoute:
    """内部询价创建路由：入口 × 商城 × 表单语种 × 操作站点 → 接口/Referer/报文形态。"""

    source: InquiryCreateSource
    mall: InquiryMall
    form: InquiryForm
    submit_url: str
    add_draft_url: str
    origin: str
    referer_path: str
    query_params: dict[str, int]
    submit_creates: bool
    supports_draft: bool
    operate_via: InquiryOperateVia = InquiryOperateVia.EN

    @property
    def label(self) -> str:
        base = f"{self.source.label} / {self.mall.label} / {self.form.label}"
        if self.mall == InquiryMall.EN and self.operate_via == InquiryOperateVia.CN:
            return f"{base} / {self.operate_via.label}"
        return base


@dataclass(frozen=True)
class InquiryTransition:
    to_status: InquiryStatus
    role: str
    handler: str
    wired: bool
    recording_title: str
    ui_action: str
    operator_hint: str


@dataclass
class InquirySubSpec:
    """主单下的一条子单规格；流转按子单独立推进。"""

    ask_price_type: InquiryAskPriceType | int | str = InquiryAskPriceType.CUSTOM
    target_status: InquiryStatus | int | str | None = None
    material_name: str | None = None
    qty: int | None = None
    year_purchase_qty: int | None = None
    extra_fields: dict[str, Any] | None = None
    # 英文商城出厂报价：按子单覆盖
    quote_channels: str | None = None  # both / online / offline
    adopt_source: str | None = None  # auto / online / offline
    packaging_type: int | str | None = None  # 1纸箱 2卷类 3其他
    is_pallet: int | str | None = None  # 1是 0否

    def resolved_type(self) -> InquiryAskPriceType:
        return parse_ask_price_type(self.ask_price_type)

    def resolved_target(self) -> InquiryStatus | None:
        if self.target_status is None:
            return None
        return parse_inquiry_status(self.target_status)


@dataclass
class InquirySubFlowResult:
    sub_id: int | None
    sub_number: str | None
    ask_price_type: int | None
    ask_price_type_name: str | None
    status: int | None
    status_name: str | None
    target: InquiryStatus | None
    current_operator: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass
class InquiryFlowResult:
    main_id: int
    source: InquiryCreateSource
    mall: InquiryMall | None = None
    form: InquiryForm | None = None
    main_number: str | None = None
    quotation_no: str | None = None
    # 兼容旧调用：取第一条子单摘要
    sub_id: int | None = None
    sub_number: str | None = None
    status: int | None = None
    status_name: str | None = None
    target: InquiryStatus | None = None
    current_operator: str | None = None
    subs: list[InquirySubFlowResult] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    snapshot: dict[str, Any] = field(default_factory=dict)


def _t(
    to_status: InquiryStatus,
    *,
    role: str,
    handler: str,
    wired: bool,
    recording_title: str,
    ui_action: str,
    operator_hint: str,
) -> InquiryTransition:
    return InquiryTransition(
        to_status=to_status,
        role=role,
        handler=handler,
        wired=wired,
        recording_title=recording_title,
        ui_action=ui_action,
        operator_hint=operator_hint,
    )


# 定制品：保存并提交→待技术方案→技术经理提交→待出厂→采购提交出厂→待平台→上架→关联→转单/完成
CUSTOM_PIPELINE: tuple[InquiryTransition, ...] = (
    _t(
        InquiryStatus.DRAFT,
        role="creator",
        handler="create_draft",
        wired=True,
        recording_title="inquiry_create_draft",
        ui_action="保存草稿",
        operator_hint="创建入口账号（CRM 销售 / 内部询价采购员）",
    ),
    _t(
        InquiryStatus.PENDING_TECH,
        role="creator",
        handler="submit_inquiry",
        wired=True,
        recording_title="inquiry_submit_custom",
        ui_action="保存并提交（定制品→待提交技术方案）",
        operator_hint="创建入口账号；流转记录样本：采购员",
    ),
    _t(
        InquiryStatus.PENDING_FACTORY_QUOTE,
        role="tech",
        handler="submit_tech_solution",
        wired=False,
        recording_title="inquiry_submit_tech",
        ui_action="提交技术方案",
        operator_hint="技术经理（英文商城样本：尤名；中文商城待录）",
    ),
    _t(
        InquiryStatus.PENDING_PLATFORM_QUOTE,
        role="purchaser",
        handler="submit_factory_quote",
        wired=False,
        recording_title="inquiry_factory_quote_custom",
        ui_action="提交出厂报价",
        operator_hint="采购员雷翰（英文商城：推送供应商+线下报价+采纳后提交）",
    ),
    _t(
        InquiryStatus.PENDING_LISTING,
        role="support",
        handler="submit_platform_quote",
        wired=False,
        recording_title="inquiry_platform_quote_custom",
        ui_action="提交平台报价",
        operator_hint="业务支撑张四（英文商城：auth.epakgroup.cn）",
    ),
    _t(
        InquiryStatus.PENDING_ASSOCIATE_PRODUCT,
        role="support",
        handler="apply_listing",
        wired=False,
        recording_title="inquiry_listing_apply_custom",
        ui_action="发起上架申请",
        operator_hint="业务支撑张四（英文商城：confirmPrice）",
    ),
    _t(
        InquiryStatus.PENDING_TRANSFER,
        role="support",
        handler="associate_product",
        wired=False,
        recording_title="inquiry_associate_product_custom",
        ui_action="关联报价商品",
        operator_hint="业务支撑张四（英文商城：relationProduct + submitCustomOrder）",
    ),
    _t(
        InquiryStatus.COMPLETED,
        role="support",
        handler="transfer_to_order",
        wired=False,
        recording_title="inquiry_transfer_to_order",
        ui_action="去创建销售订单 / 完成",
        operator_hint="业务支撑张四（英文商城：create/agent/order）",
    ),
)

# 通用品：无技术方案节点，提交后直接待出厂报价
GENERAL_PIPELINE: tuple[InquiryTransition, ...] = (
    _t(
        InquiryStatus.DRAFT,
        role="creator",
        handler="create_draft",
        wired=True,
        recording_title="inquiry_create_draft",
        ui_action="保存草稿",
        operator_hint="创建入口账号（CRM 销售 / 内部询价采购员）",
    ),
    _t(
        InquiryStatus.PENDING_FACTORY_QUOTE,
        role="creator",
        handler="submit_inquiry",
        wired=True,
        recording_title="inquiry_submit_general",
        ui_action="保存并提交（通用品→待出厂报价，跳过技术方案）",
        operator_hint="创建入口账号；流转记录样本：查晓（采购员）",
    ),
    _t(
        InquiryStatus.PENDING_PLATFORM_QUOTE,
        role="purchaser",
        handler="submit_factory_quote",
        wired=False,
        recording_title="inquiry_factory_quote_general",
        ui_action="提交出厂报价 → 生成平台报价(SYSTEM)",
        operator_hint="采购员雷翰（英文商城：推送供应商+线下报价+采纳后提交）",
    ),
    _t(
        InquiryStatus.PENDING_LISTING,
        role="support",
        handler="submit_platform_quote",
        wired=False,
        recording_title="inquiry_platform_quote_general",
        ui_action="提交平台报价",
        operator_hint="业务支撑张四（英文商城：auth.epakgroup.cn）",
    ),
    _t(
        InquiryStatus.PENDING_ASSOCIATE_PRODUCT,
        role="support",
        handler="apply_listing",
        wired=False,
        recording_title="inquiry_listing_apply_general",
        ui_action="发起上架申请",
        operator_hint="业务支撑张四（英文商城：confirmPrice）",
    ),
    _t(
        InquiryStatus.PENDING_TRANSFER,
        role="support",
        handler="associate_product",
        wired=False,
        recording_title="inquiry_associate_product_general",
        ui_action="关联询价商品",
        operator_hint="业务支撑张四（英文商城：relationProduct + submitCustomOrder）",
    ),
    _t(
        InquiryStatus.COMPLETED,
        role="support",
        handler="transfer_to_order",
        wired=False,
        recording_title="inquiry_transfer_to_order",
        ui_action="去创建销售订单 / 完成",
        operator_hint="业务支撑张四（英文商城：create/agent/order）",
    ),
)

BRANCH_TRANSITIONS: tuple[InquiryTransition, ...] = (
    _t(
        InquiryStatus.CLOSED,
        role="creator",
        handler="close_inquiry",
        wired=False,
        recording_title="inquiry_close",
        ui_action="不成单原因 / 关闭",
        operator_hint="创建人或采购员",
    ),
    _t(
        InquiryStatus.PENDING_SUBMIT,
        role="creator",
        handler="save_pending_submit",
        wired=False,
        recording_title="inquiry_pending_submit",
        ui_action="保存为待提交（status=0，与新建草稿不同）",
        operator_hint="待确认入口",
    ),
)

PIPELINES: dict[InquiryAskPriceType, tuple[InquiryTransition, ...]] = {
    InquiryAskPriceType.CUSTOM: CUSTOM_PIPELINE,
    InquiryAskPriceType.GENERAL: GENERAL_PIPELINE,
}

# 兼容旧名：默认按定制品（含技术方案）
SEED_PIPELINE = CUSTOM_PIPELINE


def pipeline_for(
    ask_price_type: InquiryAskPriceType | int | str,
) -> tuple[InquiryTransition, ...]:
    return PIPELINES[parse_ask_price_type(ask_price_type)]


def pipeline_until(
    target: InquiryStatus,
    *,
    ask_price_type: InquiryAskPriceType | int | str = InquiryAskPriceType.CUSTOM,
) -> tuple[InquiryTransition, ...]:
    ask = parse_ask_price_type(ask_price_type)
    pipe = pipeline_for(ask)
    if target in (InquiryStatus.CLOSED, InquiryStatus.PENDING_SUBMIT):
        prefix = tuple(
            step
            for step in pipe
            if step.handler in ("create_draft", "submit_inquiry")
        )
        branch = next(step for step in BRANCH_TRANSITIONS if step.to_status == target)
        return prefix + (branch,)
    steps: list[InquiryTransition] = []
    for step in pipe:
        steps.append(step)
        if step.to_status == target:
            return tuple(steps)
    labels = "、".join(s.to_status.label for s in pipe)
    raise ValueError(f"「{ask.label}」主路径不含状态 {target.label}；可选: {labels}")


def first_unwired(
    target: InquiryStatus,
    *,
    ask_price_type: InquiryAskPriceType | int | str = InquiryAskPriceType.CUSTOM,
    mall: InquiryMall | None = None,
) -> InquiryTransition | None:
    for step in pipeline_until(target, ask_price_type=ask_price_type):
        if not is_transition_wired(step, mall=mall):
            return step
    return None


def is_transition_wired(
    step: InquiryTransition,
    *,
    mall: InquiryMall | None = None,
    operate_via: InquiryOperateVia | str | None = None,
) -> bool:
    """英文商城已录技术方案～关联商品；转单仅英文站操作可用。

    中文站操作英文单（operate_via=cn）最高做到待转单，不支持转单到已完成。
    """
    if step.wired:
        return True
    if mall != InquiryMall.EN:
        return False
    via = parse_operate_via(operate_via)
    if via == InquiryOperateVia.CN and step.handler == "transfer_to_order":
        return False
    return step.handler in (
        "submit_tech_solution",
        "submit_factory_quote",
        "submit_platform_quote",
        "apply_listing",
        "associate_product",
        "transfer_to_order",
    )


def cn_operate_transfer_blocked_message() -> str:
    return (
        "中文站操作英文询价单不支持转单到「已完成」。"
        "最高目标请用「待转单」；若需已完成请改用英文站："
        "--operate-via en（或不传，默认英文站）。"
    )


def format_recording_hint(
    step: InquiryTransition,
    *,
    ask_price_type: InquiryAskPriceType | None = None,
    source: InquiryCreateSource | None = None,
) -> str:
    parts = [
        f"下一步未接线：{step.to_status.label}（code={step.to_status.code}）。",
        f"角色：{step.role}，操作人：{step.operator_hint}",
        f"页面动作：{step.ui_action}",
    ]
    if ask_price_type is not None:
        parts.append(f"询价类型：{ask_price_type.label}({ask_price_type.code})")
    if source is not None:
        parts.append(f"创建入口：{source.label} → {source.referer_path}")
        parts.append(
            "若尚未录创建入口，可先："
            f"python scripts/record_regression_session.py --title {source.recording_title} --headed"
        )
    parts.append(
        "请录制：python scripts/record_regression_session.py "
        f"--title {step.recording_title} --headed"
    )
    parts.append(f"录完把主接口 URL/报文补进 CrmInquiryService.{step.handler}")
    return "\n".join(parts)


class InquiryTransitionNotWired(NotImplementedError):
    def __init__(
        self,
        step: InquiryTransition,
        *,
        ask_price_type: InquiryAskPriceType | None = None,
        source: InquiryCreateSource | None = None,
        message: str | None = None,
    ):
        self.step = step
        self.ask_price_type = ask_price_type
        self.source = source
        super().__init__(
            message
            or format_recording_hint(step, ask_price_type=ask_price_type, source=source)
        )


class InquiryRoleMissing(RuntimeError):
    def __init__(self, role: str, step: InquiryTransition):
        self.role = role
        self.step = step
        if role == "support":
            tip = (
                "英文站配 EPAK_INQUIRY_SUPPORT_ACCOUNT；"
                "--operate-via cn 时须能登录中文 auth"
                "（优先 CRM_INQUIRY_SUPPORT_ACCOUNT，失败可由 purchaser/sales 兜底）"
            )
        else:
            tip = (
                f"请配置对应 CRM_INQUIRY_{role.upper()}_ACCOUNT "
                f"（creator 可用 sales/purchaser 兜底）"
            )
        super().__init__(
            f"造数到「{step.to_status.label}」需要 {role} 账号，{tip}。"
            f"现网操作人样本：{step.operator_hint}"
        )


def resolve_role_ctx(
    roles: dict[str, Any],
    role: str,
    *,
    source: InquiryCreateSource,
) -> Any | None:
    """creator 按创建入口映射：CRM→sales，内部询价→purchaser，再兜底。"""
    if role == "creator":
        if source == InquiryCreateSource.INTERNAL:
            order = ("purchaser", "creator", "sales")
        else:
            order = ("sales", "creator", "purchaser")
        for key in order:
            if key in roles:
                return roles[key]
        return None
    return roles.get(role)
