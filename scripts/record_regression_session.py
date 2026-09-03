#!/usr/bin/env python
"""CRM Web 可控录制会话：同时抓 UI 操作与 Network，生成回归用例草稿。

用法:
  python scripts/record_regression_session.py
  python scripts/record_regression_session.py --title create_lead
  python scripts/record_regression_session.py --start-url https://test-platform.ysbpack.com/

流程:
  1. 打开浏览器（默认进登录页）
  2. 你先登录 / 切到要测的页面
  3. 终端按 Enter -> 开始录制
  4. 按回归路径操作一遍
  5. 终端再按 Enter -> 停止并生成草稿
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from recording.session import RegressionSessionRecorder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CRM Web 回归录制：可控开始/停止，输出 UI + 主接口用例草稿",
    )
    parser.add_argument(
        "--title",
        default="crm_session",
        help="会话标题，用于草稿文件名（默认 crm_session）",
    )
    parser.add_argument(
        "--start-url",
        default=None,
        help="起始 URL，默认登录页（BASE_URL + LOGIN_PATH）",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="强制有头模式打开浏览器（忽略 HEADLESS=true）",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    headless = False if args.headed else None
    recorder = RegressionSessionRecorder(
        title=args.title,
        start_url=args.start_url,
        headless=headless,
    )

    print("=" * 60)
    print("CRM 回归录制会话")
    print(f"会话目录: {recorder.session_dir}")
    print(f"起始地址: {recorder.start_url}")
    print("=" * 60)

    meta = None
    try:
        recorder.open_browser()
        print("\n浏览器已打开。请先完成登录并进入要测的业务页。")
        print("（等待期间会持续处理浏览器事件，新页签可正常跳转）")
        recorder.wait_until_enter("准备好后，按 Enter 开始录制... ")

        recorder.start_recording()
        print("\n>>> 录制中：请按回归路径操作。完成后回到终端。")
        recorder.wait_until_enter("操作完成，按 Enter 停止录制并生成草稿... ")

        recorder.stop_recording()
        print("正在保存流量并生成草稿...")
        recorder.close()
        meta = recorder.save_and_generate()
    except KeyboardInterrupt:
        print("\n[录制] 已中断，尝试保存已捕获数据...")
        try:
            recorder.stop_recording()
            recorder.close()
            meta = recorder.save_and_generate()
        except Exception as exc:
            print(f"[错误] 中断后保存失败: {exc}")
            return 1
    except Exception as exc:
        print(f"[错误] 录制失败: {exc}")
        try:
            recorder.close()
        except Exception:
            pass
        return 1

    if not meta:
        return 1

    print("\n生成完成:")
    print(f"  UI 操作: {meta['action_count']}")
    print(f"  接口总数: {meta['call_count']}")
    print(f"  主接口: {meta['main_api_count']}")
    print(f"  UI 草稿: {meta['ui_draft']}")
    print(f"  API 草稿: {meta['api_draft']}")
    print(f"  摘要: {meta['summary']}")
    print("\n请先人工复核 drafts/，确认后再迁入 tests/ 纳入日常回归。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
