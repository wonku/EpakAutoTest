from pathlib import Path

import allure
import pytest

from config import settings
from pages.esbao_auth_page import EsbaoAuthPage
from pages.esbao_mall_home_page import EsbaoMallHomePage
from pages.esbao_product_detail_page import EsbaoProductDetailPage
from tests.mall_inspection_runner import MallInspectionSite, run_mall_inspection

ESBAO_SITE = MallInspectionSite(
    site_id="esbao",
    feature="易食包商城",
    story="生产环境首页巡检",
    title="登录页进入商城首页并检查热销商品跳转",
    email_label="易食包商城",
    report_dir=Path(settings.ESB_UI_REPORT_DIR),
    suite_name="esbao_mall_ui",
    config_report_attr="_esbao_ui_report_path",
    auth_url=settings.ESB_AUTH_URL,
    home_url=settings.ESB_MALL_HOME_URL,
    screenshot_prefix="esbao",
    auth_page_factory=lambda page, url: EsbaoAuthPage(page, url),
    home_page_factory=lambda page, url: EsbaoMallHomePage(page, url),
    detail_page_factory=lambda page: EsbaoProductDetailPage(page),
    open_product=lambda home: home.open_any_hot_product(
        preferred_name=settings.ESB_UI_HOT_PRODUCT_KEYWORD or None
    ),
)


@pytest.mark.esbao
@allure.feature(ESBAO_SITE.feature)
@allure.story(ESBAO_SITE.story)
@allure.title(ESBAO_SITE.title)
def test_esbao_mall_home_and_product_flow(mall_ui_page, request):
    run_mall_inspection(mall_ui_page, ESBAO_SITE, request)
