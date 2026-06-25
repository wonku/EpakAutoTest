from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class EsbaoUiReportCollector:
    report_root: Path
    suite: str = "esbao_mall_ui"
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    steps: list[dict[str, Any]] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)
    screenshots: list[Path] = field(default_factory=list)
    error: str = ""

    def __post_init__(self) -> None:
        self.report_root.mkdir(parents=True, exist_ok=True)

    def add_step(self, name: str, status: str, **extra: Any) -> None:
        self.steps.append({"name": name, "status": status, **extra})

    def add_check(self, name: str, data: Any) -> None:
        self.checks[name] = data

    def save_screenshot(self, page, name: str, *, full_page: bool = True) -> Path:
        path = self.report_root / name
        page.screenshot(path=str(path), full_page=full_page)
        self.screenshots.append(path)
        return path

    def mark_failed(self, message: str) -> None:
        self.error = message

    def save(self, exitstatus: int) -> Path:
        finished_at = datetime.now(timezone.utc)
        payload = {
            "suite": self.suite,
            "status": "PASS" if exitstatus == 0 and not self.error else "FAIL",
            "exitstatus": exitstatus,
            "started_at": self.started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round((finished_at - self.started_at).total_seconds(), 3),
            "report_dir": str(self.report_root.resolve()),
            "steps": self.steps,
            "checks": self.checks,
            "screenshots": [str(path) for path in self.screenshots],
            "error": self.error,
        }
        summary_path = self.report_root / "report.json"
        summary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        latest_pointer = self.report_root.parent / "latest.txt"
        latest_pointer.write_text(str(self.report_root.resolve()), encoding="utf-8")
        return summary_path


def latest_esbao_report_dir(report_parent: Path) -> Path | None:
    pointer = report_parent / "latest.txt"
    if pointer.exists():
        path = Path(pointer.read_text(encoding="utf-8").strip())
        if path.exists():
            return path
    if not report_parent.exists():
        return None
    dirs = [path for path in report_parent.iterdir() if path.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda path: path.stat().st_mtime)


def ui_report_attachments(report_dir: Path, summary_path: Path) -> list[Path]:
    attachments: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        if not path.exists():
            return
        key = str(path.resolve())
        if key in seen:
            return
        seen.add(key)
        attachments.append(path)

    add(summary_path)
    report_json = report_dir / "report.json"
    add(report_json)
    if report_json.exists():
        try:
            data = json.loads(report_json.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        for item in data.get("screenshots", []):
            add(Path(item))
    return attachments


def latest_esbao_attachments(report_parent: Path, summary_path: Path) -> list[Path]:
    attachments: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        if not path.exists():
            return
        key = str(path.resolve())
        if key in seen:
            return
        seen.add(key)
        attachments.append(path)

    add(summary_path)
    report_dir = latest_esbao_report_dir(report_parent)
    if report_dir is None:
        return attachments

    report_json = report_dir / "report.json"
    add(report_json)
    if report_json.exists():
        try:
            data = json.loads(report_json.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        for item in data.get("screenshots", []):
            add(Path(item))
    return attachments
