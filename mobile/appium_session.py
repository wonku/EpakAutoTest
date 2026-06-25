from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.webdriver import WebDriver

from config import settings
from mobile.adb import AdbClient
from mobile.apk import ApkError, resolve_package_name


class AppiumSessionError(RuntimeError):
    """Raised when an Appium session cannot be created."""


@dataclass(frozen=True)
class AppiumSessionConfig:
    server_url: str
    apk_path: Path
    package_name: str
    app_activity: str
    device_serial: str
    adb_path: str
    no_reset: bool

    @classmethod
    def from_settings(cls) -> "AppiumSessionConfig":
        return cls(
            server_url=settings.APPIUM_SERVER_URL,
            apk_path=Path(settings.MOBILE_APK_PATH),
            package_name=settings.MOBILE_PACKAGE_NAME,
            app_activity=settings.APPIUM_APP_ACTIVITY,
            device_serial=settings.MOBILE_DEVICE_SERIAL,
            adb_path=settings.MOBILE_ADB_PATH,
            no_reset=settings.APPIUM_NO_RESET,
        )


def create_android_driver(config: AppiumSessionConfig) -> WebDriver:
    adb = AdbClient(config.adb_path, config.device_serial)
    adb.ensure_available()
    device_serial = adb.require_device()

    package_name = config.package_name or _resolve_package_name(config.apk_path, adb)
    app_activity = config.app_activity or _resolve_main_activity(adb, package_name)

    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"
    options.device_name = device_serial
    options.udid = device_serial
    options.app_package = package_name
    options.app_activity = app_activity
    options.no_reset = config.no_reset
    options.new_command_timeout = settings.APPIUM_NEW_COMMAND_TIMEOUT
    options.set_capability("autoGrantPermissions", True)
    options.set_capability("disableWindowAnimation", True)

    try:
        driver = webdriver.Remote(config.server_url, options=options)
    except Exception as exc:
        raise AppiumSessionError(
            f"failed to create Appium session at {config.server_url}. "
            "Ensure Appium server is running with UiAutomator2 driver installed."
        ) from exc

    driver.implicitly_wait(settings.APPIUM_IMPLICIT_WAIT_SECONDS)
    return driver


def _resolve_package_name(apk_path: Path, adb: AdbClient) -> str:
    if apk_path.exists():
        try:
            return resolve_package_name(apk_path)
        except ApkError:
            pass

    output = adb.shell(["cmd", "package", "resolve-activity", "--brief", "com.esbao.englishmobile"], check=False).stdout
    for line in output.splitlines():
        line = line.strip()
        if "/" in line and not line.startswith("priority"):
            return line.split("/", 1)[0]
    raise AppiumSessionError("package name not found; set MOBILE_PACKAGE_NAME in .env")


def _resolve_main_activity(adb: AdbClient, package_name: str) -> str:
    output = adb.shell(["cmd", "package", "resolve-activity", "--brief", package_name], check=False).stdout.strip()
    for line in output.splitlines():
        line = line.strip()
        if "/" in line and not line.startswith("priority"):
            _, activity = line.split("/", 1)
            return activity
    raise AppiumSessionError(f"main activity not found for package {package_name}")
