import json
import time

import allure
import pytest

from config.settings import (
    CAPTCHA_MANUAL_FALLBACK,
    CAPTCHA_MANUAL_WAIT_SECONDS,
    CAPTCHA_MAX_AUTO_RETRY,
    LOGIN_PASSWORD,
    LOGIN_PHONE,
)
from pages.login_page import LoginPage


@pytest.mark.login_benchmark
@pytest.mark.parametrize(
    "iteration",
    range(10),
    ids=[f"run_{i}" for i in range(10)],
)
@allure.feature("认证模块")
@allure.story("基准测试")
@allure.title("登录成功十次耗时采样")
def test_login_success_benchmark_10(page, pytestconfig, iteration):
    t0 = time.perf_counter()
    login_page = LoginPage(page)
    with allure.step("打开登录页面"):
        login_page.open()
    with allure.step("输入手机号和密码并点击登录"):
        login_page.login(LOGIN_PHONE, LOGIN_PASSWORD)
    with allure.step("若出现滑块验证码则自动拖动处理"):
        if login_page.has_slider_captcha():
            solved = login_page.solve_slider_captcha(max_retry=CAPTCHA_MAX_AUTO_RETRY)
            if not solved and CAPTCHA_MANUAL_FALLBACK:
                with allure.step("自动未通过，切换人工手动拖动验证码"):
                    solved = login_page.wait_manual_captcha_solved(
                        timeout_ms=CAPTCHA_MANUAL_WAIT_SECONDS * 1000
                    )
            assert solved, "滑块验证码自动处理失败"
            if login_page.is_still_on_login_page():
                with allure.step("验证码通过后再次点击登录提交"):
                    login_page.click_login_button()
    with allure.step("校验登录成功"):
        login_page.assert_login_success()

    elapsed = time.perf_counter() - t0
    pytestconfig._login_benchmark_times.append(elapsed)

    payload = {
        "iteration": iteration,
        "elapsed_seconds": round(elapsed, 3),
        "note": "见终端 login_benchmark 汇总与 reports/benchmark-last.json",
    }
    allure.attach(
        json.dumps(payload, indent=2, ensure_ascii=False),
        name=f"benchmark_iteration_{iteration}_timing",
        attachment_type=allure.attachment_type.JSON,
    )
