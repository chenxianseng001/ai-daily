#!/usr/bin/env python3
"""AI Daily — 统一运行入口

一个命令完成整套流程：
  Collector → Reporter → 日报输出

用法:
  python3 run_daily.py              # 完整运行
  python3 run_daily.py --collect    # 仅采集
  python3 run_daily.py --report     # 仅生成日报
  python3 run_daily.py --date 2026-07-10  # 指定日期
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import load_config
from core.logger import setup_logger

logger = setup_logger("ai_daily.runner", log_file=Path("logs/runner.log"))


def parse_args():
    parser = argparse.ArgumentParser(
        description="AI Daily — 统一运行入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 run_daily.py                 完整运行（采集 → 报告）
  python3 run_daily.py --collect       仅采集
  python3 run_daily.py --report        仅生成报告（使用已有缓存）
  python3 run_daily.py --date 2026-07-10  指定日期（重跑报告）
        """,
    )
    parser.add_argument(
        "--collect",
        action="store_true",
        help="仅执行采集，不生成报告",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="仅生成报告（使用已有缓存，需先执行采集）",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="指定日期（YYYY-MM-DD），默认今天",
    )
    parser.add_argument(
        "--no-delivery",
        action="store_true",
        help="不投递到飞书",
    )
    return parser.parse_args()


def run():
    args = parse_args()
    config = load_config()

    logger.info("=" * 60)
    logger.info("AI Daily — Run")
    logger.info("=" * 60)

    # 默认：先采集，再报告
    if args.report:
        # 仅报告 + 投递
        from run_reporter import run as run_reporter
        run_reporter()
        if not args.no_delivery:
            logger.info("Phase 3: Delivering to Feishu...")
            from reporter.delivery.feishu import deliver
            try:
                deliver(date_str=args.date)
            except Exception as e:
                logger.warning("Delivery failed (non-fatal): %s", e)
    elif args.collect:
        # 仅采集
        from run_collector import run as run_collector
        run_collector()
    else:
        # 完整流程
        logger.info("Phase 1: Collecting...")
        from run_collector import run as run_collector
        results = run_collector()

        success_count = sum(
            1 for r in results.values() if r.status == "success"
        )
        total_items = sum(r.item_count for r in results.values())
        logger.info(
            "Collect done: %d sources, %d items", success_count, total_items
        )

        logger.info("")
        logger.info("Phase 2: Generating report...")
        from run_reporter import run as run_reporter
        run_reporter()

        # Phase 3: 投递到飞书
        if not args.no_delivery:
            logger.info("Phase 3: Delivering to Feishu...")
            from reporter.delivery.feishu import deliver
            try:
                deliver(date_str=args.date)
            except Exception as e:
                logger.warning("Delivery failed (non-fatal): %s", e)

    logger.info("=" * 60)
    logger.info("AI Daily — Done")
    logger.info("=" * 60)


if __name__ == "__main__":
    run()
