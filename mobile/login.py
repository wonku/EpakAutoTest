from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from string import Template

from mobile.adb import AdbClient


class MobileLoginError(RuntimeError):
    """Raised when the pre-monkey mobile login flow cannot finish."""


@dataclass(frozen=True)
class LoginResult:
    enabled: bool
    data_path: Path
    steps_run: int = 0


def run_mobile_login(adb: AdbClient, package_name: str, data_path: Path) -> LoginResult:
    if not data_path.exists():
        raise MobileLoginError(f"mobile login data file not found: {data_path}")

    data = json.loads(data_path.read_text(encoding="utf-8"))
    if not data.get("enabled", True):
        return LoginResult(enabled=False, data_path=data_path)

    username = str(data.get("username", ""))
    password = str(data.get("password", ""))
    variables = {"username": username, "password": password}

    adb.start_app(package_name)
    time.sleep(float(data.get("launch_wait_seconds", 5)))

    success_selector = data.get("success_selector")
    if success_selector and _find_node(adb.dump_ui_xml(), success_selector):
        return LoginResult(enabled=True, data_path=data_path, steps_run=0)

    steps = data.get("steps", [])
    if not isinstance(steps, list) or not steps:
        raise MobileLoginError("mobile login data must contain at least one step")

    for step in steps:
        if success_selector and _find_node(adb.dump_ui_xml(), success_selector):
            return LoginResult(enabled=True, data_path=data_path, steps_run=0)
        _run_step(adb, step, variables)

    if success_selector and not _wait_for_selector(
        adb,
        success_selector,
        float(data.get("post_login_wait_seconds", 15)),
    ):
        raise MobileLoginError(f"login success selector not found: {success_selector}")

    return LoginResult(enabled=True, data_path=data_path, steps_run=len(steps))


def _run_step(adb: AdbClient, step: dict, variables: dict[str, str]) -> None:
    action = step.get("action")
    wait_seconds = float(step.get("wait_seconds", 0))
    if wait_seconds:
        time.sleep(wait_seconds)

    if action == "wait":
        time.sleep(float(step.get("seconds", 1)))
        return

    if action == "press":
        adb.press_key(step["keycode"])
        return

    if action in {"tap", "input"}:
        try:
            _tap_target(adb, step)
        except MobileLoginError:
            if step.get("optional"):
                return
            raise
        if action == "input":
            value = Template(str(step.get("value", ""))).safe_substitute(variables)
            clear_first = bool(step.get("clear_first", True))
            if clear_first:
                _clear_current_field(adb)
            adb.input_text(value)
        return

    raise MobileLoginError(f"unsupported login step action: {action}")


def _tap_target(adb: AdbClient, step: dict) -> None:
    if "x" in step and "y" in step:
        adb.tap(int(step["x"]), int(step["y"]))
        return

    selector = step.get("selector")
    if not selector:
        return

    timeout_seconds = float(step.get("timeout_seconds", 10))
    deadline = time.time() + timeout_seconds
    while time.time() <= deadline:
        node = _find_node(adb.dump_ui_xml(), selector)
        if node is not None:
            if node.attrib.get("_raw_match") == "true":
                time.sleep(1)
                continue
            x, y = _node_center(node)
            adb.tap(x, y)
            return
        time.sleep(1)

    raise MobileLoginError(f"target not found for selector: {selector}")


def _wait_for_selector(adb: AdbClient, selector: dict, timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() <= deadline:
        if _find_node(adb.dump_ui_xml(), selector):
            return True
        time.sleep(1)
    return False


def _find_node(xml_text: str, selector: dict) -> ET.Element | None:
    if not xml_text.strip():
        return None
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return _raw_xml_contains(xml_text, selector)

    for node in root.iter("node"):
        if _matches(node.attrib, selector):
            return node
    return None


def _raw_xml_contains(xml_text: str, selector: dict) -> ET.Element | None:
    for key in ("text", "text_contains", "hint", "hint_contains", "description", "description_contains"):
        value = selector.get(key)
        if value and str(value) in xml_text:
            return ET.Element("node", {"_raw_match": "true"})
    return None


def _matches(attrs: dict[str, str], selector: dict) -> bool:
    checks = {
        "text": attrs.get("text", ""),
        "text_contains": attrs.get("text", ""),
        "hint": attrs.get("hint", ""),
        "hint_contains": attrs.get("hint", ""),
        "resource_id": attrs.get("resource-id", ""),
        "resource_id_contains": attrs.get("resource-id", ""),
        "description": attrs.get("content-desc", ""),
        "description_contains": attrs.get("content-desc", ""),
        "class_name": attrs.get("class", ""),
    }
    for key, expected in selector.items():
        actual = checks.get(key)
        if actual is None:
            continue
        expected = str(expected)
        if key.endswith("_contains"):
            if expected not in actual:
                return False
        elif actual != expected:
            return False
    return True


def _node_center(node: ET.Element) -> tuple[int, int]:
    bounds = node.attrib.get("bounds", "")
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
    if not match:
        raise MobileLoginError(f"invalid node bounds: {bounds}")
    left, top, right, bottom = [int(item) for item in match.groups()]
    return (left + right) // 2, (top + bottom) // 2


def _clear_current_field(adb: AdbClient) -> None:
    adb.press_key("KEYCODE_MOVE_END")
    for _ in range(30):
        adb.press_key("KEYCODE_DEL")
