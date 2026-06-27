from datetime import datetime, timezone
from pathlib import Path

import allure
import pytest

from config import settings
from pages.esbao_auth_page import EsbaoAuthPage
from pages.esbao_mall_home_page import EsbaoMallHomePage
from pages.esbao_product_detail_page import EsbaoProductDetailPage
from utils.esbao_ui_report import EsbaoUiReportCollector
from utils.ui_report_email import send_ui_report_email


@pytest.fixture(scope="function")
def esbao_report_collector() -> EsbaoUiReportCollector:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report_dir = Path(settings.ESB_UI_REPORT_DIR) / timestamp
    return EsbaoUiReportCollector(report_root=report_dir, suite="esbao_mall_ui")


@pytest.mark.esbao
@allure.feature("易食包商城")
@allure.story("生产环境首页巡检")
@allure.title("登录页进入商城首页并检查热销商品跳转")
def test_esbao_mall_home_and_product_flow(mall_ui_page, esbao_report_collector, request):
    collector = esbao_report_collector
    mall_page = mall_ui_page
    exitstatus = 0

    try:
        with allure.step("打开 auth.esbao.com 登录页"):
            auth_page = EsbaoAuthPage(mall_ui_page, settings.ESB_AUTH_URL)
            auth_page.open()
            auth_page.assert_login_page_loaded()
            collector.save_screenshot(mall_ui_page, "01-auth-login.png", full_page=False)
            collector.add_step("打开登录页", "pass", url=mall_ui_page.url)

        with allure.step("点击顶部易食包 Logo 进入商城首页"):
            mall_page = auth_page.open_mall_home_in_new_tab()
            collector.add_step("进入商城首页", "pass", url=mall_page.url)

        home = EsbaoMallHomePage(mall_page, settings.ESB_MALL_HOME_URL)
        with allure.step("校验商城首页关键模块"):
            home.assert_on_home()
            collector.save_screenshot(mall_page, "02-mall-home-top.png", full_page=False)

        with allure.step("全页滚动检查首页元素与图片加载"):
            homepage_checks = home.assert_full_page_loaded(
                scroll_pause_ms=settings.ESB_UI_SCROLL_PAUSE_MS
            )
            collector.add_check("homepage", homepage_checks)
            collector.save_screenshot(mall_page, "03-mall-home-hot-section.png", full_page=False)
            collector.add_step("首页全页检查", "pass", **homepage_checks)

        with allure.step("点击热销爆款任意商品并校验详情页"):
            product_name, mall_page = home.open_any_hot_product(
                preferred_name=settings.ESB_UI_HOT_PRODUCT_KEYWORD or None
            )
            detail = EsbaoProductDetailPage(mall_page)
            detail_checks = detail.assert_detail_loaded()
            collector.add_check(
                "product_detail",
                {"clicked_product": product_name, **detail_checks},
            )
            collector.save_screenshot(mall_page, "04-product-detail.png", full_page=False)
            collector.add_step(
                "商品详情检查",
                "pass",
                product_name=product_name,
                url=mall_page.url,
            )
    except Exception as exc:
        exitstatus = 1
        collector.mark_failed(str(exc))
        collector.add_step("执行失败", "fail", error=str(exc))
        try:
            active = mall_page if mall_page else mall_ui_page
            collector.save_screenshot(active, "99-failure.png", full_page=False)
        except Exception:
            pass
        raise
    finally:
        summary_path = collector.save(exitstatus=exitstatus)
        request.config._esbao_ui_report_path = str(summary_path)
        send_ui_report_email(request.config, "易食包商城", summary_path)
