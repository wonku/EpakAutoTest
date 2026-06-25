from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def inspect_ui_text(xml_text: str, keywords: list[str]) -> list[dict]:
    issues: list[dict] = []
    for keyword in keywords:
        if keyword and keyword in xml_text:
            issues.append(
                {
                    "type": "error_text",
                    "keyword": keyword,
                    "message": f"found error keyword in UI: {keyword}",
                }
            )
    return issues


def is_white_screen(screenshot_path: Path, brightness_threshold: int, white_ratio_threshold: float) -> bool:
    image = cv2.imread(str(screenshot_path))
    if image is None:
        return False
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    white_ratio = float(np.mean(gray >= brightness_threshold))
    return white_ratio >= white_ratio_threshold
