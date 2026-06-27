import allure

from config.settings import (
    CAPTCHA_MANUAL_FALLBACK,
    CAPTCHA_MANUAL_WAIT_SECONDS,
    CAPTCHA_MAX_AUTO_RETRY,
    LOGIN_PASSWORD,
    LOGIN_PHONE,
)
from pages.login_page import LoginPage


@allure.feature("认证模块")
@allure.story("账号密码登录")
@allure.title("用户使用正确账号密码登录成功")
def test_login_success(page):
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


@allure.feature("认证模块")
@allure.story("账号密码登录")
@allure.title("用户使用错误密码登录失败")
def test_login_failed_with_wrong_password(page):
    login_page = LoginPage(page)
    login_page.open()
    login_page.login(LOGIN_PHONE, f"{LOGIN_PASSWORD}X")
    if login_page.has_slider_captcha():
        login_page.solve_slider_captcha()
    error_text = login_page.get_any_error_text()
    assert error_text, "未捕获到失败提示信息"


@allure.feature("认证模块")
@allure.story("账号密码登录")
@allure.title("用户不输入密码时登录失败")
def test_login_failed_without_password(page):
    login_page = LoginPage(page)
    login_page.open()
    login_page.login(LOGIN_PHONE, "")
    error_text = login_page.get_any_error_text()
    assert error_text, "未捕获到空密码校验提示"
