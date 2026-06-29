from pathlib import Path

import allure
import pytest

from config import settings
from pages.epak_auth_page import EpakAuthPage
from pages.epak_mall_home_page import EpakMallHomePage
from pages.epak_product_detail_page import EpakProductDetailPage
from tests.mall_inspection_runner import MallInspectionSite, run_mall_inspection


def _epak_pre_home_checks(home, collector, mall_page, prefix) -> None:
    with allure.step("等待订阅弹窗加载并关闭"):
        popup_loaded = home.wait_for_subscribe_popup_loaded()
        collector.add_check("subscribe_popup", {"loaded": popup_loaded})
        if popup_loaded:
            collector.save_screenshot(
                mall_page, f"03-{prefix}-subscribe-popup.png", full_page=False
            )
            home.close_subscribe_popup()
        home.dismiss_cookie_banner_if_present()
        collector.add_step("关闭订阅弹窗", "pass", popup_loaded=popup_loaded)


EPAK_SITE = MallInspectionSite(
    site_id="epak",
    feature="EPAK 英文商城",
    story="生产环境首页巡检",
    title="登录页进入商城首页并检查 One-Stop 商品跳转",
    email_label="EPAK 英文商城",
    report_dir=Path(settings.EPAK_UI_REPORT_DIR),
    suite_name="epak_mall_ui",
    config_report_attr="_epak_ui_report_path",
    auth_url=settings.EPAK_AUTH_URL,
    home_url=settings.EPAK_MALL_HOME_URL,
    screenshot_prefix="epak",
    auth_page_factory=lambda page, url: EpakAuthPage(page, url),
    home_page_factory=lambda page, url: EpakMallHomePage(page, url),
    detail_page_factory=lambda page: EpakProductDetailPage(page),
    open_product=lambda home: home.open_any_one_stop_product(
        preferred_name=settings.EPAK_UI_PRODUCT_KEYWORD or None
    ),
    pre_home_checks=_epak_pre_home_checks,
)


@pytest.mark.epak
@allure.feature(EPAK_SITE.feature)
@allure.story(EPAK_SITE.story)
@allure.title(EPAK_SITE.title)
def test_epak_mall_home_and_product_flow(mall_ui_page, request):
    run_mall_inspection(mall_ui_page, EPAK_SITE, request)
