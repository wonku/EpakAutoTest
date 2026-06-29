from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import allure
import pytest

from config import settings
from pages.esbao_auth_page import EsbaoAuthPage
from pages.esbao_mall_home_page import EsbaoMallHomePage
from pages.esbao_product_detail_page import EsbaoProductDetailPage
from pages.epak_auth_page import EpakAuthPage
from pages.epak_mall_home_page import EpakMallHomePage
from pages.epak_product_detail_page import EpakProductDetailPage
from utils.mall_ui_report import MallUiReportCollector
from utils.ui_report_email import send_ui_report_email


@dataclass(frozen=True)
class MallInspectionSite:
    site_id: str
    feature: str
    story: str
    title: str
    email_label: str
    report_dir: Path
    suite_name: str
    config_report_attr: str
    auth_url: str
    home_url: str
    screenshot_prefix: str
    auth_page_factory: Callable
    home_page_factory: Callable
    detail_page_factory: Callable
    open_product: Callable
    pre_home_checks: Callable | None = None


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
    pre_home_checks=lambda home, collector, mall_page, prefix: _epak_pre_home_checks(
        home, collector, mall_page, prefix
    ),
)


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


def _make_collector(site: MallInspectionSite) -> MallUiReportCollector:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return MallUiReportCollector(
        report_root=site.report_dir / timestamp,
        suite=site.suite_name,
    )


def run_mall_inspection(mall_ui_page, site: MallInspectionSite, request) -> None:
    collector = _make_collector(site)
    mall_page = mall_ui_page
    exitstatus = 0
    prefix = site.screenshot_prefix

    try:
        with allure.step(f"打开 {site.auth_url} 登录页"):
            auth_page = site.auth_page_factory(mall_ui_page, site.auth_url)
            auth_page.open()
            auth_page.assert_login_page_loaded()
            collector.save_screenshot(
                mall_ui_page, f"01-{prefix}-auth-login.png", full_page=False
            )
            collector.add_step("打开登录页", "pass", url=mall_ui_page.url)

        with allure.step("点击顶部 Logo 进入商城首页"):
            mall_page = auth_page.open_mall_home_in_new_tab()
            collector.add_step("进入商城首页", "pass", url=mall_page.url)

        home = site.home_page_factory(mall_page, site.home_url)
        with allure.step("校验商城首页关键模块"):
            home.assert_on_home()
            collector.save_screenshot(
                mall_page, f"02-{prefix}-mall-home-top.png", full_page=False
            )

        if site.pre_home_checks:
            site.pre_home_checks(home, collector, mall_page, prefix)

        with allure.step("全页滚动检查首页元素与图片加载"):
            homepage_checks = home.assert_full_page_loaded(
                scroll_pause_ms=settings.ESB_UI_SCROLL_PAUSE_MS
            )
            collector.add_check("homepage", homepage_checks)
            section_shot = (
                f"03-{prefix}-mall-home-hot-section.png"
                if site.site_id == "esbao"
                else f"04-{prefix}-mall-home-one-stop.png"
            )
            collector.save_screenshot(mall_page, section_shot, full_page=False)
            collector.add_step("首页全页检查", "pass", **homepage_checks)

        with allure.step("点击商品并校验详情页"):
            product_name, mall_page = site.open_product(home)
            detail = site.detail_page_factory(mall_page)
            detail_checks = detail.assert_detail_loaded()
            collector.add_check(
                "product_detail",
                {"clicked_product": product_name, **detail_checks},
            )
            detail_shot = (
                f"04-{prefix}-product-detail.png"
                if site.site_id == "esbao"
                else f"05-{prefix}-product-detail.png"
            )
            collector.save_screenshot(mall_page, detail_shot, full_page=False)
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
            collector.save_screenshot(active, f"99-{prefix}-failure.png", full_page=False)
        except Exception:
            pass
        raise
    finally:
        summary_path = collector.save(exitstatus=exitstatus)
        setattr(request.config, site.config_report_attr, str(summary_path))
        send_ui_report_email(request.config, site.email_label, summary_path)

