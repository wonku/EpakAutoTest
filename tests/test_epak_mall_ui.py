from datetime import datetime, timezone
from pathlib import Path

import allure
import pytest

from config import settings
from pages.epak_auth_page import EpakAuthPage
from pages.epak_mall_home_page import EpakMallHomePage
from pages.epak_product_detail_page import EpakProductDetailPage
from utils.esbao_ui_report import EsbaoUiReportCollector
from utils.ui_report_email import send_ui_report_email


@pytest.fixture(scope="function")
def epak_report_collector() -> EsbaoUiReportCollector:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report_dir = Path(settings.EPAK_UI_REPORT_DIR) / timestamp
    return EsbaoUiReportCollector(report_root=report_dir, suite="epak_mall_ui")


@pytest.mark.epak
@allure.feature("EPAK 英文商城")
@allure.story("生产环境首页巡检")
@allure.title("登录页进入商城首页并检查 One-Stop 商品跳转")
def test_epak_mall_home_and_product_flow(mall_ui_page, epak_report_collector, request):
    collector = epak_report_collector
    mall_page = mall_ui_page
    exitstatus = 0

    try:
        with allure.step("打开 auth.epakgroup.com 登录页"):
            auth_page = EpakAuthPage(mall_ui_page, settings.EPAK_AUTH_URL)
            auth_page.open()
            auth_page.assert_login_page_loaded()
            collector.save_screenshot(mall_ui_page, "01-epak-auth-login.png", full_page=False)
            collector.add_step("打开登录页", "pass", url=mall_ui_page.url)

        with allure.step("点击顶部 EPAK Logo 进入商城首页"):
            mall_page = auth_page.open_mall_home_in_new_tab()
            collector.add_step("进入商城首页", "pass", url=mall_page.url)

        home = EpakMallHomePage(mall_page, settings.EPAK_MALL_HOME_URL)
        with allure.step("校验商城首页关键模块"):
            home.assert_on_home()
            collector.save_screenshot(mall_page, "02-epak-mall-home-top.png", full_page=False)

        with allure.step("等待订阅弹窗加载并关闭"):
            popup_loaded = home.wait_for_subscribe_popup_loaded()
            collector.add_check("subscribe_popup", {"loaded": popup_loaded})
            if popup_loaded:
                collector.save_screenshot(mall_page, "03-epak-subscribe-popup.png", full_page=False)
                home.close_subscribe_popup()
            home.dismiss_cookie_banner_if_present()
            collector.add_step("关闭订阅弹窗", "pass", popup_loaded=popup_loaded)

        with allure.step("全页滚动检查首页元素与图片加载"):
            homepage_checks = home.assert_full_page_loaded(
                scroll_pause_ms=settings.ESB_UI_SCROLL_PAUSE_MS
            )
            collector.add_check("homepage", homepage_checks)
            collector.save_screenshot(mall_page, "04-epak-mall-home-one-stop.png", full_page=False)
            collector.add_step("首页全页检查", "pass", **homepage_checks)

        with allure.step("点击 One-Stop 专区任意商品并校验详情页"):
            product_name, mall_page = home.open_any_one_stop_product(
                preferred_name=settings.EPAK_UI_PRODUCT_KEYWORD or None
            )
            detail = EpakProductDetailPage(mall_page)
            detail_checks = detail.assert_detail_loaded()
            collector.add_check(
                "product_detail",
                {"clicked_product": product_name, **detail_checks},
            )
            collector.save_screenshot(mall_page, "05-epak-product-detail.png", full_page=False)
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
            collector.save_screenshot(active, "99-epak-failure.png", full_page=False)
        except Exception:
            pass
        raise
    finally:
        summary_path = collector.save(exitstatus=exitstatus)
        request.config._epak_ui_report_path = str(summary_path)
        send_ui_report_email(request.config, "EPAK 英文商城", summary_path)
