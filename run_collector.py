#!/usr/bin/env python3
"""AI Daily — Collector 入口

由 run_daily.py 或 Hermes Cron Job 触发。

职责:
  1. 加载统一配置
  2. 按配置决定哪些数据源启用
  3. 并行执行所有启用的 Collector
  4. 更新 state（成功/失败/自动禁用）
  5. 记录日志
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from collectors.base_collector import CollectorStateManager
from collectors.github_trending import GithubTrendingCollector
from collectors.hacker_news import HackerNewsCollector
from collectors.product_hunt import ProductHuntCollector
from collectors.youtube import YouTubeCollector
from collectors.twitter import TwitterCollector
from collectors.china_ai import ChinaAICollector
from core.config import load_config, is_source_enabled, get_source_config
from core.logger import setup_logger

# ── 配置 ──────────────────────────────────────────────────────────────

LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "collector.log"

# 连续失败自动禁用阈值
MAX_CONSECUTIVE_FAILURES = 3


# ── Collector 工厂 ────────────────────────────────────────────────────
# 根据配置初始化 Collector 实例


def create_collectors(config: dict) -> dict:
    """根据配置创建启用的 Collector 字典。"""
    collectors: dict = {}

    if is_source_enabled(config, "github_trending"):
        src_cfg = get_source_config(config, "github_trending")
        collectors["github_trending"] = GithubTrendingCollector(
            token=src_cfg.get("token") or None,
            max_concurrent=src_cfg.get("max_concurrent", 5),
        )

    if is_source_enabled(config, "hacker_news"):
        collectors["hacker_news"] = HackerNewsCollector()

    if is_source_enabled(config, "product_hunt"):
        src_cfg = get_source_config(config, "product_hunt")
        collectors["product_hunt"] = ProductHuntCollector(
            token=src_cfg.get("token") or None,
        )

    if is_source_enabled(config, "youtube"):
        collectors["youtube"] = YouTubeCollector()

    if is_source_enabled(config, "twitter"):
        src_cfg = get_source_config(config, "twitter")
        collectors["twitter"] = TwitterCollector(
            bearer_token=src_cfg.get("bearer_token") or None,
        )

    if is_source_enabled(config, "china_ai"):
        collectors["china_ai"] = ChinaAICollector()

    return collectors


# ── 主流程 ────────────────────────────────────────────────────────────


def run() -> dict:
    """执行所有 Collector 采集。

    Returns:
        采集结果字典 {source_name: CollectorResult}
    """
    config = load_config()
    logger = setup_logger(
        "ai_daily.collector",
        level=getattr(logging, config.get("global", {}).get("log_level", "INFO")),
        log_file=LOG_FILE,
        console=True,
    )

    logger.info("=" * 60)
    logger.info("AI Daily Collector — Start")
    logger.info("=" * 60)

    collectors = create_collectors(config)
    state_mgr = CollectorStateManager()
    state = state_mgr.load()

    if not collectors:
        logger.warning("No collectors enabled in config")
        return {}

    results = {}
    for source_name, collector in collectors.items():
        src_state = state.get("sources", {}).get(source_name, {})
        con_fail = src_state.get("consecutive_failures", 0)

        if con_fail >= MAX_CONSECUTIVE_FAILURES:
            logger.warning(
                "[%s] Skipped: %d consecutive failures (max %d)",
                source_name, con_fail, MAX_CONSECUTIVE_FAILURES,
            )
            continue

        if not collector.should_collect(src_state):
            logger.info("[%s] Already collected today, skipped", source_name)
            continue

        logger.info("[%s] Starting collection...", source_name)
        try:
            result = collector.collect(src_state)
            results[source_name] = result

            if result.status == "success":
                state_mgr.update_source(source_name, {
                    **result.state_update,
                    "consecutive_failures": 0,
                })
                logger.info(
                    "[%s] Done: %d items in %.1fs",
                    source_name, result.item_count, result.execution_seconds,
                )
            else:
                new_con_fail = con_fail + 1
                state_mgr.update_source(source_name, {
                    **result.state_update,
                    "consecutive_failures": new_con_fail,
                })
                logger.error(
                    "[%s] Failed (attempt %d/%d): %s",
                    source_name, new_con_fail, MAX_CONSECUTIVE_FAILURES,
                    result.error,
                )
                if new_con_fail >= MAX_CONSECUTIVE_FAILURES:
                    state_mgr.mark_disabled(source_name)
                    logger.warning(
                        "[%s] Auto-disabled after %d consecutive failures",
                        source_name, new_con_fail,
                    )

        except Exception as e:
            logger.exception("[%s] Unexpected error: %s", source_name, e)

    # 汇总
    success_count = sum(
        1 for r in results.values() if r.status == "success"
    )
    total_items = sum(r.item_count for r in results.values())
    logger.info("=" * 60)
    logger.info(
        "Summary: %d/%d collectors done, %d items total",
        success_count, len(collectors), total_items,
    )
    logger.info("AI Daily Collector — End")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    run()
