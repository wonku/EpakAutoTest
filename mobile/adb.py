from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


class AdbError(RuntimeError):
    """Raised when an adb command cannot complete successfully."""


class AdbClient:
    def __init__(self, adb_path: str = "adb", serial: str = ""):
        self.adb_path = adb_path or "adb"
        self.serial = serial.strip()

    def _command(self, args: list[str]) -> list[str]:
        command = [self.adb_path]
        if self.serial:
            command.extend(["-s", self.serial])
        command.extend(args)
        return command

    def run(self, args: list[str], timeout: int = 60, check: bool = True) -> CommandResult:
        command = self._command(args)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise AdbError(f"adb not found: {self.adb_path}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"adb command timed out after {timeout}s: {' '.join(command)}") from exc

        result = CommandResult(command, completed.returncode, completed.stdout, completed.stderr)
        if check and completed.returncode != 0:
            raise AdbError(
                "adb command failed: "
                f"{' '.join(command)}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        return result

    def run_bytes(self, args: list[str], timeout: int = 60, check: bool = True) -> bytes:
        command = self._command(args)
        try:
            completed = subprocess.run(command, capture_output=True, timeout=timeout)
        except FileNotFoundError as exc:
            raise AdbError(f"adb not found: {self.adb_path}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"adb command timed out after {timeout}s: {' '.join(command)}") from exc

        if check and completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace")
            raise AdbError(f"adb command failed: {' '.join(command)}\nstderr:\n{stderr}")
        return completed.stdout

    def ensure_available(self) -> str:
        return self.run(["version"], timeout=15).stdout.strip()

    def connected_devices(self) -> list[str]:
        result = self.run(["devices"], timeout=15)
        devices: list[str] = []
        for line in result.stdout.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices

    def require_device(self) -> str:
        if self.serial:
            state = self.run(["get-state"], timeout=15).stdout.strip()
            if state != "device":
                raise AdbError(f"device {self.serial} is not ready, state={state!r}")
            return self.serial

        devices = self.connected_devices()
        if not devices:
            raise AdbError("no Android device is connected or authorized")
        if len(devices) > 1:
            raise AdbError(
                "multiple Android devices are connected; set MOBILE_DEVICE_SERIAL to choose one: "
                + ", ".join(devices)
            )
        return devices[0]

    def install(self, apk_path: str | Path, timeout: int = 300) -> CommandResult:
        path = Path(apk_path)
        if not path.exists():
            raise AdbError(f"apk not found: {path}")
        result = self.run(["install", "-r", str(path)], timeout=timeout, check=False)
        output = f"{result.stdout}\n{result.stderr}"
        if result.returncode != 0 or "Success" not in output:
            raise AdbError(f"apk install failed:\n{output}")
        return result

    def shell(self, args: list[str], timeout: int = 60, check: bool = True) -> CommandResult:
        return self.run(["shell", *args], timeout=timeout, check=check)

    def tap(self, x: int, y: int) -> None:
        self.shell(["input", "tap", str(x), str(y)], timeout=15)

    def input_text(self, text: str) -> None:
        self.shell(["input", "text", _escape_input_text(text)], timeout=30)

    def press_key(self, keycode: str | int) -> None:
        self.shell(["input", "keyevent", str(keycode)], timeout=15)

    def start_app(self, package_name: str) -> CommandResult:
        return self.shell(
            ["monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"],
            timeout=30,
            check=False,
        )

    def dump_ui_xml(self, retries: int = 3) -> str:
        for attempt in range(retries):
            self.shell(["uiautomator", "dump", "/sdcard/window_dump.xml"], timeout=30, check=False)
            xml_text = self.shell(["cat", "/sdcard/window_dump.xml"], timeout=30, check=False).stdout
            if xml_text.strip().startswith("<?xml") or xml_text.strip().startswith("<hierarchy"):
                return xml_text
            if attempt < retries - 1:
                time.sleep(1)
        return ""

    def screenshot(self, output_path: str | Path) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        png_bytes = self.run_bytes(["exec-out", "screencap", "-p"], timeout=30)
        if not png_bytes:
            raise AdbError("failed to capture screenshot: empty screencap output")
        path.write_bytes(png_bytes)
        return path

    def package_names(self) -> set[str]:
        result = self.shell(["pm", "list", "packages"], timeout=60, check=False)
        packages: set[str] = set()
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                packages.add(line.removeprefix("package:"))
        return packages

    def clear_logcat(self) -> None:
        self.run(["logcat", "-c"], timeout=30, check=False)

    def dump_logcat(self, timeout: int = 60) -> str:
        return self.run(["logcat", "-d", "-v", "time"], timeout=timeout, check=False).stdout

    def device_info(self) -> str:
        fields = [
            ("brand", "ro.product.brand"),
            ("model", "ro.product.model"),
            ("android", "ro.build.version.release"),
            ("sdk", "ro.build.version.sdk"),
        ]
        lines = []
        for label, prop in fields:
            value = self.shell(["getprop", prop], timeout=15, check=False).stdout.strip()
            lines.append(f"{label}: {value}")
        return "\n".join(lines)


def _escape_input_text(text: str) -> str:
    escaped = text.replace("%", r"\%").replace(" ", "%s")
    return re.sub(r"([&|;<>()\"'`])", r"\\\1", escaped)
