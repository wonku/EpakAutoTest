from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from config import settings
from mobile.adb import AdbClient
from mobile.apk import ApkError, resolve_package_name
from mobile.login import run_mobile_login


@dataclass(frozen=True)
class MonkeyConfig:
    apk_path: Path
    package_name: str
    install_apk: bool
    event_count: int
    throttle_ms: int
    seed: str
    extra_args: list[str]
    fail_on_crash: bool
    report_dir: Path
    adb_path: str
    device_serial: str
    keep_wifi_enabled: bool
    login_enabled: bool
    login_data_path: Path
    chunk_event_count: int
    screenshot_enabled: bool
    white_screen_enabled: bool
    white_screen_brightness_threshold: int
    white_screen_ratio: float
    error_text_keywords: list[str]
    fail_on_inspection_issue: bool

    @classmethod
    def from_settings(cls) -> "MonkeyConfig":
        return cls(
            apk_path=Path(settings.MOBILE_APK_PATH),
            package_name=settings.MOBILE_PACKAGE_NAME,
            install_apk=settings.MOBILE_INSTALL_APK,
            event_count=settings.MONKEY_EVENT_COUNT,
            throttle_ms=settings.MONKEY_THROTTLE_MS,
            seed=settings.MONKEY_SEED,
            extra_args=shlex.split(settings.MONKEY_EXTRA_ARGS),
            fail_on_crash=settings.MONKEY_FAIL_ON_CRASH,
            report_dir=Path(settings.MONKEY_REPORT_DIR),
            adb_path=settings.MOBILE_ADB_PATH,
            device_serial=settings.MOBILE_DEVICE_SERIAL,
            keep_wifi_enabled=settings.MONKEY_KEEP_WIFI_ENABLED,
            login_enabled=settings.MOBILE_LOGIN_ENABLED,
            login_data_path=Path(settings.MOBILE_LOGIN_DATA_PATH),
            chunk_event_count=settings.MONKEY_CHUNK_EVENT_COUNT,
            screenshot_enabled=settings.MONKEY_SCREENSHOT_ENABLED,
            white_screen_enabled=settings.MONKEY_WHITE_SCREEN_ENABLED,
            white_screen_brightness_threshold=settings.MONKEY_WHITE_SCREEN_BRIGHTNESS_THRESHOLD,
            white_screen_ratio=settings.MONKEY_WHITE_SCREEN_RATIO,
            error_text_keywords=settings.MONKEY_ERROR_TEXT_KEYWORDS,
            fail_on_inspection_issue=settings.MONKEY_FAIL_ON_INSPECTION_ISSUE,
        )


@dataclass(frozen=True)
class MonkeyResult:
    package_name: str
    device_serial: str
    returncode: int
    monkey_log_path: Path
    logcat_path: Path
    device_info_path: Path
    inspection_summary_path: Path
    screenshot_paths: list[Path]
    issue_screenshot_paths: list[Path]
    inspection_issues: list[dict]
    stdout: str
    stderr: str

    @property
    def has_crash_or_anr(self) -> bool:
        combined = f"{self.stdout}\n{self.stderr}"
        indicators = ("CRASH:", "ANR in ", "NOT RESPONDING", "Process crashed")
        return any(indicator in combined for indicator in indicators)

    @property
    def has_inspection_issues(self) -> bool:
        return bool(self.inspection_issues)


def run_monkey(config: MonkeyConfig) -> MonkeyResult:
    if config.event_count <= 0:
        raise ValueError("MONKEY_EVENT_COUNT must be greater than 0")
    if config.throttle_ms < 0:
        raise ValueError("MONKEY_THROTTLE_MS must be greater than or equal to 0")
    if not config.apk_path.exists():
        raise FileNotFoundError(f"APK not found: {config.apk_path}")

    adb = AdbClient(config.adb_path, config.device_serial)
    adb.ensure_available()
    device_serial = adb.require_device()

    package_name = config.package_name
    packages_before_install: set[str] = set()
    if not package_name and config.install_apk:
        packages_before_install = adb.package_names()

    if config.install_apk:
        adb.install(config.apk_path)

    if not package_name:
        package_name = _resolve_package_name(config.apk_path, adb, packages_before_install)

    if config.keep_wifi_enabled:
        _enable_wifi_best_effort(adb)

    if config.login_enabled:
        run_mobile_login(adb, package_name, config.login_data_path)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = config.report_dir / timestamp
    report_dir.mkdir(parents=True, exist_ok=True)

    device_info_path = report_dir / "device-info.txt"
    monkey_log_path = report_dir / "monkey.log"
    logcat_path = report_dir / "logcat.txt"
    inspection_summary_path = report_dir / "inspection-summary.json"
    screenshots_dir = report_dir / "screenshots"

    device_info_path.write_text(adb.device_info(), encoding="utf-8")

    adb.clear_logcat()
    command_base = [
        "monkey",
        "-p",
        package_name,
        "--throttle",
        str(config.throttle_ms),
    ]
    if config.seed:
        command_base.extend(["-s", str(config.seed)])
    command_base.extend(config.extra_args)
    command_base.extend(["-v", "-v"])

    screenshot_paths: list[Path] = []
    issue_screenshot_paths: list[Path] = []
    inspection_issues: list[dict] = []
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    returncode = 0

    remaining_events = config.event_count
    chunk_event_count = config.chunk_event_count if config.chunk_event_count > 0 else config.event_count
    chunk_index = 0
    while remaining_events > 0:
        chunk_index += 1
        current_events = min(chunk_event_count, remaining_events)
        command = [*command_base, str(current_events)]
        timeout = max(120, int(current_events * max(config.throttle_ms, 1) / 1000) + 180)
        monkey = adb.shell(command, timeout=timeout, check=False)
        stdout_parts.append(f"\n===== chunk {chunk_index} stdout =====\n{monkey.stdout}")
        stderr_parts.append(f"\n===== chunk {chunk_index} stderr =====\n{monkey.stderr}")
        returncode = monkey.returncode if monkey.returncode != 0 else returncode
        remaining_events -= current_events

        screenshot_path = None
        if config.screenshot_enabled:
            screenshot_path = screenshots_dir / f"chunk-{chunk_index:03d}.png"
            try:
                adb.screenshot(screenshot_path)
                screenshot_paths.append(screenshot_path)
            except Exception as exc:
                inspection_issues.append(
                    {
                        "type": "screenshot_failed",
                        "chunk": chunk_index,
                        "message": str(exc),
                    }
                )

        chunk_issues = _inspect_app_state(adb, config, screenshot_path, chunk_index)
        inspection_issues.extend(chunk_issues)
        if chunk_issues and screenshot_path:
            issue_screenshot_paths.append(screenshot_path)

        if monkey.returncode != 0 or chunk_issues:
            break

    if config.keep_wifi_enabled:
        _enable_wifi_best_effort(adb)

    stdout = "\n".join(stdout_parts)
    stderr = "\n".join(stderr_parts)
    monkey_log_path.write_text(
        "command: adb shell " + " ".join([*command_base, str(config.event_count)]) + "\n\n"
        f"returncode: {returncode}\n\n"
        f"chunk_event_count: {chunk_event_count}\n\n"
        "stdout:\n" + stdout + "\n\nstderr:\n" + stderr,
        encoding="utf-8",
    )

    logcat_path.write_text(adb.dump_logcat(), encoding="utf-8")
    inspection_summary = {
        "package_name": package_name,
        "device_serial": device_serial,
        "event_count_requested": config.event_count,
        "chunk_event_count": chunk_event_count,
        "screenshots": [str(path) for path in screenshot_paths],
        "issue_screenshots": [str(path) for path in issue_screenshot_paths],
        "issues": inspection_issues,
    }
    inspection_summary_path.write_text(
        json.dumps(inspection_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return MonkeyResult(
        package_name=package_name,
        device_serial=device_serial,
        returncode=returncode,
        monkey_log_path=monkey_log_path,
        logcat_path=logcat_path,
        device_info_path=device_info_path,
        inspection_summary_path=inspection_summary_path,
        screenshot_paths=screenshot_paths,
        issue_screenshot_paths=issue_screenshot_paths,
        inspection_issues=inspection_issues,
        stdout=stdout,
        stderr=stderr,
    )


def _inspect_app_state(
    adb: AdbClient,
    config: MonkeyConfig,
    screenshot_path: Path | None,
    chunk_index: int,
) -> list[dict]:
    issues: list[dict] = []
    if config.white_screen_enabled and screenshot_path and _is_white_screen(
        screenshot_path,
        config.white_screen_brightness_threshold,
        config.white_screen_ratio,
    ):
        issues.append(
            {
                "type": "white_screen",
                "chunk": chunk_index,
                "screenshot": str(screenshot_path),
                "message": "screen is mostly white",
            }
        )

    xml_text = adb.dump_ui_xml()
    for keyword in config.error_text_keywords:
        if keyword and keyword in xml_text:
            issues.append(
                {
                    "type": "error_text",
                    "chunk": chunk_index,
                    "keyword": keyword,
                    "screenshot": str(screenshot_path) if screenshot_path else "",
                    "message": f"found error keyword in UI: {keyword}",
                }
            )
    return issues


def _is_white_screen(screenshot_path: Path, brightness_threshold: int, white_ratio_threshold: float) -> bool:
    image = cv2.imread(str(screenshot_path))
    if image is None:
        return False
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    white_ratio = float(np.mean(gray >= brightness_threshold))
    return white_ratio >= white_ratio_threshold


def _enable_wifi_best_effort(adb: AdbClient) -> None:
    # Some devices block these commands, so WiFi enforcement should not fail the test itself.
    adb.shell(["svc", "wifi", "enable"], timeout=15, check=False)
    adb.shell(["cmd", "wifi", "set-wifi-enabled", "enabled"], timeout=15, check=False)


def _resolve_package_name(apk_path: Path, adb: AdbClient, packages_before_install: set[str]) -> str:
    try:
        return resolve_package_name(apk_path)
    except ApkError:
        packages_after_install = adb.package_names()
        new_packages = sorted(packages_after_install - packages_before_install)
        if len(new_packages) == 1:
            return new_packages[0]
        raise
