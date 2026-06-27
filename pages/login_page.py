import json
import cv2
import numpy as np
import random
import time

import allure
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect

from config.settings import (
    BASE_URL,
    CAPTCHA_DRAG_STEPS,
    CAPTCHA_DRAG_STEP_DELAY_MAX,
    CAPTCHA_DRAG_STEP_DELAY_MIN,
    CAPTCHA_HOLD_AFTER_REACH_MAX_MS,
    CAPTCHA_HOLD_AFTER_REACH_MIN_MS,
    CAPTCHA_IMAGE_SOLVE_ENABLED,
    CAPTCHA_IMAGE_SOLVE_OFFSET_PX,
    CAPTCHA_SWEEP_ENABLED,
    CAPTCHA_SWEEP_END_RATIO,
    CAPTCHA_SWEEP_HOLD_MS,
    CAPTCHA_SWEEP_START_RATIO,
    CAPTCHA_SWEEP_STEP_PX,
    LOGIN_PATH,
)
from utils.base_page import BasePage


def _attach_allure_json(name: str, data: dict) -> None:
    allure.attach(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        name=name,
        attachment_type=allure.attachment_type.JSON,
    )


def _attach_allure_png_bytes(name: str, png_bytes: bytes) -> None:
    allure.attach(
        png_bytes,
        name=name,
        attachment_type=allure.attachment_type.PNG,
    )


class LoginPage(BasePage):
    phone_selectors = [
        "input[placeholder*='手机号']",
        "input[placeholder*='手机号码']",
        "input[type='tel']",
        "input[name='phone']",
        "input[name='mobile']",
    ]
    password_selectors = [
        "input[placeholder*='密码']",
        "input[type='password']",
        "input[name='password']",
    ]
    login_button_selectors = [
        "button:has-text('登录')",
        "button:has-text('登 录')",
        "button[type='submit']",
        ".el-button--primary",
    ]
    error_message_selectors = [
        ".el-message__content",
        ".el-form-item__error",
        ".ant-message-notice-content",
    ]

    def open(self) -> None:
        self.goto(f"{BASE_URL}{LOGIN_PATH}")

    def _fill_first(self, selectors: list[str], value: str) -> None:
        for selector in selectors:
            locator = self.page.locator(selector).first
            if locator.count() > 0:
                locator.fill(value)
                return
        raise AssertionError(f"未找到可填写输入框: {selectors}")

    def _click_first(self, selectors: list[str]) -> None:
        for selector in selectors:
            locator = self.page.locator(selector).first
            if locator.count() > 0:
                locator.click()
                return
        raise AssertionError(f"未找到可点击登录按钮: {selectors}")

    def login(self, phone: str, password: str) -> None:
        self._fill_first(self.phone_selectors, phone)
        self._fill_first(self.password_selectors, password)
        self.click_login_button()

    def click_login_button(self) -> None:
        self._click_first(self.login_button_selectors)

    def is_still_on_login_page(self) -> bool:
        return LOGIN_PATH in self.page.url

    def has_slider_captcha(self) -> bool:
        self.page.wait_for_timeout(800)
        tencent_iframe = self.page.frame_locator("iframe[id*='tcaptcha'], iframe[src*='captcha']").first
        if tencent_iframe.locator("#tcaptcha_drag_thumb").count() > 0:
            return True
        return self.page.locator(
            "#tcaptcha_drag_thumb, .slider, .captcha-slider, [class*='slider']"
        ).count() > 0

    def solve_slider_captcha(self, max_retry: int = 8) -> bool:
        """
        通用滑块验证码处理：
        1) 优先处理腾讯验证码 iframe。
        2) 未命中时尝试当前页常见滑块按钮。
        """
        for attempt_idx in range(max_retry):
            if self._solve_tencent_slider_once(attempt_idx=attempt_idx):
                return True
            if self._solve_inline_slider_once():
                return True
            self.page.wait_for_timeout(1200)
            if not self.has_slider_captcha():
                return True
        return not self.has_slider_captcha()

    def wait_manual_captcha_solved(self, timeout_ms: int = 120000) -> bool:
        """
        人工接管模式：保留浏览器让测试人员手动拖动验证码，直到验证码消失或超时。
        """
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            if not self.has_slider_captcha():
                return True
            self.page.wait_for_timeout(1200)
        return not self.has_slider_captcha()

    def _drag_like_human(self, handle, distance: int, hold_ms: int | None = None) -> None:
        box = handle.bounding_box()
        if not box:
            return
        start_x = box["x"] + box["width"] / 2
        start_y = box["y"] + box["height"] / 2
        self.page.mouse.move(start_x, start_y)
        self.page.mouse.down()

        # 分段慢速拖拽，增强“人工操作”特征，减少风控误判
        steps = max(CAPTCHA_DRAG_STEPS, 12)
        moved = 0
        for step in range(1, steps + 1):
            target = int(distance * step / steps)
            delta = target - moved + random.randint(-2, 2)
            moved += max(delta, 1)
            self.page.mouse.move(start_x + moved, start_y + random.randint(-1, 1), steps=2)
            time.sleep(random.uniform(CAPTCHA_DRAG_STEP_DELAY_MIN, CAPTCHA_DRAG_STEP_DELAY_MAX))

        # 轻微回拉再前进，模拟真实手势
        self.page.mouse.move(start_x + moved - random.randint(2, 5), start_y, steps=2)
        self.page.mouse.move(start_x + moved + random.randint(2, 4), start_y, steps=2)
        # 到达目标后保持按住一小段时间，给验证码服务端校验窗口
        if hold_ms is None:
            hold_ms = random.randint(CAPTCHA_HOLD_AFTER_REACH_MIN_MS, CAPTCHA_HOLD_AFTER_REACH_MAX_MS)
        self.page.wait_for_timeout(hold_ms)
        self.page.mouse.up()

    def _solve_tencent_slider_once(self, attempt_idx: int = 0) -> bool:
        frame = self.page.frame(name="tcaptcha_iframe")
        if frame is None:
            for f in self.page.frames:
                if "captcha" in f.url or "tencent" in f.url:
                    frame = f
                    break
        frame_scope = frame
        if frame_scope is None:
            frame_scope = self.page.frame_locator("iframe[id*='tcaptcha'], iframe[src*='captcha']").first

        handle = frame_scope.locator("#tcaptcha_drag_thumb")
        if handle.count() == 0:
            return False

        bar = frame_scope.locator("#tcaptcha_drag_track")
        drag_distance = 260
        bar_width = 260
        if bar.count() > 0:
            bar_box = bar.first.bounding_box()
            if bar_box:
                drag_distance = int(bar_box["width"] - 38)
                bar_width = int(bar_box["width"])

        if CAPTCHA_IMAGE_SOLVE_ENABLED and bar.count() > 0:
            image_target, image_dbg = self._detect_tencent_gap_distance_by_image(frame_scope, bar_width)
            image_dbg["attempt_idx"] = attempt_idx
            image_dbg["image_solve_enabled"] = True
            _attach_allure_json("captcha_image_analysis", image_dbg)
            if image_target is not None:
                final_px = image_target + CAPTCHA_IMAGE_SOLVE_OFFSET_PX
                image_dbg["offset_px"] = CAPTCHA_IMAGE_SOLVE_OFFSET_PX
                image_dbg["final_drag_px_before_attempt"] = final_px
                self._drag_like_human(handle.first, final_px)
                self.page.wait_for_timeout(1500)
                solved_img = self._is_tencent_solved()
                _attach_allure_json(
                    "captcha_after_image_drag",
                    {
                        **image_dbg,
                        "final_drag_px_applied": final_px,
                        "solved_after_image_drag": solved_img,
                    },
                )
                if solved_img:
                    return True
                self._refresh_tencent_captcha(frame_scope)

        if CAPTCHA_SWEEP_ENABLED and bar.count() > 0:
            start = max(80, int(drag_distance * CAPTCHA_SWEEP_START_RATIO))
            end = max(start + CAPTCHA_SWEEP_STEP_PX, int(drag_distance * CAPTCHA_SWEEP_END_RATIO))
            sweep_log: list[dict] = []
            candidates = list(range(start, end + 1, CAPTCHA_SWEEP_STEP_PX))
            # 图像识别失败时不要每轮都从同一起点扫描，避免“固定错误点”。
            if candidates:
                shift = attempt_idx % len(candidates)
                candidates = candidates[shift:] + candidates[:shift]
            _attach_allure_json(
                "captcha_sweep_plan",
                {
                    "attempt_idx": attempt_idx,
                    "start_px": start,
                    "end_px": end,
                    "step_px": CAPTCHA_SWEEP_STEP_PX,
                    "candidate_count": len(candidates),
                    "shift": (attempt_idx % len(candidates)) if candidates else 0,
                },
            )
            for sweep_idx, candidate in enumerate(candidates):
                fresh = self.page.frame(name="tcaptcha_iframe")
                if fresh is None:
                    for f in self.page.frames:
                        if "captcha" in f.url or "tencent" in f.url:
                            fresh = f
                            break
                if fresh is None:
                    return True
                fresh_handle = fresh.locator("#tcaptcha_drag_thumb").first
                if fresh_handle.count() == 0:
                    return True
                self._drag_like_human(fresh_handle, candidate, hold_ms=CAPTCHA_SWEEP_HOLD_MS)
                self.page.wait_for_timeout(1200)
                solved_sweep = self._is_tencent_solved()
                sweep_log.append(
                    {
                        "sweep_idx": sweep_idx,
                        "candidate_drag_px": candidate,
                        "hold_ms": CAPTCHA_SWEEP_HOLD_MS,
                        "solved": solved_sweep,
                    }
                )
                _attach_allure_json(f"captcha_sweep_step_{candidate}px", sweep_log[-1])
                if solved_sweep:
                    _attach_allure_json("captcha_sweep_summary", {"attempts": sweep_log})
                    return True
                self._refresh_tencent_captcha(fresh)
            _attach_allure_json("captcha_sweep_summary_failed", {"attempts": sweep_log})
            return self._is_tencent_solved()

        self._drag_like_human(handle.first, drag_distance)
        self.page.wait_for_timeout(1500)
        if self._is_tencent_solved():
            return True

        # 失败后尝试点击刷新，避免卡在同一张难图上
        self._refresh_tencent_captcha(frame_scope)
        return False

    def _detect_tencent_gap_distance_by_image(self, frame, bar_width: int) -> tuple[int | None, dict]:
        bg_selectors = [
            "#slideBg",
            "#tcaptcha-verify-image",
            "img[id*='slide'][id*='bg']",
            "img[src*='captcha']",
            "canvas",
        ]
        bg_locator = None
        matched_selector = None
        for selector in bg_selectors:
            loc = frame.locator(selector).first
            if loc.count() > 0:
                bg_locator = loc
                matched_selector = selector
                break
        debug: dict = {"strategy": "dark_column_plus_canny_edges", "matched_selector": matched_selector}
        if bg_locator is None:
            debug["failure"] = "no_background_element"
            return None, debug

        bg_box = bg_locator.bounding_box()
        debug["bounding_box_css_px"] = bg_box
        if not bg_box or bg_box["width"] < 50:
            debug["failure"] = "invalid_bounding_box"
            return None, debug

        raw = bg_locator.screenshot(type="png")
        _attach_allure_png_bytes("captcha_background_raw_for_analysis", raw)
        img_np = np.frombuffer(raw, dtype=np.uint8)
        img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
        if img is None:
            debug["failure"] = "imdecode_failed"
            return None, debug

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        # 基于“缺口区域偏暗+边缘突变”构造列得分，寻找最可能缺口 X
        edge = cv2.Canny(blur, 60, 140)
        dark_score = 255 - np.mean(blur, axis=0)
        edge_score = np.sum(edge > 0, axis=0).astype(np.float32)
        score = dark_score * 0.7 + edge_score * 0.3
        score = cv2.GaussianBlur(score.reshape(1, -1), (1, 21), 0).reshape(-1)

        width = gray.shape[1]
        left = int(width * 0.18)
        right = int(width * 0.95)
        if right <= left:
            debug["failure"] = "scan_window_empty"
            return None, debug
        gap_x = int(np.argmax(score[left:right]) + left)

        ratio = gap_x / max(width, 1)
        # 滑块中心通常需要比缺口中心略小的位移
        base_drag_px = int(ratio * bar_width) - 18

        debug.update(
            {
                "image_pixels_w": width,
                "scan_left": left,
                "scan_right_exclusive": right,
                "estimated_gap_center_x_px": gap_x,
                "ratio_gap_to_width": round(ratio, 4),
                "bar_width_css_px_used": bar_width,
                "base_drag_px_estimate": base_drag_px,
            }
        )
        return base_drag_px, debug

    def _is_tencent_solved(self) -> bool:
        fresh_frame = self.page.frame(name="tcaptcha_iframe")
        if fresh_frame is None:
            locator_thumb = self.page.frame_locator(
                "iframe[id*='tcaptcha'], iframe[src*='captcha']"
            ).first.locator("#tcaptcha_drag_thumb")
            return locator_thumb.count() == 0
        return fresh_frame.locator("#tcaptcha_drag_thumb").count() == 0

    def _refresh_tencent_captcha(self, frame) -> None:
        refresh_btn = frame.locator("#reload, .tc-action-icon, [id*='reload']").first
        if refresh_btn.count() > 0:
            try:
                refresh_btn.click(timeout=1000)
                self.page.wait_for_timeout(800)
            except PlaywrightTimeoutError:
                pass

    def _solve_inline_slider_once(self) -> bool:
        slider = self.page.locator(
            ".slider-button, .captcha-slider-button, [class*='slider'][class*='button'], [class*='drag']"
        )
        if slider.count() == 0:
            return False
        self._drag_like_human(slider.first, 280)
        self.page.wait_for_timeout(1500)
        return slider.count() == 0 or not self.has_slider_captcha()

    def get_any_error_text(self) -> str:
        for selector in self.error_message_selectors:
            locator = self.page.locator(selector).first
            try:
                if locator.count() > 0 and locator.is_visible(timeout=1500):
                    text = locator.inner_text().strip()
                    if text:
                        return text
            except PlaywrightTimeoutError:
                continue
        return ""

    def assert_login_success(self) -> None:
        expect(self.page).not_to_have_url(f"{BASE_URL}{LOGIN_PATH}", timeout=15000)
