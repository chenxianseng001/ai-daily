#!/usr/bin/env python3
"""AI Daily — Reporter 入口

由 run_daily.py 或 Hermes Cron Job 触发。

使用 ReportBuilder 生成完整日报：
  - 模块化 Section 架构
  - 自动目录
  - 今日 AI 三件大事
  - 今日值得关注
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import load_config
from core.logger import setup_logger
from reporter.report_builder import build_report, get_date_str

logger = setup_logger("ai_daily.reporter", log_file=Path("logs/reporter.log"))


def save_report(content: str, date_str: str, output_dir: str = "output") -> Path:
    """保存日报到 output/ 目录。"""
    out_path = PROJECT_ROOT / output_dir / date_str
    out_path.mkdir(parents=True, exist_ok=True)
    output_file = out_path / "daily_report.md"
    output_file.write_text(content, encoding="utf-8")
    logger.info("Report saved to %s (%d chars)", output_file, len(content))
    return output_file


def run() -> str:
    """执行 Reporter 生成日报。

    Returns:
        日报 Markdown 字符串
    """
    config = load_config()
    date_str = get_date_str()
    logger.info("Generating report for %s", date_str)

    # 从配置构建 reporter 参数
    reporter_cfg = {}
    for source_key in ("github_trending", "hacker_news", "product_hunt"):
        src_cfg = config.get(source_key, {})
        if src_cfg.get("enabled", True):
            if source_key == "github_trending":
                reporter_cfg["github_show_all"] = src_cfg.get("show_all", True)
                reporter_cfg["github_max_items"] = src_cfg.get("max_items", 15)
            elif source_key == "hacker_news":
                reporter_cfg["hn_max_items"] = src_cfg.get("max_items", 10)
            elif source_key == "product_hunt":
                reporter_cfg["ph_max_items"] = src_cfg.get("show_top", 10)
            elif source_key == "youtube":
                reporter_cfg["youtube_max_items"] = src_cfg.get("max_items", 10)
            elif source_key == "twitter":
                reporter_cfg["twitter_max_items"] = src_cfg.get("max_items", 10)
            elif source_key == "china_ai":
                reporter_cfg["china_ai_max_items"] = src_cfg.get("max_items", 10)

    report = build_report(date_str=date_str, config=reporter_cfg)
    output_dir = config.get("reporter", {}).get("output_dir", "output")
    save_report(report, date_str, output_dir)

    print(report)
    logger.info("Report done")
    return report


if __name__ == "__main__":
    run()
