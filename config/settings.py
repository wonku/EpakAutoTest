import json
import os
import re
from pathlib import Path

from config.env_loader import PROJECT_ROOT, bootstrap_env

# 先按 EPAK_ENV / --env 加载 .env + .env.en.{test|uat|prod}，再读下方配置
EPAK_ENV = bootstrap_env()
CRM_INQUIRY_ALLOW_PROD_SEED = os.getenv(
    "CRM_INQUIRY_ALLOW_PROD_SEED", "0"
).strip().lower() in {"1", "true", "yes", "y"}


def parse_email_recipients(raw: str | None = None) -> list[str]:
    value = raw if raw is not None else os.getenv("EMAIL_TO", "")
    if not value:
        return []
    parts = re.split(r"[,;]", value)
    return [item.strip() for item in parts if item.strip()]

BASE_URL = os.getenv("BASE_URL", "https://test-auth.ysbpack.com")
LOGIN_PATH = os.getenv("LOGIN_PATH", "/user/login")
LOGIN_PHONE = os.getenv("LOGIN_PHONE", "13550147740")
LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD", "Esbao0930666")
LOGIN_PASSWORD_ENCRYPTED = os.getenv("LOGIN_PASSWORD_ENCRYPTED", "HcCnzfhJr4kFtev4QVJnGA==")
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
SLOW_MO = int(os.getenv("SLOW_MO", "150"))
BROWSER_EXECUTABLE_PATH = os.getenv("BROWSER_EXECUTABLE_PATH", "").strip()
# UI 浏览器：chromium（默认，与现网一致）| firefox | webkit | chrome | msedge
# 日常回归勿改；兼容测试用 CLI：pytest --ui-browser=firefox 或 --ui-browsers=chromium,firefox,webkit
UI_BROWSER = (os.getenv("UI_BROWSER", "chromium") or "chromium").strip().lower()
UI_BROWSERS = [
    item.strip().lower()
    for item in (os.getenv("UI_BROWSERS", "") or "").split(",")
    if item.strip()
]
AUTH_API_URL = os.getenv("AUTH_API_URL", "https://test-auth.ysbpack.com/api/member/login")
APP_HOME_URL = os.getenv("APP_HOME_URL", "https://test-platform.ysbpack.com/")
AUTH_ENVIRONMENT = os.getenv("AUTH_ENVIRONMENT", "1")
AUTH_SITE = os.getenv("AUTH_SITE", "1")
AUTH_SOURCE = os.getenv("AUTH_SOURCE", "1")
API_TIMEOUT_SECONDS = int(os.getenv("API_TIMEOUT_SECONDS", "30"))
# 接口请求遇到 SSL/连接闪断时的重试（常见于 test-auth SSLEOFError）
API_REQUEST_RETRIES = int(os.getenv("API_REQUEST_RETRIES", "3"))
API_RETRY_BACKOFF_SECONDS = float(os.getenv("API_RETRY_BACKOFF_SECONDS", "1.5"))
API_SSL_VERIFY = os.getenv("API_SSL_VERIFY", "true").lower() == "true"
PLATFORM_BASE_URL = os.getenv("PLATFORM_BASE_URL", "https://test-platform.ysbpack.com")
# 英文询价造数：供应商线上报价走中文站登录/平台（可与英文 EPAK_* 不同环境）
CRM_INQUIRY_SUPPLIER_AUTH_ORIGIN = os.getenv(
    "CRM_INQUIRY_SUPPLIER_AUTH_ORIGIN",
    "",
).strip().rstrip("/") or (
    BASE_URL.rstrip("/") if str(BASE_URL).startswith("http") else "https://test-auth.ysbpack.com"
)
CRM_INQUIRY_SUPPLIER_AUTH_API_URL = os.getenv(
    "CRM_INQUIRY_SUPPLIER_AUTH_API_URL",
    "",
).strip() or f"{CRM_INQUIRY_SUPPLIER_AUTH_ORIGIN}/api/member/login"
CRM_INQUIRY_SUPPLIER_PLATFORM_BASE_URL = os.getenv(
    "CRM_INQUIRY_SUPPLIER_PLATFORM_BASE_URL",
    "",
).strip().rstrip("/") or PLATFORM_BASE_URL.rstrip("/")
CRM_LEAD_SAVE_API_URL = os.getenv(
    "CRM_LEAD_SAVE_API_URL", "https://test-platform.ysbpack.com/api/crm/lead/saveOrUpdate"
)
CRM_LEAD_PAGE_API_URL = os.getenv("CRM_LEAD_PAGE_API_URL", "https://test-platform.ysbpack.com/api/crm/lead/page")
CRM_LEAD_DETAIL_API_URL = os.getenv(
    "CRM_LEAD_DETAIL_API_URL",
    "https://test-platform.ysbpack.com/api/crm/lead/detail",
)
CRM_DIC_BY_TYPE_API_URL = os.getenv(
    "CRM_DIC_BY_TYPE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/common/queryDicByType",
)
CRM_EXHIBITION_OPTIONS_API_URL = os.getenv(
    "CRM_EXHIBITION_OPTIONS_API_URL",
    "https://test-platform.ysbpack.com/api/crm/exhibition/options",
)
COUNTRY_LIST_API_URL = os.getenv(
    "COUNTRY_LIST_API_URL", "https://test-platform.ysbpack.com/api/crm/common/country/list"
)
CRM_ACTIVITY_SAVE_API_URL = os.getenv(
    "CRM_ACTIVITY_SAVE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/common/activity/saveOrUpdate",
)
CRM_LEAD_MOVE_PUBLIC_SEA_API_URL = os.getenv(
    "CRM_LEAD_MOVE_PUBLIC_SEA_API_URL",
    "https://test-platform.ysbpack.com/api/crm/lead/movePublicSea",
)
MOVE_PUBLIC_SEA_REASON_CODE = int(os.getenv("MOVE_PUBLIC_SEA_REASON_CODE", "5"))
MOVE_PUBLIC_SEA_REMARK = os.getenv("MOVE_PUBLIC_SEA_REMARK", "自动化移入公海")
MOVE_PUBLIC_SEA_LEAD_IDS = [
    int(item.strip())
    for item in os.getenv("MOVE_PUBLIC_SEA_LEAD_IDS", "495").split(",")
    if item.strip()
]
MOVE_PUBLIC_SEA_CASES = os.getenv("MOVE_PUBLIC_SEA_CASES", "").strip()
CRM_LEAD_CLAIM_API_URL = os.getenv(
    "CRM_LEAD_CLAIM_API_URL",
    "https://test-platform.ysbpack.com/api/crm/lead/claimLead",
)
CLAIM_LEAD_LEAD_IDS = [
    int(item.strip())
    for item in os.getenv("CLAIM_LEAD_LEAD_IDS", "495").split(",")
    if item.strip()
]
CLAIM_LEAD_CASES = os.getenv("CLAIM_LEAD_CASES", "").strip()
MEMBER_USER_EFFECTIVE_LIST_API_URL = os.getenv(
    "MEMBER_USER_EFFECTIVE_LIST_API_URL",
    "https://test-platform.ysbpack.com/api/member/user/effective/list",
)
CRM_LEAD_ASSIGN_API_URL = os.getenv(
    "CRM_LEAD_ASSIGN_API_URL",
    "https://test-platform.ysbpack.com/api/crm/lead/assign",
)
CRM_LEAD_DELETE_API_URL = os.getenv(
    "CRM_LEAD_DELETE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/lead/delete",
)
# 客户模块（录制会话 20260803-142110 / customer_main）
CRM_CUSTOMER_PAGE_API_URL = os.getenv(
    "CRM_CUSTOMER_PAGE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/customer/page",
)
CRM_CUSTOMER_FIND_BY_ID_API_URL = os.getenv(
    "CRM_CUSTOMER_FIND_BY_ID_API_URL",
    "https://test-platform.ysbpack.com/api/crm/customer/findById",
)
CRM_CUSTOMER_CHECK_REPEAT_API_URL = os.getenv(
    "CRM_CUSTOMER_CHECK_REPEAT_API_URL",
    "https://test-platform.ysbpack.com/api/crm/customer/checkRepeatPage",
)
CRM_CUSTOMER_SAVE_API_URL = os.getenv(
    "CRM_CUSTOMER_SAVE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/customer/save",
)
CRM_CUSTOMER_UPDATE_API_URL = os.getenv(
    "CRM_CUSTOMER_UPDATE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/customer/update",
)
CRM_ACTIVITY_PAGE_API_URL = os.getenv(
    "CRM_ACTIVITY_PAGE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/common/activity/page",
)
CRM_ACTIVITY_REFERER = os.getenv(
    "CRM_ACTIVITY_REFERER",
    "/memberCenter/crm2Ability/activityLog",
)
CRM_CUSTOMER_REFERER = os.getenv(
    "CRM_CUSTOMER_REFERER",
    "/memberCenter/crm2Ability/customer",
)
CRM_CUSTOMER_DUP_REFERER = os.getenv(
    "CRM_CUSTOMER_DUP_REFERER",
    "/memberCenter/crm2Ability/customerDuplicateCheck",
)
CRM_CUSTOMER_VIEW_TYPE = int(os.getenv("CRM_CUSTOMER_VIEW_TYPE", "1"))
CRM_CUSTOMER_ACTIVITY_RECORD_TYPE_CODE = int(
    os.getenv("CRM_CUSTOMER_ACTIVITY_RECORD_TYPE_CODE", "2")
)
# 销售机会（录制会话 20260803-155343 / opportunity_main）
CRM_OPPORTUNITY_PAGE_API_URL = os.getenv(
    "CRM_OPPORTUNITY_PAGE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/sale/opportunity/page",
)
CRM_OPPORTUNITY_FIND_BY_ID_API_URL = os.getenv(
    "CRM_OPPORTUNITY_FIND_BY_ID_API_URL",
    "https://test-platform.ysbpack.com/api/crm/sale/opportunity/findById",
)
CRM_OPPORTUNITY_SAVE_API_URL = os.getenv(
    "CRM_OPPORTUNITY_SAVE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/sale/opportunity/saveOrUpdate",
)
CRM_OPPORTUNITY_DELETE_API_URL = os.getenv(
    "CRM_OPPORTUNITY_DELETE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/sale/opportunity/delete",
)
# 拜访日程
CRM_VISIT_SCHEDULE_PAGE_API_URL = os.getenv(
    "CRM_VISIT_SCHEDULE_PAGE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/visit/schedule/page",
)
CRM_VISIT_SCHEDULE_SAVE_API_URL = os.getenv(
    "CRM_VISIT_SCHEDULE_SAVE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/visit/schedule/saveOrUpdate",
)
CRM_VISIT_SCHEDULE_DELETE_API_URL = os.getenv(
    "CRM_VISIT_SCHEDULE_DELETE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/visit/schedule/delete",
)
CRM_UI_VISIT_CUSTOMER_KEYWORD = os.getenv(
    "CRM_UI_VISIT_CUSTOMER_KEYWORD",
    "北京中镜眼镜有限责任公司",
).strip()
CRM_CONTACT_PERSON_PAGE_API_URL = os.getenv(
    "CRM_CONTACT_PERSON_PAGE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/customer/contactPerson/page",
)
CRM_OPPORTUNITY_REFERER = os.getenv(
    "CRM_OPPORTUNITY_REFERER",
    "/memberCenter/crm2Ability/salesOpportunity",
)
CRM_OPPORTUNITY_ACTIVITY_RECORD_TYPE_CODE = int(
    os.getenv("CRM_OPPORTUNITY_ACTIVITY_RECORD_TYPE_CODE", "4")
)
# 联系人（录制会话 20260803-164057 / contact_main）
CRM_CONTACT_PAGE_API_URL = os.getenv(
    "CRM_CONTACT_PAGE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/contact/person/page",
)
CRM_CONTACT_FIND_BY_ID_API_URL = os.getenv(
    "CRM_CONTACT_FIND_BY_ID_API_URL",
    "https://test-platform.ysbpack.com/api/crm/contact/person/findById",
)
CRM_CONTACT_SAVE_API_URL = os.getenv(
    "CRM_CONTACT_SAVE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/contact/person/saveOrUpdate",
)
CRM_CONTACT_DELETE_API_URL = os.getenv(
    "CRM_CONTACT_DELETE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/contact/person/delete",
)
CRM_CONTACT_REFERER = os.getenv(
    "CRM_CONTACT_REFERER",
    "/memberCenter/crm2Ability/contactPerson",
)
CRM_CONTACT_ACTIVITY_RECORD_TYPE_CODE = int(
    os.getenv("CRM_CONTACT_ACTIVITY_RECORD_TYPE_CODE", "3")
)
ASSIGN_LEAD_LEAD_IDS = [
    int(item.strip())
    for item in os.getenv("ASSIGN_LEAD_LEAD_IDS", "495").split(",")
    if item.strip()
]
ASSIGN_LEAD_NEW_FOLLOW_USER_NAME = os.getenv(
    "ASSIGN_LEAD_NEW_FOLLOW_USER_NAME",
    "甜甜（采购员）",
)
_assign_lead_follow_user_id = os.getenv("ASSIGN_LEAD_NEW_FOLLOW_USER_ID", "").strip()
ASSIGN_LEAD_NEW_FOLLOW_USER_ID = (
    int(_assign_lead_follow_user_id) if _assign_lead_follow_user_id else None
)
ASSIGN_LEAD_CASES = os.getenv("ASSIGN_LEAD_CASES", "").strip()
CRM_DEFAULT_FOLLOW_USER_ID = int(os.getenv("CRM_DEFAULT_FOLLOW_USER_ID", "104360"))
CRM_DEFAULT_FOLLOW_USER_NAME = os.getenv("CRM_DEFAULT_FOLLOW_USER_NAME", "tinker001")
LEAD_COUNTRY = os.getenv("LEAD_COUNTRY", "中国")
LEAD_COUNTRY_CODE = os.getenv("LEAD_COUNTRY_CODE", "")
# 线索来源：优先 LEAD_SOURCE_CODE；也可填名称（如「展会」）由字典接口解析
_lead_source_code = os.getenv("LEAD_SOURCE_CODE", "").strip()
LEAD_SOURCE_CODE = int(_lead_source_code) if _lead_source_code else None
LEAD_SOURCE = os.getenv("LEAD_SOURCE", "").strip()
# 线索等级：优先 LEAD_LEVEL_CODE（0=S…4=D）；也可填 S/A/B/C/D
_lead_level_code = os.getenv("LEAD_LEVEL_CODE", "").strip()
LEAD_LEVEL_CODE = int(_lead_level_code) if _lead_level_code else None
LEAD_LEVEL = os.getenv("LEAD_LEVEL", "").strip()
# 展会：优先 CRM_EXHIBITION_ID；也可填展会名称由 options 接口解析
_crm_exhibition_id = os.getenv("CRM_EXHIBITION_ID", "").strip()
CRM_EXHIBITION_ID = int(_crm_exhibition_id) if _crm_exhibition_id else None
LEAD_EXHIBITION_NAME = os.getenv("LEAD_EXHIBITION_NAME", "").strip()
# 创建线索多组数据驱动（设置后优先于上方单值默认）
# CREATE_LEAD_CASES=[{"lead_source":"展会","lead_level":"A","exhibition_name":"tinker展会01易食包参加有效修改名称"}]
CREATE_LEAD_CASES = os.getenv("CREATE_LEAD_CASES", "").strip()
ACTIVITY_TYPE_CODE = int(os.getenv("ACTIVITY_TYPE_CODE", "2"))
ACTIVITY_RECORD_TYPE_CODE = int(os.getenv("ACTIVITY_RECORD_TYPE_CODE", "1"))
CAPTCHA_MAX_AUTO_RETRY = int(os.getenv("CAPTCHA_MAX_AUTO_RETRY", "3"))
CAPTCHA_MANUAL_FALLBACK = os.getenv("CAPTCHA_MANUAL_FALLBACK", "true").lower() == "true"
CAPTCHA_MANUAL_WAIT_SECONDS = int(os.getenv("CAPTCHA_MANUAL_WAIT_SECONDS", "120"))
CAPTCHA_DRAG_STEPS = int(os.getenv("CAPTCHA_DRAG_STEPS", "20"))
CAPTCHA_DRAG_STEP_DELAY_MIN = float(os.getenv("CAPTCHA_DRAG_STEP_DELAY_MIN", "0.03"))
CAPTCHA_DRAG_STEP_DELAY_MAX = float(os.getenv("CAPTCHA_DRAG_STEP_DELAY_MAX", "0.08"))
CAPTCHA_HOLD_AFTER_REACH_MIN_MS = int(os.getenv("CAPTCHA_HOLD_AFTER_REACH_MIN_MS", "500"))
CAPTCHA_HOLD_AFTER_REACH_MAX_MS = int(os.getenv("CAPTCHA_HOLD_AFTER_REACH_MAX_MS", "1000"))
CAPTCHA_SWEEP_ENABLED = os.getenv("CAPTCHA_SWEEP_ENABLED", "true").lower() == "true"
CAPTCHA_SWEEP_START_RATIO = float(os.getenv("CAPTCHA_SWEEP_START_RATIO", "0.45"))
CAPTCHA_SWEEP_END_RATIO = float(os.getenv("CAPTCHA_SWEEP_END_RATIO", "0.95"))
CAPTCHA_SWEEP_STEP_PX = int(os.getenv("CAPTCHA_SWEEP_STEP_PX", "12"))
CAPTCHA_SWEEP_HOLD_MS = int(os.getenv("CAPTCHA_SWEEP_HOLD_MS", "900"))
CAPTCHA_IMAGE_SOLVE_ENABLED = os.getenv("CAPTCHA_IMAGE_SOLVE_ENABLED", "true").lower() == "true"
CAPTCHA_IMAGE_SOLVE_OFFSET_PX = int(os.getenv("CAPTCHA_IMAGE_SOLVE_OFFSET_PX", "6"))

MOBILE_APK_PATH = os.getenv("MOBILE_APK_PATH", str(PROJECT_ROOT / "app-release.apk")).strip()
MOBILE_PACKAGE_NAME = os.getenv("MOBILE_PACKAGE_NAME", "").strip()
MOBILE_DEVICE_SERIAL = os.getenv("MOBILE_DEVICE_SERIAL", "").strip()
MOBILE_ADB_PATH = os.getenv("MOBILE_ADB_PATH", "adb").strip()
MOBILE_INSTALL_APK = os.getenv("MOBILE_INSTALL_APK", "true").lower() == "true"
MOBILE_LOGIN_ENABLED = os.getenv("MOBILE_LOGIN_ENABLED", "false").lower() == "true"
MOBILE_LOGIN_DATA_PATH = os.getenv(
    "MOBILE_LOGIN_DATA_PATH",
    str(PROJECT_ROOT / "config" / "mobile_login.json"),
).strip()
MONKEY_EVENT_COUNT = int(os.getenv("MONKEY_EVENT_COUNT", "5000"))
MONKEY_THROTTLE_MS = int(os.getenv("MONKEY_THROTTLE_MS", "200"))
MONKEY_SEED = os.getenv("MONKEY_SEED", "").strip()
MONKEY_EXTRA_ARGS = os.getenv(
    "MONKEY_EXTRA_ARGS",
    "--ignore-crashes --ignore-timeouts --monitor-native-crashes "
    "--pct-syskeys 0 --pct-appswitch 0 --pct-anyevent 0 "
    "--pct-motion 0 --pct-trackball 0 --pct-nav 0 --pct-majornav 0",
).strip()
MONKEY_FAIL_ON_CRASH = os.getenv("MONKEY_FAIL_ON_CRASH", "true").lower() == "true"
MONKEY_REPORT_DIR = os.getenv("MONKEY_REPORT_DIR", str(PROJECT_ROOT / "reports" / "mobile" / "monkey")).strip()
MONKEY_KEEP_WIFI_ENABLED = os.getenv("MONKEY_KEEP_WIFI_ENABLED", "true").lower() == "true"
MONKEY_CHUNK_EVENT_COUNT = int(os.getenv("MONKEY_CHUNK_EVENT_COUNT", "500"))
MONKEY_SCREENSHOT_ENABLED = os.getenv("MONKEY_SCREENSHOT_ENABLED", "true").lower() == "true"
MONKEY_WHITE_SCREEN_ENABLED = os.getenv("MONKEY_WHITE_SCREEN_ENABLED", "true").lower() == "true"
MONKEY_WHITE_SCREEN_BRIGHTNESS_THRESHOLD = int(os.getenv("MONKEY_WHITE_SCREEN_BRIGHTNESS_THRESHOLD", "245"))
MONKEY_WHITE_SCREEN_RATIO = float(os.getenv("MONKEY_WHITE_SCREEN_RATIO", "0.90"))
MONKEY_ERROR_TEXT_KEYWORDS = [
    item.strip()
    for item in os.getenv(
        "MONKEY_ERROR_TEXT_KEYWORDS",
        "Error,Failed,Exception,Network error,Something went wrong,加载失败,错误,异常,白屏",
    ).split(",")
    if item.strip()
]
MONKEY_FAIL_ON_INSPECTION_ISSUE = os.getenv("MONKEY_FAIL_ON_INSPECTION_ISSUE", "true").lower() == "true"

APPIUM_SERVER_URL = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723").strip()
APPIUM_APP_ACTIVITY = os.getenv("APPIUM_APP_ACTIVITY", ".MainActivity").strip()
APPIUM_NO_RESET = os.getenv("APPIUM_NO_RESET", "true").lower() == "true"
APPIUM_NEW_COMMAND_TIMEOUT = int(os.getenv("APPIUM_NEW_COMMAND_TIMEOUT", "300"))
APPIUM_IMPLICIT_WAIT_SECONDS = int(os.getenv("APPIUM_IMPLICIT_WAIT_SECONDS", "2"))
APPIUM_EXPLORE_STEPS = int(os.getenv("APPIUM_EXPLORE_STEPS", "100"))
APPIUM_EXPLORE_PAUSE_MS = int(os.getenv("APPIUM_EXPLORE_PAUSE_MS", "500"))
APPIUM_REPORT_DIR = os.getenv("APPIUM_REPORT_DIR", str(PROJECT_ROOT / "reports" / "mobile" / "appium")).strip()
APPIUM_SCREENSHOT_ENABLED = os.getenv("APPIUM_SCREENSHOT_ENABLED", "true").lower() == "true"
APPIUM_WHITE_SCREEN_ENABLED = os.getenv("APPIUM_WHITE_SCREEN_ENABLED", "true").lower() == "true"
APPIUM_FAIL_ON_ISSUE = os.getenv("APPIUM_FAIL_ON_ISSUE", "true").lower() == "true"
APPIUM_BLOCK_TEXT_KEYWORDS = [
    item.strip()
    for item in os.getenv(
        "APPIUM_BLOCK_TEXT_KEYWORDS",
        "Logout,Log out,Delete,Remove,Pay,Payment,退出,注销,删除,支付",
    ).split(",")
    if item.strip()
]

EMAIL_REPORT_ENABLED = os.getenv("EMAIL_REPORT_ENABLED", "false").lower() == "true"
EMAIL_SMTP_HOST = os.getenv("EMAIL_SMTP_HOST", "").strip()
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "465"))
EMAIL_SMTP_SSL = os.getenv("EMAIL_SMTP_SSL", "true").lower() == "true"
EMAIL_SMTP_STARTTLS = os.getenv("EMAIL_SMTP_STARTTLS", "false").lower() == "true"
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME", "").strip()
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "").strip()
EMAIL_FROM = os.getenv("EMAIL_FROM", EMAIL_USERNAME).strip()
EMAIL_TO = parse_email_recipients()
EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "[Pyautotest]").strip()
EMAIL_REPORT_LABEL = os.getenv("EMAIL_REPORT_LABEL", "").strip()
EMAIL_ATTACH_LOGS = os.getenv("EMAIL_ATTACH_LOGS", "true").lower() == "true"
EMAIL_MAX_ATTACHMENT_MB = int(os.getenv("EMAIL_MAX_ATTACHMENT_MB", "10"))

ESB_AUTH_URL = os.getenv("ESB_AUTH_URL", "https://auth.esbao.com/").strip()
ESB_MALL_HOME_URL = os.getenv("ESB_MALL_HOME_URL", "https://www.esbao.com/").strip()
ESB_UI_REPORT_DIR = os.getenv(
    "ESB_UI_REPORT_DIR",
    str(PROJECT_ROOT / "reports" / "ui" / "esbao"),
).strip()
ESB_UI_HEADLESS = os.getenv("ESB_UI_HEADLESS", os.getenv("HEADLESS", "true")).lower() == "true"
ESB_UI_VIEWPORT_WIDTH = int(os.getenv("ESB_UI_VIEWPORT_WIDTH", "1920"))
ESB_UI_VIEWPORT_HEIGHT = int(os.getenv("ESB_UI_VIEWPORT_HEIGHT", "1080"))
ESB_UI_SCROLL_PAUSE_MS = int(os.getenv("ESB_UI_SCROLL_PAUSE_MS", "800"))
ESB_UI_IMAGE_SETTLE_MS = int(os.getenv("ESB_UI_IMAGE_SETTLE_MS", "3000"))
ESB_UI_HOME_IMAGE_WAIT_MS = int(os.getenv("ESB_UI_HOME_IMAGE_WAIT_MS", "20000"))
ESB_UI_DETAIL_READY_MS = int(os.getenv("ESB_UI_DETAIL_READY_MS", "60000"))
ESB_UI_HOT_PRODUCT_KEYWORD = os.getenv("ESB_UI_HOT_PRODUCT_KEYWORD", "").strip()

MALL_UI_NAV_TIMEOUT_MS = int(os.getenv("MALL_UI_NAV_TIMEOUT_MS", "120000"))
MALL_UI_AUTH_READY_TIMEOUT_MS = int(
    os.getenv("MALL_UI_AUTH_READY_TIMEOUT_MS", "60000")
)
MALL_UI_GOTO_WAIT_UNTIL = os.getenv("MALL_UI_GOTO_WAIT_UNTIL", "commit").strip()
MALL_UI_GOTO_RETRIES = int(os.getenv("MALL_UI_GOTO_RETRIES", "3"))
MALL_UI_DETAIL_IMAGE_WAIT_MS = int(os.getenv("MALL_UI_DETAIL_IMAGE_WAIT_MS", "90000"))
MALL_UI_HOME_TEXT_WAIT_MS = int(os.getenv("MALL_UI_HOME_TEXT_WAIT_MS", "30000"))

CRM_YUYINGCLOUD_CALL_PHONE_API_URL = os.getenv(
    "CRM_YUYINGCLOUD_CALL_PHONE_API_URL",
    "https://test-platform.ysbpack.com/api/crm/yuyingcloud/callPhone",
)
OUTBOUND_CALL_OPERATE_TYPE_CODE = int(os.getenv("OUTBOUND_CALL_OPERATE_TYPE_CODE", "1"))
OUTBOUND_KEEPALIVE_PASSWORD_ENCRYPTED = os.getenv("OUTBOUND_KEEPALIVE_PASSWORD_ENCRYPTED", "").strip()
OUTBOUND_KEEPALIVE_ACCOUNT_INTERVAL_SECONDS = int(
    os.getenv("OUTBOUND_KEEPALIVE_ACCOUNT_INTERVAL_SECONDS", "300")
)
OUTBOUND_KEEPALIVE_REPORT_DIR = os.getenv(
    "OUTBOUND_KEEPALIVE_REPORT_DIR",
    str(PROJECT_ROOT / "reports" / "outbound-keepalive"),
).strip()
OUTBOUND_KEEPALIVE_CASES_RAW = os.getenv("OUTBOUND_KEEPALIVE_CASES", "").strip()


def _default_outbound_keepalive_cases() -> list[dict]:
    return [
        {"account": "17701563749", "relation_id": 603},
        {"account": "17768025264", "relation_id": 603},
        {"account": "17751104143", "relation_id": 603},
    ]


def load_outbound_keepalive_cases() -> list[dict]:
    if not OUTBOUND_KEEPALIVE_CASES_RAW:
        return _default_outbound_keepalive_cases()
    raw_cases = json.loads(OUTBOUND_KEEPALIVE_CASES_RAW)
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("OUTBOUND_KEEPALIVE_CASES 必须是非空 JSON 数组")
    cases: list[dict] = []
    for index, item in enumerate(raw_cases):
        if not isinstance(item, dict):
            raise ValueError(f"OUTBOUND_KEEPALIVE_CASES[{index}] 必须是对象")
        account = item.get("account") or item.get("phone")
        if not account:
            raise ValueError(f"OUTBOUND_KEEPALIVE_CASES[{index}] 缺少 account / phone")
        case: dict = {"account": str(account)}
        if item.get("relation_id") is not None or item.get("relationId") is not None:
            case["relation_id"] = int(item.get("relation_id") or item.get("relationId"))
        password_encrypted = (
            item.get("password_encrypted")
            or item.get("passwordEncrypted")
            or item.get("password")
        )
        if password_encrypted:
            case["password_encrypted"] = str(password_encrypted)
        cases.append(case)
    return cases


OUTBOUND_KEEPALIVE_CASES = load_outbound_keepalive_cases()

EPAK_AUTH_URL = os.getenv(
    "EPAK_AUTH_URL", "https://auth.epakgroup.com/user/login"
).strip()
EPAK_MALL_HOME_URL = os.getenv("EPAK_MALL_HOME_URL", "https://www.epakgroup.com/").strip()
# 英文商城测试平台（登录 auth.epakgroup.cn，业务 platform.epakgroup.cn）
EPAK_PLATFORM_BASE_URL = os.getenv(
    "EPAK_PLATFORM_BASE_URL",
    "https://platform.epakgroup.cn",
).rstrip("/")
EPAK_PLATFORM_AUTH_ORIGIN = os.getenv(
    "EPAK_PLATFORM_AUTH_ORIGIN",
    "https://auth.epakgroup.cn",
).rstrip("/")
EPAK_PLATFORM_AUTH_API_URL = os.getenv(
    "EPAK_PLATFORM_AUTH_API_URL",
    f"{EPAK_PLATFORM_AUTH_ORIGIN}/api/member/login",
).strip()
EPAK_PLATFORM_AUTH_REFERER = os.getenv(
    "EPAK_PLATFORM_AUTH_REFERER",
    f"{EPAK_PLATFORM_AUTH_ORIGIN}/user/login?",
).strip()
EPAK_PLATFORM_ACCEPT_LANGUAGE = os.getenv(
    "EPAK_PLATFORM_ACCEPT_LANGUAGE",
    "en-US",
).strip()
EPAK_PLATFORM_LANG_COOKIE = os.getenv(
    "EPAK_PLATFORM_LANG_COOKIE",
    "LX_LANG=ZW4tVVM=",
).strip()
EPAK_LOGIN_PHONE = os.getenv("EPAK_LOGIN_PHONE", LOGIN_PHONE).strip()
EPAK_LOGIN_PASSWORD_ENCRYPTED = os.getenv(
    "EPAK_LOGIN_PASSWORD_ENCRYPTED",
    LOGIN_PASSWORD_ENCRYPTED,
).strip()
EPAK_UI_REPORT_DIR = os.getenv(
    "EPAK_UI_REPORT_DIR",
    str(PROJECT_ROOT / "reports" / "ui" / "epak"),
).strip()
EPAK_UI_PRODUCT_KEYWORD = os.getenv("EPAK_UI_PRODUCT_KEYWORD", "Slant Spout").strip()

ORDER_AGENT_CREATE_API_URL = os.getenv(
    "ORDER_AGENT_CREATE_API_URL",
    "https://test-platform.ysbpack.com/api/order/vendor/create/agent/order",
)
ORDER_VENDOR_PAGE_API_URL = os.getenv(
    "ORDER_VENDOR_PAGE_API_URL",
    "https://test-platform.ysbpack.com/api/order/vendor/page",
)
ORDER_FILE_UPLOAD_BATCH_API_URL = os.getenv(
    "ORDER_FILE_UPLOAD_BATCH_API_URL",
    "https://test-platform.ysbpack.com/api/file/file/upload/batch",
)
ORDER_UPLOAD_CONTRACT_API_URL = os.getenv(
    "ORDER_UPLOAD_CONTRACT_API_URL",
    "https://test-platform.ysbpack.com/api/order/vendor/upload/contract",
)
ORDER_COMBINATION_DETAIL_API_URL = os.getenv(
    "ORDER_COMBINATION_DETAIL_API_URL",
    "https://test-platform.ysbpack.com/api/order/vendor/combination/detail",
)
ORDER_VALET_PAY_API_URL = os.getenv(
    "ORDER_VALET_PAY_API_URL",
    "https://test-platform.ysbpack.com/api/order/vendor/validate/valet/pay",
)
ORDER_PAY_CONFIRM_API_URL = os.getenv(
    "ORDER_PAY_CONFIRM_API_URL",
    "https://test-platform.ysbpack.com/api/order/vendor/validate/pay/confirm",
)
ORDER_BUYER_MEMBER_ID = int(os.getenv("ORDER_BUYER_MEMBER_ID", "104440"))
ORDER_BUYER_MEMBER_NAME = os.getenv("ORDER_BUYER_MEMBER_NAME", "衢州白马投资有限公司")
ORDER_SKU_ID = int(os.getenv("ORDER_SKU_ID", "107721"))
ORDER_QUANTITY = int(os.getenv("ORDER_QUANTITY", "100"))
ORDER_UNIT_PRICE = float(os.getenv("ORDER_UNIT_PRICE", "25"))
ORDER_PAY_TYPE = int(os.getenv("ORDER_PAY_TYPE", "2"))
ORDER_PAY_CHANNEL = int(os.getenv("ORDER_PAY_CHANNEL", "5"))
ORDER_FUND_MODE = int(os.getenv("ORDER_FUND_MODE", "2"))
ORDER_EXPECTED_INNER_STATUS = int(os.getenv("ORDER_EXPECTED_INNER_STATUS", "124"))
ORDER_EXPECTED_OUTER_STATUS = int(os.getenv("ORDER_EXPECTED_OUTER_STATUS", "17"))
ORDER_EXPECTED_STATUS_NAME = os.getenv("ORDER_EXPECTED_STATUS_NAME", "订单备货中")
ORDER_QUERY_MAX_RETRIES = int(os.getenv("ORDER_QUERY_MAX_RETRIES", "10"))
ORDER_QUERY_RETRY_INTERVAL_SECONDS = float(os.getenv("ORDER_QUERY_RETRY_INTERVAL_SECONDS", "2"))
ORDER_CONTRACT_FILE_PATH = os.getenv(
    "ORDER_CONTRACT_FILE_PATH",
    str(PROJECT_ROOT / "testdata" / "order" / "contract_sample.jpg"),
).strip()
ORDER_VOUCHER_FILE_PATH = os.getenv(
    "ORDER_VOUCHER_FILE_PATH",
    str(PROJECT_ROOT / "testdata" / "order" / "payment_voucher_sample.jpg"),
).strip()
COMMODITY_LIST_API_URL = os.getenv(
    "COMMODITY_LIST_API_URL",
    "https://test-platform.ysbpack.com/api/product/commodity/getCommodityList",
)
COMMODITY_DETAIL_API_URL = os.getenv(
    "COMMODITY_DETAIL_API_URL",
    "https://test-platform.ysbpack.com/api/product/commodity/getCommodity",
)
COMMODITY_GUEST_LIST_API_URL = os.getenv(
    "COMMODITY_GUEST_LIST_API_URL",
    "https://test-platform.ysbpack.com/api/product/commodity/common/getCommodityListByGuest",
)
RECEIVER_ADDRESS_AGENT_PAGE_API_URL = os.getenv(
    "RECEIVER_ADDRESS_AGENT_PAGE_API_URL",
    "https://test-platform.ysbpack.com/api/logistics/receiverAddress/agent/page",
)
ORDER_SHOP_ID = int(os.getenv("ORDER_SHOP_ID", "1"))
ORDER_SOURCE_SHOP_TYPE = int(os.getenv("ORDER_SOURCE_SHOP_TYPE", "1"))
ORDER_RELATION_ID = int(os.getenv("ORDER_RELATION_ID", "1"))
ORDER_BUYER_ROLE_ID = int(os.getenv("ORDER_BUYER_ROLE_ID", "21"))
_order_buyer_user_id = os.getenv("ORDER_BUYER_USER_ID", "").strip()
ORDER_BUYER_USER_ID = int(_order_buyer_user_id) if _order_buyer_user_id else None
ORDER_FREIGHT_CARRIAGE_TYPE_2_AMOUNT = float(os.getenv("ORDER_FREIGHT_CARRIAGE_TYPE_2_AMOUNT", "50"))

# CRM regression recording session (UI actions + Network -> draft cases)
RECORDING_DIR = os.getenv(
    "RECORDING_DIR",
    str(PROJECT_ROOT / "recordings"),
).strip()
RECORDING_MIN_SCORE = int(os.getenv("RECORDING_MIN_SCORE", "30"))
RECORDING_MAX_MAIN_APIS = int(os.getenv("RECORDING_MAX_MAIN_APIS", "30"))
RECORDING_ALLOWED_HOSTS = {
    item.strip().lower()
    for item in os.getenv("RECORDING_ALLOWED_HOSTS", "").split(",")
    if item.strip()
}

# CRM Web / 录制回放导航（SPA 常用 commit，避免等满整个 domcontentloaded）
CRM_NAV_TIMEOUT_MS = int(os.getenv("CRM_NAV_TIMEOUT_MS", "120000"))
CRM_GOTO_WAIT_UNTIL = os.getenv("CRM_GOTO_WAIT_UNTIL", "commit").strip() or "commit"
CRM_GOTO_RETRIES = int(os.getenv("CRM_GOTO_RETRIES", "3"))
CRM_UI_PAUSE_ON_FAILURE = os.getenv("CRM_UI_PAUSE_ON_FAILURE", "false").lower() == "true"
# CRM UI 新建线索草稿默认项（空则打开下拉后点第一项）
CRM_UI_LEAD_SOURCE_TEXT = os.getenv("CRM_UI_LEAD_SOURCE_TEXT", "").strip()
# 销售线索 UI 冒烟（对齐录制 20260807-160515）
CRM_UI_LEAD_FOLLOW_KEYWORD = os.getenv(
    "CRM_UI_LEAD_FOLLOW_KEYWORD",
    os.getenv("CRM_UI_FOLLOW_USER_KEYWORD", "甜") or "甜",
).strip()
CRM_UI_LEAD_COMPANY_KEYWORD = os.getenv("CRM_UI_LEAD_COMPANY_KEYWORD", "白象").strip()
# 公司名称下拉中要点选的完整项（优先精确匹配；空则点选含关键字的第一项）
CRM_UI_LEAD_COMPANY_OPTION = os.getenv(
    "CRM_UI_LEAD_COMPANY_OPTION",
    "白象食品股份有限公司",
).strip()
CRM_UI_LEAD_QICHACHA_BACKFILL = (
    os.getenv("CRM_UI_LEAD_QICHACHA_BACKFILL", "true").lower() == "true"
)
# 来源=展会时展会名称关键字（空则点选下拉第一项）；默认复用接口造数 LEAD_EXHIBITION_NAME
CRM_UI_LEAD_EXHIBITION_KEYWORD = os.getenv(
    "CRM_UI_LEAD_EXHIBITION_KEYWORD",
    LEAD_EXHIBITION_NAME or "tinker",
).strip()
# 线索 UI：分配目标跟进人（必须与当前登录账号/原跟进人不同，否则会报「分配前后跟进人一致」）
CRM_UI_LEAD_ASSIGN_FOLLOW_KEYWORD = os.getenv(
    "CRM_UI_LEAD_ASSIGN_FOLLOW_KEYWORD",
    "tinker",
).strip()
# 活动记录 UI 冒烟（对齐录制 20260810-135954）
CRM_UI_ACTIVITY_FOLLOW_KEYWORD = os.getenv(
    "CRM_UI_ACTIVITY_FOLLOW_KEYWORD",
    os.getenv("CRM_UI_FOLLOW_USER_KEYWORD", "甜") or "甜",
).strip()
CRM_UI_ACTIVITY_CONTENT_KEYWORD = os.getenv(
    "CRM_UI_ACTIVITY_CONTENT_KEYWORD", "添加线下摆放"
).strip()
CRM_UI_ACTIVITY_TYPE_TEXT = os.getenv(
    "CRM_UI_ACTIVITY_TYPE_TEXT", "线下拜访"
).strip()
CRM_UI_ACTIVITY_CREATE_TIME_START = os.getenv(
    "CRM_UI_ACTIVITY_CREATE_TIME_START", "2026-05-27"
).strip()
CRM_UI_ACTIVITY_CREATE_TIME_END = os.getenv(
    "CRM_UI_ACTIVITY_CREATE_TIME_END",
    os.getenv("CRM_UI_ACTIVITY_CREATE_TIME_START", "2026-05-27"),
).strip()
# 跟进人搜索关键字；空字符串表示沿用页面默认「系统分配」
CRM_UI_FOLLOW_USER_KEYWORD = os.getenv("CRM_UI_FOLLOW_USER_KEYWORD", "").strip()
# 销售机会 UI 冒烟：关联客户关键字（需账号下已有该客户及联系人）
CRM_UI_OPPORTUNITY_CUSTOMER_KEYWORD = os.getenv(
    "CRM_UI_OPPORTUNITY_CUSTOMER_KEYWORD",
    "苏州市吴中区金庭金陵烧饼店",
).strip()
CRM_UI_OPPORTUNITY_AMOUNT = os.getenv("CRM_UI_OPPORTUNITY_AMOUNT", "1000").strip()
CRM_UI_OPPORTUNITY_PRODUCT_PRICE = os.getenv("CRM_UI_OPPORTUNITY_PRODUCT_PRICE", "11").strip()
CRM_UI_OPPORTUNITY_PRODUCT_COUNT = os.getenv("CRM_UI_OPPORTUNITY_PRODUCT_COUNT", "10").strip()
# 联系人 UI 冒烟：关联客户关键字（与录制一致）
CRM_UI_CONTACT_CUSTOMER_KEYWORD = os.getenv(
    "CRM_UI_CONTACT_CUSTOMER_KEYWORD",
    os.getenv("CRM_UI_OPPORTUNITY_CUSTOMER_KEYWORD", "苏州市吴中区金庭金陵烧饼店"),
).strip()
# 联系人列表筛选（对齐录制首次查询：来源=手动创建、注册状态=未注册、创建时间）
CRM_UI_CONTACT_SOURCE_TEXT = os.getenv("CRM_UI_CONTACT_SOURCE_TEXT", "手动创建").strip()
CRM_UI_CONTACT_REGISTER_STATUS_TEXT = os.getenv(
    "CRM_UI_CONTACT_REGISTER_STATUS_TEXT", "未注册"
).strip()
CRM_UI_CONTACT_CREATE_TIME_START = os.getenv(
    "CRM_UI_CONTACT_CREATE_TIME_START", "2026-07-03"
).strip()
CRM_UI_CONTACT_CREATE_TIME_END = os.getenv(
    "CRM_UI_CONTACT_CREATE_TIME_END", "2026-07-03"
).strip()
# 客户 UI 冒烟：国内走工商关键字；国外企业名用例内随机生成（不校验工商）
CRM_UI_CUSTOMER_COUNTRY = os.getenv("CRM_UI_CUSTOMER_COUNTRY", "美国").strip()
CRM_UI_CUSTOMER_FOLLOW_KEYWORD = os.getenv(
    "CRM_UI_CUSTOMER_FOLLOW_KEYWORD",
    os.getenv("CRM_UI_FOLLOW_USER_KEYWORD", "甜") or "甜",
).strip()
CRM_UI_CUSTOMER_COMPANY_EMAIL = os.getenv(
    "CRM_UI_CUSTOMER_COMPANY_EMAIL", "auto_customer@example.com"
).strip()
# 国内客户：工商信息查询关键字（输入后从下拉选一项）
CRM_UI_CUSTOMER_DOMESTIC_KEYWORD = os.getenv(
    "CRM_UI_CUSTOMER_DOMESTIC_KEYWORD",
    "苏州糖",
).strip()
# 国外/国内客户：经营类型级联（一级→二级，如 终端客户→品牌方）
CRM_UI_CUSTOMER_BUSINESS_TYPE_L1 = os.getenv(
    "CRM_UI_CUSTOMER_BUSINESS_TYPE_L1", "终端客户"
).strip()
CRM_UI_CUSTOMER_BUSINESS_TYPE_L2 = os.getenv(
    "CRM_UI_CUSTOMER_BUSINESS_TYPE_L2", "品牌方"
).strip()
# 国内客户：行业级联（一级→二级；默认食品行业→点右侧第一项）
CRM_UI_CUSTOMER_INDUSTRY_L1 = os.getenv(
    "CRM_UI_CUSTOMER_INDUSTRY_L1", "食品行业"
).strip()
CRM_UI_CUSTOMER_INDUSTRY_L2 = os.getenv(
    "CRM_UI_CUSTOMER_INDUSTRY_L2", ""
).strip()
# 国内地址 / 工商补充字段默认值（工商回填已有值则保留）
CRM_UI_CUSTOMER_PROVINCE = os.getenv("CRM_UI_CUSTOMER_PROVINCE", "江苏").strip()
CRM_UI_CUSTOMER_CITY = os.getenv("CRM_UI_CUSTOMER_CITY", "苏州").strip()
CRM_UI_CUSTOMER_DISTRICT = os.getenv("CRM_UI_CUSTOMER_DISTRICT", "姑苏区").strip()
CRM_UI_CUSTOMER_COMPANY_PHONE = os.getenv(
    "CRM_UI_CUSTOMER_COMPANY_PHONE", "0512-88888888"
).strip()
CRM_UI_CUSTOMER_PEOPLE_NUM = os.getenv("CRM_UI_CUSTOMER_PEOPLE_NUM", "100").strip()
CRM_UI_CUSTOMER_REGISTERED_CAPITAL = os.getenv(
    "CRM_UI_CUSTOMER_REGISTERED_CAPITAL", "1000"
).strip()
CRM_UI_CUSTOMER_ESTABLISHMENT_TIME = os.getenv(
    "CRM_UI_CUSTOMER_ESTABLISHMENT_TIME", "2020-01-01"
).strip()
CRM_UI_CUSTOMER_BUSINESS_SCOPE = os.getenv(
    "CRM_UI_CUSTOMER_BUSINESS_SCOPE", "自动化经营范围（测试）"
).strip()
CRM_UI_CUSTOMER_STANDARD_INDUSTRY = os.getenv(
    "CRM_UI_CUSTOMER_STANDARD_INDUSTRY", "商贸零售"
).strip()
CRM_UI_CUSTOMER_OFFICE_ADDRESS = os.getenv(
    "CRM_UI_CUSTOMER_OFFICE_ADDRESS", "自动化办公地址"
).strip()
# 国内新建非必填也维护
CRM_UI_CUSTOMER_COOPERATION_SUPPLIER = os.getenv(
    "CRM_UI_CUSTOMER_COOPERATION_SUPPLIER", "自动化合作供应商"
).strip()
CRM_UI_CUSTOMER_PREDICT_MARKET = os.getenv(
    "CRM_UI_CUSTOMER_PREDICT_MARKET", ""
).strip()
# 销售市场：国内为省份枚举（全国/上海/北京/江苏省…），不是国家
CRM_UI_CUSTOMER_SALES_MARKET = os.getenv(
    "CRM_UI_CUSTOMER_SALES_MARKET",
    CRM_UI_CUSTOMER_PREDICT_MARKET
    or (
        f"{CRM_UI_CUSTOMER_PROVINCE}省"
        if CRM_UI_CUSTOMER_PROVINCE and not CRM_UI_CUSTOMER_PROVINCE.endswith(
            ("省", "市", "区")
        )
        else (CRM_UI_CUSTOMER_PROVINCE or "江苏省")
    ),
).strip()
# 询盘信息
CRM_UI_CUSTOMER_INQUIRY_KEYWORD = os.getenv(
    "CRM_UI_CUSTOMER_INQUIRY_KEYWORD", "购买"
).strip()
CRM_UI_CUSTOMER_YEAR_PURCHASE_QTY = os.getenv(
    "CRM_UI_CUSTOMER_YEAR_PURCHASE_QTY", "100"
).strip()
CRM_UI_CUSTOMER_REQUIREMENT_CLARITY = os.getenv(
    "CRM_UI_CUSTOMER_REQUIREMENT_CLARITY", ""
).strip()
CRM_UI_CUSTOMER_REMARK = os.getenv(
    "CRM_UI_CUSTOMER_REMARK", "自动化备注"
).strip()
# 联系人职务 / 部门
CRM_UI_CUSTOMER_CONTACT_POSITION = os.getenv(
    "CRM_UI_CUSTOMER_CONTACT_POSITION", "采购员"
).strip()
CRM_UI_CUSTOMER_CONTACT_DEPARTMENT = os.getenv(
    "CRM_UI_CUSTOMER_CONTACT_DEPARTMENT", "采购部"
).strip()
# 国内工商选中后的完整公司名（用于清重 / 回滚；与关键字「苏州糖」对应）
CRM_UI_CUSTOMER_DOMESTIC_FULL_NAME = os.getenv(
    "CRM_UI_CUSTOMER_DOMESTIC_FULL_NAME",
    "苏州糖烟酒有限公司",
).strip()
# 客户查重 UI：有重复 / 无重复关键字（菜单进入查重页后查询）
CRM_UI_CUSTOMER_DUP_HIT_KEYWORD = os.getenv(
    "CRM_UI_CUSTOMER_DUP_HIT_KEYWORD",
    "",
).strip()
CRM_UI_CUSTOMER_DUP_MISS_KEYWORD = os.getenv(
    "CRM_UI_CUSTOMER_DUP_MISS_KEYWORD",
    "自动化查重无重复ZZZ999",
).strip()
# CRM 测试库（客户回滚 SQL）
CRM_DB_HOST = os.getenv("CRM_DB_HOST", "").strip()
CRM_DB_PORT = int(os.getenv("CRM_DB_PORT", "5432") or 5432)
CRM_DB_USER = os.getenv("CRM_DB_USER", "").strip()
CRM_DB_PASSWORD = os.getenv("CRM_DB_PASSWORD", "")
CRM_DB_DATABASE = os.getenv("CRM_DB_DATABASE", "").strip()
# 造数回滚：有 DB 配置时默认开启；可用 CRM_CUSTOMER_ROLLBACK_ENABLED 强制开关
_rollback_env = os.getenv("CRM_CUSTOMER_ROLLBACK_ENABLED", "").strip().lower()
if _rollback_env in {"true", "1", "yes"}:
    CRM_CUSTOMER_ROLLBACK_ENABLED = True
elif _rollback_env in {"false", "0", "no"}:
    CRM_CUSTOMER_ROLLBACK_ENABLED = False
else:
    CRM_CUSTOMER_ROLLBACK_ENABLED = bool(CRM_DB_HOST and CRM_DB_USER and CRM_DB_DATABASE)
# 可选覆盖整段回滚 SQL；空则用 utils/crm_data_rollback.py 内置模板（{name}）
CRM_CUSTOMER_ROLLBACK_SQL = os.getenv("CRM_CUSTOMER_ROLLBACK_SQL", "").strip()

# 询价单（录制会话 20260804-105954 / inquiry_main：客户详情 → 发起内部询价单）
CRM_INQUIRY_QUERY_API_URL = os.getenv(
    "CRM_INQUIRY_QUERY_API_URL",
    "https://test-platform.ysbpack.com/api/crm/customer/iqrMain/query",
)
CRM_INQUIRY_DETAIL_BY_SUB_API_URL = os.getenv(
    "CRM_INQUIRY_DETAIL_BY_SUB_API_URL",
    "https://test-platform.ysbpack.com/api/crm/customer/iqrMain/detailBySub",
)
CRM_INQUIRY_ADD_DRAFT_API_URL = os.getenv(
    "CRM_INQUIRY_ADD_DRAFT_API_URL",
    "https://test-platform.ysbpack.com/api/crm/customer/iqrMain/addDraft",
)
CRM_INQUIRY_SUBMIT_API_URL = os.getenv(
    "CRM_INQUIRY_SUBMIT_API_URL",
    "https://test-platform.ysbpack.com/api/crm/customer/iqrMain/submitOrUpdate",
)
# 中文商城-内部询价：创建中文询价单（transaction，无 sourceMallType）
CRM_INQUIRY_TX_SUBMIT_API_URL = os.getenv(
    "CRM_INQUIRY_TX_SUBMIT_API_URL",
    "https://test-platform.ysbpack.com/api/transaction/iqrMain/submitOrUpdate",
)
CRM_INQUIRY_TX_ADD_DRAFT_API_URL = os.getenv(
    "CRM_INQUIRY_TX_ADD_DRAFT_API_URL",
    "https://test-platform.ysbpack.com/api/transaction/iqrMain/addDraft",
)
# 英文商城-内部询价
CRM_INQUIRY_EN_SUBMIT_API_URL = os.getenv(
    "CRM_INQUIRY_EN_SUBMIT_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/transaction/iqrMain/en/submitOrUpdate",
)
CRM_INQUIRY_EN_ADD_DRAFT_API_URL = os.getenv(
    "CRM_INQUIRY_EN_ADD_DRAFT_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/transaction/iqrMain/en/addDraft",
)
CRM_INQUIRY_EN_SUBMIT_TECH_API_URL = os.getenv(
    "CRM_INQUIRY_EN_SUBMIT_TECH_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/transaction/iqrMain/en/submitTechProgram",
)
CRM_INQUIRY_EN_PUSH_SUPPLIER_API_URL = os.getenv(
    "CRM_INQUIRY_EN_PUSH_SUPPLIER_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/transaction/iqrSupplier/platform/pushSupplier",
)
CRM_INQUIRY_EN_OFFLINE_QUOTE_API_URL = os.getenv(
    "CRM_INQUIRY_EN_OFFLINE_QUOTE_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/transaction/iqrOfflineQuote/platform/save",
)
CRM_INQUIRY_EN_OFFLINE_ADOPT_API_URL = os.getenv(
    "CRM_INQUIRY_EN_OFFLINE_ADOPT_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/transaction/iqrOfflineQuote/platform/adopt",
)
CRM_INQUIRY_EN_ADOPT_QUOTE_API_URL = os.getenv(
    "CRM_INQUIRY_EN_ADOPT_QUOTE_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/transaction/iqrSupplier/platform/adopt",
)
CRM_INQUIRY_EN_RECORDS_BY_SUB_API_URL = os.getenv(
    "CRM_INQUIRY_EN_RECORDS_BY_SUB_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/transaction/iqrSupplier/platform/recordsBySub",
)
CRM_INQUIRY_EN_SUBMIT_FACTORY_API_URL = os.getenv(
    "CRM_INQUIRY_EN_SUBMIT_FACTORY_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/transaction/iqrMain/en/submitFactoryPrice",
)
CRM_INQUIRY_EN_SUBMIT_PLATFORM_API_URL = os.getenv(
    "CRM_INQUIRY_EN_SUBMIT_PLATFORM_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/transaction/iqrMain/en/submitPlatformPrice",
)
CRM_INQUIRY_EN_CONFIRM_PRICE_API_URL = os.getenv(
    "CRM_INQUIRY_EN_CONFIRM_PRICE_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/transaction/iqrMain/en/confirmPrice",
)
CRM_INQUIRY_EN_RELATION_PRODUCT_API_URL = os.getenv(
    "CRM_INQUIRY_EN_RELATION_PRODUCT_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/transaction/iqrMain/en/relationProduct",
)
CRM_INQUIRY_EN_SUBMIT_CUSTOM_ORDER_API_URL = os.getenv(
    "CRM_INQUIRY_EN_SUBMIT_CUSTOM_ORDER_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/transaction/iqrMain/en/submitCustomOrder",
)
CRM_INQUIRY_EN_RELATION_SKU_IDS = [
    int(item.strip())
    for item in os.getenv("CRM_INQUIRY_EN_RELATION_SKU_IDS", "105212").split(",")
    if item.strip()
]
# 中文商城关联 SKU（写在 .env.cn.*；后续中文流转用）
CRM_INQUIRY_RELATION_SKU_IDS = [
    int(item.strip())
    for item in os.getenv("CRM_INQUIRY_RELATION_SKU_IDS", "").split(",")
    if item.strip()
]
EPAK_ORDER_AGENT_CREATE_API_URL = os.getenv(
    "EPAK_ORDER_AGENT_CREATE_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/order/vendor/create/agent/order",
)
EPAK_COMMODITY_GUEST_LIST_API_URL = os.getenv(
    "EPAK_COMMODITY_GUEST_LIST_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/product/commodity/common/getCommodityListByGuest",
)
EPAK_RECEIVER_ADDRESS_AGENT_PAGE_API_URL = os.getenv(
    "EPAK_RECEIVER_ADDRESS_AGENT_PAGE_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/logistics/receiverAddress/agent/page",
)
CRM_INQUIRY_EN_ORDER_CURRENCY_ID = int(os.getenv("CRM_INQUIRY_EN_ORDER_CURRENCY_ID", "3"))
CRM_INQUIRY_EN_ORDER_TRADE_MODE = int(os.getenv("CRM_INQUIRY_EN_ORDER_TRADE_MODE", "4"))
CRM_INQUIRY_EN_ORDER_SHOP_NAME = os.getenv(
    "CRM_INQUIRY_EN_ORDER_SHOP_NAME",
    "Food Pack Mall-web",
).strip()
CRM_INQUIRY_EN_ORDER_SHOP_CLASSIFY = int(
    os.getenv("CRM_INQUIRY_EN_ORDER_SHOP_CLASSIFY", "2")
)
CRM_INQUIRY_EN_SUPPLIER_QUERY_API_URL = os.getenv(
    "CRM_INQUIRY_EN_SUPPLIER_QUERY_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/transaction/iqrSupplier/platform/page",
)
CRM_INQUIRY_CN_SUPPLIER_QUOTE_API_URL = os.getenv(
    "CRM_INQUIRY_CN_SUPPLIER_QUOTE_API_URL",
    f"{CRM_INQUIRY_SUPPLIER_PLATFORM_BASE_URL}/api/transaction/iqrSupplier/platform/submitQuote",
)
CRM_INQUIRY_CN_SUPPLIER_QUERY_API_URL = os.getenv(
    "CRM_INQUIRY_CN_SUPPLIER_QUERY_API_URL",
    f"{CRM_INQUIRY_SUPPLIER_PLATFORM_BASE_URL}/api/transaction/iqrSupplier/platform/page",
)
CRM_INQUIRY_EN_QUERY_API_URL = os.getenv(
    "CRM_INQUIRY_EN_QUERY_API_URL",
    f"{EPAK_PLATFORM_BASE_URL}/api/transaction/iqrMain/en/pageList",
).strip()
CRM_INQUIRY_CUSTOMER_BRIEF_API_URL = os.getenv(
    "CRM_INQUIRY_CUSTOMER_BRIEF_API_URL",
    "https://test-platform.ysbpack.com/api/crm/customer/getCustomerBriefForIqr",
)
CRM_INQUIRY_REFERER = os.getenv(
    "CRM_INQUIRY_REFERER",
    "/memberCenter/crm2Ability/customer",
)
CRM_INQUIRY_SOURCE_MALL_TYPE = int(os.getenv("CRM_INQUIRY_SOURCE_MALL_TYPE", "1"))
# 客户详情询价 Tab 查询：CRM 客户 id + 商城会员 id（录制样本）
CRM_INQUIRY_CUSTOMER_ID = int(os.getenv("CRM_INQUIRY_CUSTOMER_ID", "1036"))
CRM_INQUIRY_BUYER_MEMBER_ID = int(os.getenv("CRM_INQUIRY_BUYER_MEMBER_ID", "104450"))
CRM_INQUIRY_BUYER_MEMBER_NAME = os.getenv(
    "CRM_INQUIRY_BUYER_MEMBER_NAME", "北京郑州企业商会"
).strip()
CRM_INQUIRY_BUYER_USER_ID = int(os.getenv("CRM_INQUIRY_BUYER_USER_ID", "104632"))
CRM_INQUIRY_BUYER_USER_NAME = os.getenv(
    "CRM_INQUIRY_BUYER_USER_NAME",
    CRM_INQUIRY_BUYER_MEMBER_NAME,
).strip()
CRM_INQUIRY_BUYER_SALE_ORG_TYPE = int(os.getenv("CRM_INQUIRY_BUYER_SALE_ORG_TYPE", "5"))
CRM_INQUIRY_CATEGORY_FULL_ID = os.getenv(
    "CRM_INQUIRY_CATEGORY_FULL_ID",
    "00100803.00100804.00100805.00100806",
).strip()
# UI：客户列表关键字（与录制一致）
CRM_UI_INQUIRY_CUSTOMER_KEYWORD = os.getenv(
    "CRM_UI_INQUIRY_CUSTOMER_KEYWORD",
    CRM_INQUIRY_BUYER_MEMBER_NAME,
).strip()
# 询价按状态造数：目标状态可用中文名 / 枚举名 / 状态码（14=新建草稿, 2=待提交技术方案…）
CRM_INQUIRY_TARGET_STATUS = os.getenv(
    "CRM_INQUIRY_TARGET_STATUS",
    "待提交技术方案",
).strip()
CRM_INQUIRY_SEED_STATUSES = os.getenv("CRM_INQUIRY_SEED_STATUSES", "").strip()
# 创建入口：crm_customer=CRM客户详情；internal=交易能力/内部询价单
CRM_INQUIRY_CREATE_SOURCE = os.getenv("CRM_INQUIRY_CREATE_SOURCE", "crm_customer").strip()
# 英文询价单操作站点：en=英文站（默认）；cn=中文站操作英文单（CRM + sourceMallType=2）
CRM_INQUIRY_OPERATE_VIA = os.getenv("CRM_INQUIRY_OPERATE_VIA", "en").strip()
# 操作商城：cn=中文商城；en=英文商城
CRM_INQUIRY_MALL = os.getenv("CRM_INQUIRY_MALL", "cn").strip()
# 询价单语种：cn/en；空则中文商城默认中文单、英文商城默认英文单
CRM_INQUIRY_FORM = os.getenv("CRM_INQUIRY_FORM", "").strip()
# 子单类型：1/通用品；2/定制品（流转节点不同）
CRM_INQUIRY_ASK_PRICE_TYPE = os.getenv("CRM_INQUIRY_ASK_PRICE_TYPE", "定制品").strip()
# 多子单：JSON 数组，如 [{"ask_price_type":"定制品"},{"ask_price_type":"通用品","target_status":"待出厂报价"}]
CRM_INQUIRY_SUBS_JSON = os.getenv("CRM_INQUIRY_SUBS_JSON", "").strip()
CRM_INQUIRY_EN_BUYER_MEMBER_ID = int(os.getenv("CRM_INQUIRY_EN_BUYER_MEMBER_ID", "569"))
CRM_INQUIRY_EN_BUYER_MEMBER_NAME = os.getenv(
    "CRM_INQUIRY_EN_BUYER_MEMBER_NAME",
    "CURSOR注册客户8650",
).strip()
CRM_INQUIRY_EN_BUYER_USER_ID = int(os.getenv("CRM_INQUIRY_EN_BUYER_USER_ID", "101926"))
CRM_INQUIRY_EN_BUYER_USER_NAME = os.getenv(
    "CRM_INQUIRY_EN_BUYER_USER_NAME",
    CRM_INQUIRY_EN_BUYER_MEMBER_NAME,
).strip()
CRM_INQUIRY_EN_CATEGORY_FULL_ID = os.getenv(
    "CRM_INQUIRY_EN_CATEGORY_FULL_ID",
    "00100101.00100102.00100252.00100253",
).strip()
CRM_INQUIRY_TECH_ACCOUNT = os.getenv("CRM_INQUIRY_TECH_ACCOUNT", "").strip()
CRM_INQUIRY_TECH_PASSWORD_ENCRYPTED = os.getenv(
    "CRM_INQUIRY_TECH_PASSWORD_ENCRYPTED",
    "",
).strip() or LOGIN_PASSWORD_ENCRYPTED
# 英文商城技术经理（auth.epakgroup.cn）
EPAK_INQUIRY_TECH_ACCOUNT = os.getenv("EPAK_INQUIRY_TECH_ACCOUNT", "13143409929").strip()
EPAK_INQUIRY_TECH_PASSWORD_ENCRYPTED = os.getenv(
    "EPAK_INQUIRY_TECH_PASSWORD_ENCRYPTED",
    "QYA3znjH9+0ski/+mT/izA==",
).strip()
CRM_INQUIRY_EN_TECH_PROGRAM = os.getenv(
    "CRM_INQUIRY_EN_TECH_PROGRAM",
    "自动化提交技术方案",
).strip()
CRM_INQUIRY_EN_TECH_FILE_NAME = os.getenv(
    "CRM_INQUIRY_EN_TECH_FILE_NAME",
    "财富猫.jpg",
).strip()
CRM_INQUIRY_EN_TECH_FILE_URL = os.getenv(
    "CRM_INQUIRY_EN_TECH_FILE_URL",
    "https://aliyunosscdn.epakgroup.com/FILENAMEFIXED22987323b73a4a08b13f737accfeea15.jpg",
).strip()
# 英文商城采购员（auth.epakgroup.cn，雷翰；出厂报价）
EPAK_INQUIRY_PURCHASER_ACCOUNT = os.getenv(
    "EPAK_INQUIRY_PURCHASER_ACCOUNT", "15346087993"
).strip()
EPAK_INQUIRY_PURCHASER_PASSWORD_ENCRYPTED = os.getenv(
    "EPAK_INQUIRY_PURCHASER_PASSWORD_ENCRYPTED",
    "QYA3znjH9+0ski/+mT/izA==",
).strip()
# 英文商城业务支撑（auth.epakgroup.cn，张四；平台报价）
EPAK_INQUIRY_SUPPORT_ACCOUNT = os.getenv(
    "EPAK_INQUIRY_SUPPORT_ACCOUNT", "18373383111"
).strip()
EPAK_INQUIRY_SUPPORT_PASSWORD_ENCRYPTED = os.getenv(
    "EPAK_INQUIRY_SUPPORT_PASSWORD_ENCRYPTED",
    "QYA3znjH9+0ski/+mT/izA==",
).strip()
CRM_INQUIRY_SUPPLIER_ACCOUNT = os.getenv("CRM_INQUIRY_SUPPLIER_ACCOUNT", "17751104143").strip()
CRM_INQUIRY_SUPPLIER_PASSWORD_ENCRYPTED = os.getenv(
    "CRM_INQUIRY_SUPPLIER_PASSWORD_ENCRYPTED",
    "QYA3znjH9+0ski/+mT/izA==",
).strip()
EPAK_INQUIRY_SUPPLIER_MEMBER_ID = int(os.getenv("EPAK_INQUIRY_SUPPLIER_MEMBER_ID", "1547"))
EPAK_INQUIRY_SUPPLIER_MEMBER_NAME = os.getenv(
    "EPAK_INQUIRY_SUPPLIER_MEMBER_NAME",
    "杭州珀莱雅商业经营管理有限公司",
).strip()
CRM_INQUIRY_SUPPLIER_MEMBER_ID = int(os.getenv("CRM_INQUIRY_SUPPLIER_MEMBER_ID", "104391"))
CRM_INQUIRY_SUPPLIER_MEMBER_NAME = os.getenv(
    "CRM_INQUIRY_SUPPLIER_MEMBER_NAME",
    EPAK_INQUIRY_SUPPLIER_MEMBER_NAME,
).strip()
# online,offline / both；默认同时造线上询价 + 线下报价
CRM_INQUIRY_EN_QUOTE_CHANNELS = os.getenv(
    "CRM_INQUIRY_EN_QUOTE_CHANNELS", "both"
).strip()
# 线下报价包装：1纸箱 2卷类 3其他；是否打托：1是 0否
CRM_INQUIRY_EN_OFFLINE_PACKAGING_TYPE = int(
    os.getenv("CRM_INQUIRY_EN_OFFLINE_PACKAGING_TYPE", "1")
)
CRM_INQUIRY_EN_OFFLINE_IS_PALLET = int(
    os.getenv("CRM_INQUIRY_EN_OFFLINE_IS_PALLET", "1")
)
# 出厂报价采纳来源：online / offline / auto
# both 时 auto=offline（submitFactoryPrice 带上线下包装字段，与手工采纳线下一致）
CRM_INQUIRY_EN_FACTORY_ADOPT_SOURCE = os.getenv(
    "CRM_INQUIRY_EN_FACTORY_ADOPT_SOURCE", "auto"
).strip()
CRM_INQUIRY_EN_FACTORY_CITY = os.getenv(
    "CRM_INQUIRY_EN_FACTORY_CITY",
    "伯明翰",
).strip()
CRM_INQUIRY_EN_COMPARE_PRICE_REMARK = os.getenv(
    "CRM_INQUIRY_EN_COMPARE_PRICE_REMARK",
    "自动化比价小结",
).strip()
CRM_INQUIRY_EN_PLATFORM_UNIT_PRICE = float(
    os.getenv("CRM_INQUIRY_EN_PLATFORM_UNIT_PRICE", "10")
)
CRM_INQUIRY_EN_PLATFORM_PRICE_TYPE = os.getenv(
    "CRM_INQUIRY_EN_PLATFORM_PRICE_TYPE",
    "含税不含运",
).strip()
CRM_INQUIRY_EN_PLATFORM_DESC = os.getenv(
    "CRM_INQUIRY_EN_PLATFORM_DESC",
    "自动化平台报价备注",
).strip()
CRM_INQUIRY_PURCHASER_ACCOUNT = os.getenv("CRM_INQUIRY_PURCHASER_ACCOUNT", "").strip()
CRM_INQUIRY_PURCHASER_PASSWORD_ENCRYPTED = os.getenv(
    "CRM_INQUIRY_PURCHASER_PASSWORD_ENCRYPTED",
    "",
).strip() or LOGIN_PASSWORD_ENCRYPTED
CRM_INQUIRY_SUPPORT_ACCOUNT = os.getenv("CRM_INQUIRY_SUPPORT_ACCOUNT", "").strip()
CRM_INQUIRY_SUPPORT_PASSWORD_ENCRYPTED = os.getenv(
    "CRM_INQUIRY_SUPPORT_PASSWORD_ENCRYPTED",
    "",
).strip() or LOGIN_PASSWORD_ENCRYPTED
