from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import allure

from config import settings
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

    @property
    def email_report_label(self) -> str:
        return f"{self.email_label}UI巡检"


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
        send_ui_report_email(
            request.config,
            site.email_label,
            summary_path,
            report_label=site.email_report_label,
        )
