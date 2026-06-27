import allure

from config.settings import APP_HOME_URL
from pages.crm_page import CrmPage
from pages.home_page import HomePage


@allure.feature("认证模块")
@allure.story("Token 注入登录态")
@allure.title("通过接口获取 token 并直接进入系统")
def test_open_system_by_token(authenticated_page):
    authenticated_page.goto(APP_HOME_URL, wait_until="domcontentloaded")
    authenticated_page.wait_for_timeout(3000)
    assert "login" not in authenticated_page.url.lower(), f"仍停留在登录态: {authenticated_page.url}"


@allure.feature("认证模块")
@allure.story("Token 注入登录态")
@allure.title("登录后点击左侧菜单进入 CRM 2.0")
def test_open_crm2_by_left_menu(authenticated_page):
    authenticated_page.goto(APP_HOME_URL, wait_until="domcontentloaded")
    authenticated_page.wait_for_timeout(3000)
    assert "login" not in authenticated_page.url.lower(), f"仍停留在登录态: {authenticated_page.url}"

    home_page = HomePage(authenticated_page)
    crm_page = home_page.open_left_menu("CRM 2.0")
    crm_page.wait_for_timeout(3000)
    assert "login" not in crm_page.url.lower(), f"点击 CRM 2.0 后仍回到登录页: {crm_page.url}"
    home_page.assert_crm_page_loaded(crm_page)
    with allure.step("进入 CRM 2.0 后截图"):
        crm_png = crm_page.screenshot(full_page=True)
        allure.attach(
            crm_png,
            name="crm2_page_after_enter",
            attachment_type=allure.attachment_type.PNG,
        )


@allure.feature("认证模块")
@allure.story("Token 注入登录态")
@allure.title("进入 CRM 2.0 后打开销售线索菜单")
def test_open_sales_lead_menu_in_crm(authenticated_page):
    authenticated_page.goto(APP_HOME_URL, wait_until="domcontentloaded")
    authenticated_page.wait_for_timeout(3000)
    home_page = HomePage(authenticated_page)
    crm_page = home_page.open_left_menu("CRM 2.0")
    crm_page.wait_for_timeout(3000)
    crm = CrmPage(crm_page)
    crm.open_menu("销售线索")
    crm_page.wait_for_timeout(2000)
    assert "login" not in crm_page.url.lower(), f"打开销售线索后回到登录页: {crm_page.url}"
