from __future__ import annotations

import json
import random
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException

from config import settings
from mobile.adb import AdbClient
from mobile.appium_session import AppiumSessionConfig, create_android_driver
from mobile.inspection import inspect_ui_text, is_white_screen
from mobile.login import run_mobile_login


class ExploreError(RuntimeError):
    """Raised when Appium random exploration cannot continue."""


@dataclass(frozen=True)
class ExploreConfig:
    steps: int
    pause_ms: int
    report_dir: Path
    login_enabled: bool
    login_data_path: Path
    keep_wifi_enabled: bool
    screenshot_enabled: bool
    white_screen_enabled: bool
    white_screen_brightness_threshold: int
    white_screen_ratio: float
    error_text_keywords: list[str]
    block_text_keywords: list[str]
    fail_on_issue: bool
    appium: AppiumSessionConfig

    @classmethod
    def from_settings(cls) -> "ExploreConfig":
        return cls(
            steps=settings.APPIUM_EXPLORE_STEPS,
            pause_ms=settings.APPIUM_EXPLORE_PAUSE_MS,
            report_dir=Path(settings.APPIUM_REPORT_DIR),
            login_enabled=settings.MOBILE_LOGIN_ENABLED,
            login_data_path=Path(settings.MOBILE_LOGIN_DATA_PATH),
            keep_wifi_enabled=settings.MONKEY_KEEP_WIFI_ENABLED,
            screenshot_enabled=settings.APPIUM_SCREENSHOT_ENABLED,
            white_screen_enabled=settings.APPIUM_WHITE_SCREEN_ENABLED,
            white_screen_brightness_threshold=settings.MONKEY_WHITE_SCREEN_BRIGHTNESS_THRESHOLD,
            white_screen_ratio=settings.MONKEY_WHITE_SCREEN_RATIO,
            error_text_keywords=settings.MONKEY_ERROR_TEXT_KEYWORDS,
            block_text_keywords=settings.APPIUM_BLOCK_TEXT_KEYWORDS,
            fail_on_issue=settings.APPIUM_FAIL_ON_ISSUE,
            appium=AppiumSessionConfig.from_settings(),
        )


@dataclass(frozen=True)
class ExploreResult:
    package_name: str
    device_serial: str
    steps_requested: int
    steps_executed: int
    report_dir: Path
    summary_path: Path
    log_path: Path
    screenshot_paths: list[Path]
    issue_screenshot_paths: list[Path]
    issues_dir: Path | None
    issues: list[dict]
    actions: list[dict]

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)


def run_appium_explore(config: ExploreConfig) -> ExploreResult:
    if config.steps <= 0:
        raise ValueError("APPIUM_EXPLORE_STEPS must be greater than 0")

    adb = AdbClient(config.appium.adb_path, config.appium.device_serial)
    adb.ensure_available()
    device_serial = adb.require_device()

    package_name = config.appium.package_name or "com.esbao.englishmobile"
    if config.keep_wifi_enabled:
        _enable_wifi_best_effort(adb)

    if config.login_enabled:
        run_mobile_login(adb, package_name, config.login_data_path)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = config.report_dir / timestamp
    screenshots_dir = report_dir / "screenshots"
    issues_dir = report_dir / "issues"
    report_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    summary_path = report_dir / "explore-summary.json"
    log_path = report_dir / "explore.log"
    actions: list[dict] = []
    issues: list[dict] = []
    screenshot_paths: list[Path] = []
    issue_screenshot_paths: list[Path] = []
    issues_dir_created: Path | None = None

    _append_log(log_path, "INFO", f"explore started package={package_name} device={device_serial} steps={config.steps}")
    _append_log(log_path, "INFO", f"report_dir={report_dir}")

    driver = create_android_driver(config.appium)
    steps_executed = 0
    try:
        current_package = driver.current_package
        package_name = current_package or package_name

        for step_index in range(1, config.steps + 1):
            screenshot_path = None
            if config.screenshot_enabled:
                screenshot_path = screenshots_dir / f"step-{step_index:03d}.png"
                _save_screenshot(driver, screenshot_path)
                screenshot_paths.append(screenshot_path)
                _append_log(
                    log_path,
                    "STEP",
                    f"step={step_index:03d} screenshot={screenshot_path.name} (state after previous action)",
                )

            page_source = driver.page_source or ""
            step_issues = _inspect_page(
                page_source,
                screenshot_path,
                config,
                step_index,
            )
            if step_issues:
                issues_dir_created = _archive_issues(
                    issues_dir=issues_dir,
                    step_index=step_index,
                    step_issues=step_issues,
                    screenshot_path=screenshot_path,
                    previous_screenshot=screenshot_paths[-2] if len(screenshot_paths) >= 2 else None,
                    actions=actions,
                    log_path=log_path,
                )
                for issue in step_issues:
                    issue["issues_dir"] = str(issues_dir_created)
                issues.extend(step_issues)
                if screenshot_path:
                    issue_screenshot_paths.extend(
                        path for path in issues_dir_created.glob("*.png") if path not in issue_screenshot_paths
                    )
                break

            action = _perform_random_action(driver, config.block_text_keywords)
            actions.append({"step": step_index, **action})
            _append_log(
                log_path,
                "ACTION",
                f"step={step_index:03d} type={action['type']} label={action.get('label', '')}",
            )
            steps_executed = step_index
            time.sleep(config.pause_ms / 1000)
    finally:
        driver.quit()

    if issues:
        _append_log(log_path, "INFO", f"explore stopped due to issue at step={issues[0].get('step')} see {issues_dir_created}")
    else:
        _append_log(log_path, "INFO", f"explore finished normally steps_executed={steps_executed}")

    summary = {
        "package_name": package_name,
        "device_serial": device_serial,
        "steps_requested": config.steps,
        "steps_executed": steps_executed,
        "issues_dir": str(issues_dir_created) if issues_dir_created else "",
        "screenshots": [str(path) for path in screenshot_paths],
        "issue_screenshots": [str(path) for path in issue_screenshot_paths],
        "issues": issues,
        "actions": actions,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return ExploreResult(
        package_name=package_name,
        device_serial=device_serial,
        steps_requested=config.steps,
        steps_executed=steps_executed,
        report_dir=report_dir,
        summary_path=summary_path,
        log_path=log_path,
        screenshot_paths=screenshot_paths,
        issue_screenshot_paths=issue_screenshot_paths,
        issues_dir=issues_dir_created,
        issues=issues,
        actions=actions,
    )


def _perform_random_action(driver: WebDriver, block_keywords: list[str]) -> dict:
    candidates = _collect_clickable_elements(driver)
    candidates = [item for item in candidates if not _is_blocked(item, block_keywords)]
    if candidates:
        element = random.choice(candidates)
        label = _element_label(element)
        element.click()
        return {"type": "click", "label": label}

    if random.random() < 0.2:
        driver.back()
        return {"type": "back", "label": "system_back"}

    _swipe_random(driver)
    return {"type": "swipe", "label": "random_swipe"}


def _collect_clickable_elements(driver: WebDriver) -> list:
    selectors = [
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().clickable(true)'),
        (AppiumBy.XPATH, "//*[@clickable='true']"),
        (AppiumBy.CLASS_NAME, "android.widget.EditText"),
    ]
    elements = []
    seen = set()
    for by, value in selectors:
        try:
            found = driver.find_elements(by, value)
        except WebDriverException:
            continue
        for element in found:
            try:
                if not element.is_displayed() or not element.is_enabled():
                    continue
                key = (
                    element.get_attribute("resource-id") or "",
                    element.get_attribute("text") or "",
                    element.get_attribute("content-desc") or "",
                    element.get_attribute("class") or "",
                )
                if key in seen:
                    continue
                seen.add(key)
                elements.append(element)
            except StaleElementReferenceException:
                continue
    return elements


def _is_blocked(element, block_keywords: list[str]) -> bool:
    label = _element_label(element).lower()
    return any(keyword.lower() in label for keyword in block_keywords if keyword)


def _element_label(element) -> str:
    parts = [
        element.get_attribute("text") or "",
        element.get_attribute("content-desc") or "",
        element.get_attribute("resource-id") or "",
        element.get_attribute("class") or "",
    ]
    return " | ".join(part for part in parts if part).strip()


def _swipe_random(driver: WebDriver) -> None:
    size = driver.get_window_size()
    width = size["width"]
    height = size["height"]
    start_x = random.randint(int(width * 0.2), int(width * 0.8))
    start_y = random.randint(int(height * 0.3), int(height * 0.8))
    end_x = start_x
    end_y = start_y - random.randint(int(height * 0.1), int(height * 0.3))
    if end_y < int(height * 0.1):
        end_y = start_y + random.randint(int(height * 0.1), int(height * 0.3))
    driver.swipe(start_x, start_y, end_x, end_y, 400)


def _inspect_page(
    page_source: str,
    screenshot_path: Path | None,
    config: ExploreConfig,
    step_index: int,
) -> list[dict]:
    issues = inspect_ui_text(page_source, config.error_text_keywords)
    for issue in issues:
        issue["step"] = step_index
        if screenshot_path:
            issue["screenshot"] = str(screenshot_path)

    if (
        config.white_screen_enabled
        and screenshot_path
        and is_white_screen(
            screenshot_path,
            config.white_screen_brightness_threshold,
            config.white_screen_ratio,
        )
    ):
        issues.append(
            {
                "type": "white_screen",
                "step": step_index,
                "screenshot": str(screenshot_path),
                "message": "screen is mostly white",
            }
        )
    return issues


def _save_screenshot(driver: WebDriver, screenshot_path: Path) -> None:
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    driver.save_screenshot(str(screenshot_path))


def _archive_issues(
    issues_dir: Path,
    step_index: int,
    step_issues: list[dict],
    screenshot_path: Path | None,
    previous_screenshot: Path | None,
    actions: list[dict],
    log_path: Path,
) -> Path:
    issues_dir.mkdir(parents=True, exist_ok=True)
    archived_paths: list[Path] = []
    primary_issue = step_issues[0]
    issue_slug = _issue_slug(primary_issue)

    if screenshot_path and screenshot_path.exists():
        issue_path = issues_dir / f"step-{step_index:03d}-{issue_slug}.png"
        shutil.copy2(screenshot_path, issue_path)
        archived_paths.append(issue_path)
        primary_issue["issue_screenshot"] = str(issue_path)

    if previous_screenshot and previous_screenshot.exists():
        before_path = issues_dir / f"step-{step_index - 1:03d}-before-action.png"
        shutil.copy2(previous_screenshot, before_path)
        archived_paths.append(before_path)
        primary_issue["before_screenshot"] = str(before_path)

    recent_actions = actions[-5:]
    context = {
        "step": step_index,
        "issues": step_issues,
        "recent_actions": recent_actions,
        "archived_screenshots": [str(path) for path in archived_paths],
    }
    context_path = issues_dir / "issue-context.json"
    context_path.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_lines = [
        f"ISSUE DETECTED AT STEP {step_index:03d}",
        "=" * 60,
    ]
    for issue in step_issues:
        summary_lines.append(f"type: {issue.get('type')}")
        summary_lines.append(f"message: {issue.get('message', issue.get('keyword', ''))}")
    summary_lines.extend(
        [
            "",
            "Archived screenshots:",
            *[f"  - {path.name}" for path in archived_paths],
            "",
            "Recent actions (for reproduction, oldest -> newest):",
        ]
    )
    if recent_actions:
        for action in recent_actions:
            summary_lines.append(
                f"  step={action['step']:03d} type={action['type']} label={action.get('label', '')}"
            )
    else:
        summary_lines.append("  (no prior actions)")
    summary_lines.extend(["", f"Full log: {log_path}", f"Context JSON: {context_path}"])
    issue_summary_path = issues_dir / "issue-summary.txt"
    issue_summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    _append_log(log_path, "ISSUE", ">>> ISSUE DETECTED <<<")
    _append_log(log_path, "ISSUE", f"step={step_index:03d} type={primary_issue.get('type')} message={primary_issue.get('message', primary_issue.get('keyword', ''))}")
    _append_log(log_path, "ISSUE", f"issue_folder={issues_dir}")
    for path in archived_paths:
        _append_log(log_path, "ISSUE", f"screenshot={path.name}")
    _append_log(log_path, "ISSUE", "recent_actions:")
    for action in recent_actions:
        _append_log(
            log_path,
            "ISSUE",
            f"  step={action['step']:03d} type={action['type']} label={action.get('label', '')}",
        )
    _append_log(log_path, "ISSUE", ">>> END ISSUE <<<")
    return issues_dir


def _issue_slug(issue: dict) -> str:
    issue_type = str(issue.get("type", "issue"))
    keyword = str(issue.get("keyword", "")).strip()
    if keyword:
        safe_keyword = "".join(char if char.isalnum() else "-" for char in keyword).strip("-")
        if safe_keyword:
            return f"{issue_type}-{safe_keyword[:30]}"
    return issue_type


def _append_log(log_path: Path, level: str, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] [{level}] {message}\n")


def _enable_wifi_best_effort(adb: AdbClient) -> None:
    adb.shell(["svc", "wifi", "enable"], timeout=15, check=False)
    adb.shell(["cmd", "wifi", "set-wifi-enabled", "enabled"], timeout=15, check=False)
