from utils.mall_ui_report import (
    MallUiReportCollector,
    latest_mall_report_dir,
    ui_report_attachments,
)

EsbaoUiReportCollector = MallUiReportCollector
latest_esbao_report_dir = latest_mall_report_dir


def latest_esbao_attachments(report_parent, summary_path):
    report_dir = latest_mall_report_dir(report_parent)
    if report_dir is None:
        return [summary_path] if summary_path.exists() else []
    return ui_report_attachments(report_dir, summary_path)
