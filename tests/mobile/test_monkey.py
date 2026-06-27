from pathlib import Path

import allure
import pytest

from mobile.adb import AdbError
from mobile.apk import ApkError
from mobile.monkey import MonkeyConfig, run_monkey


@pytest.mark.mobile
@pytest.mark.monkey
def test_android_monkey_stability():
    config = MonkeyConfig.from_settings()
    if not Path(config.apk_path).exists():
        pytest.skip(f"APK not found: {config.apk_path}")

    try:
        result = run_monkey(config)
    except AdbError as exc:
        pytest.skip(str(exc))
    except ApkError as exc:
        pytest.fail(f"Failed to read package name from APK. Set MOBILE_PACKAGE_NAME manually. {exc}")

    allure.dynamic.title(f"Android Monkey stability: {result.package_name}")
    allure.dynamic.description(
        f"device={result.device_serial}, events={config.event_count}, throttle={config.throttle_ms}ms"
    )
    allure.attach.file(str(result.device_info_path), name="device-info", attachment_type=allure.attachment_type.TEXT)
    allure.attach.file(str(result.monkey_log_path), name="monkey-log", attachment_type=allure.attachment_type.TEXT)
    allure.attach.file(str(result.logcat_path), name="logcat", attachment_type=allure.attachment_type.TEXT)
    allure.attach.file(
        str(result.inspection_summary_path),
        name="inspection-summary",
        attachment_type=allure.attachment_type.JSON,
    )
    for index, screenshot_path in enumerate(result.issue_screenshot_paths, start=1):
        allure.attach.file(
            str(screenshot_path),
            name=f"issue-screenshot-{index}",
            attachment_type=allure.attachment_type.PNG,
        )
    if not result.issue_screenshot_paths and result.screenshot_paths:
        allure.attach.file(
            str(result.screenshot_paths[-1]),
            name="final-screenshot",
            attachment_type=allure.attachment_type.PNG,
        )

    assert result.returncode == 0, f"Monkey exited with {result.returncode}. See {result.monkey_log_path}"
    if config.fail_on_crash:
        assert not result.has_crash_or_anr, f"Monkey found crash or ANR. See {result.monkey_log_path}"
    if config.fail_on_inspection_issue:
        assert not result.has_inspection_issues, (
            f"Monkey inspection found app issue. See {result.inspection_summary_path}"
        )
