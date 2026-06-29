import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
AUTH_API_URL = os.getenv("AUTH_API_URL", "https://test-auth.ysbpack.com/api/member/login")
APP_HOME_URL = os.getenv("APP_HOME_URL", "https://test-platform.ysbpack.com/")
AUTH_ENVIRONMENT = os.getenv("AUTH_ENVIRONMENT", "1")
AUTH_SITE = os.getenv("AUTH_SITE", "1")
AUTH_SOURCE = os.getenv("AUTH_SOURCE", "1")
API_TIMEOUT_SECONDS = int(os.getenv("API_TIMEOUT_SECONDS", "30"))
PLATFORM_BASE_URL = os.getenv("PLATFORM_BASE_URL", "https://test-platform.ysbpack.com")
CRM_LEAD_SAVE_API_URL = os.getenv(
    "CRM_LEAD_SAVE_API_URL", "https://test-platform.ysbpack.com/api/crm/lead/saveOrUpdate"
)
CRM_LEAD_PAGE_API_URL = os.getenv("CRM_LEAD_PAGE_API_URL", "https://test-platform.ysbpack.com/api/crm/lead/page")
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
EPAK_UI_REPORT_DIR = os.getenv(
    "EPAK_UI_REPORT_DIR",
    str(PROJECT_ROOT / "reports" / "ui" / "epak"),
).strip()
EPAK_UI_PRODUCT_KEYWORD = os.getenv("EPAK_UI_PRODUCT_KEYWORD", "Slant Spout").strip()
