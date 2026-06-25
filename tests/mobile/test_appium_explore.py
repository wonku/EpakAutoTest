from pathlib import Path

import allure
import pytest

from mobile.adb import AdbError
from mobile.appium_session import AppiumSessionError
from mobile.explorer import ExploreConfig, run_appium_explore
from mobile.login import MobileLoginError


@pytest.mark.mobile
@pytest.mark.appium
def test_android_appium_random_explore():
    config = ExploreConfig.from_settings()
    apk_exists = Path(config.appium.apk_path).exists()
    if not apk_exists and not config.appium.package_name:
        pytest.skip(
            f"APK not found: {config.appium.apk_path} and MOBILE_PACKAGE_NAME is not set"
        )

    try:
        result = run_appium_explore(config)
    except AppiumSessionError as exc:
        pytest.skip(str(exc))
    except AdbError as exc:
        pytest.skip(str(exc))
    except MobileLoginError as exc:
        pytest.fail(f"Mobile login failed before Appium explore: {exc}")

    allure.dynamic.title(f"Appium random explore: {result.package_name}")
    allure.dynamic.description(
        f"device={result.device_serial}, steps={config.steps}, pause={config.pause_ms}ms"
    )
    allure.attach.file(str(result.summary_path), name="explore-summary", attachment_type=allure.attachment_type.JSON)
    allure.attach.file(str(result.log_path), name="explore-log", attachment_type=allure.attachment_type.TEXT)
    if result.issues_dir:
        issue_summary = result.issues_dir / "issue-summary.txt"
        if issue_summary.exists():
            allure.attach.file(str(issue_summary), name="issue-summary", attachment_type=allure.attachment_type.TEXT)
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

    print(f"\n=== Appium Explore Result ===")
    print(f"Report: {result.report_dir}")
    print(f"Log: {result.log_path}")
    print(f"Steps: {result.steps_executed}/{result.steps_requested}")
    if result.issues_dir:
        print(f"ISSUE folder: {result.issues_dir}")
        print(f"Issue summary: {result.issues_dir / 'issue-summary.txt'}")
        print(f"Search log for: >>> ISSUE DETECTED <<<")
    else:
        print("Issues: none")
    print(f"Summary: {result.summary_path}")

    if config.fail_on_issue:
        assert not result.has_issues, f"Appium explore found app issue. See {result.summary_path}"
