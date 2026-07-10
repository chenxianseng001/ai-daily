"""AI Daily — Report Builder

报告生成器，负责：
  1. 加载所有数据源缓存
  2. 路由到对应 Section 渲染
  3. 生成目录（TOC）
  4. 生成《今日 AI 三件大事》总结
  5. 生成《今日值得关注》推荐
  6. 组合最终 Markdown
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from reporter.base_section import BaseSection
from reporter.sections.github_section import GitHubSection
from reporter.sections.hacker_news_section import HackerNewsSection
from reporter.sections.product_hunt_section import ProductHuntSection
from reporter.sections.youtube_section import YouTubeSection
from reporter.sections.twitter_section import TwitterSection
from reporter.sections.china_ai_section import ChinaAISection

logger = logging.getLogger("ai_daily.reporter")

CST = timezone(timedelta(hours=8))

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Section 注册表 ────────────────────────────────────────────────────
# 新增数据源只需在此注册：name → Section 实例

SECTIONS: list[BaseSection] = [
    ChinaAISection(),
    TwitterSection(),
    YouTubeSection(),
    ProductHuntSection(),
    HackerNewsSection(),
    GitHubSection(),
]

# ── 默认配置 ──────────────────────────────────────────────────────────

DEFAULT_CONFIG: dict[str, Any] = {
    "hn_max_items": 10,
    "github_show_all": True,
    "github_max_items": 15,
}

# ── 日期工具 ──────────────────────────────────────────────────────────


def get_date_str() -> str:
    return datetime.now(CST).strftime("%Y-%m-%d")


def load_source(date_str: str, source: str) -> dict | None:
    """加载指定数据源的 JSON。"""
    json_path = PROJECT_ROOT / "storage" / source / "json" / f"{date_str}.json"
    if not json_path.exists():
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


# ── TOC 生成 ──────────────────────────────────────────────────────────


def generate_toc(active_sections: list[tuple[str, str]]) -> str:
    """生成目录。

    Args:
        active_sections: [(display_name, anchor_id), ...]
    """
    lines = []
    lines.append("## 📋 目录\n")
    for name, anchor in active_sections:
        lines.append(f"- [{name}](#{anchor})")
    lines.append("")
    return "\n".join(lines)


# ── 今日 AI 三件大事（基于事件聚类） ──────────────────────────────────


def generate_top3(all_data: dict[str, list[dict]]) -> str:
    """基于事件聚类，输出跨源聚合的今日三件大事。"""
    from reporter.event_cluster import EventCluster

    clusterer = EventCluster()
    events = clusterer.cluster(all_data)

    # 过滤：优先选涉及多个来源的事件，再按热度排序
    cross_source = [e for e in events if e.source_count >= 2]
    top_events = cross_source[:3] if cross_source else events[:3]

    lines = []
    lines.append("## 🏆 今日 AI 三件大事\n")

    for rank, event in enumerate(top_events, 1):
        title = event.title
        source_str = event.source_summary
        score_str = ""
        if event.max_score > 0:
            score_str = f" 🔥 {event.max_score:,}"

        lines.append(f"**{rank}. {title}**")
        lines.append(f"📡 {source_str}{score_str}")
        if event.top_keywords:
            lines.append(f"🏷️ {' · '.join(event.top_keywords[:4])}")
        lines.append("")

    if not cross_source:
        lines.append("> 今日各数据源事件独立性较强，未发现跨源大事件。")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


# ── 今日值得关注（基于事件聚类） ──────────────────────────────────────


def generate_recommendations(all_data: dict[str, list[dict]]) -> str:
    """推荐今日最值得关注的事件。"""
    from reporter.event_cluster import EventCluster

    clusterer = EventCluster()
    events = clusterer.cluster(all_data)

    lines = []
    lines.append("## ⭐ 今日值得关注\n")

    # 按综合热度排序
    events.sort(key=lambda e: (e.source_count, e.max_score, e.total_score), reverse=True)

    # 跨源事件推荐
    cross_source = [e for e in events if e.source_count >= 2]
    if cross_source:
        lines.append("### 🔥 跨源热点\n")
        for event in cross_source[:3]:
            lines.append(
                f"**{event.title[:80]}** — "
                f"{event.source_summary}, 热度 {event.max_score:,}"
            )
            if event.description:
                lines.append(f"> {event.description[:200]}")
            lines.append("")

    # 单源高热度推荐
    single_source = [e for e in events if e.source_count < 2]
    if single_source:
        lines.append("### 📊 各源热门\n")
        for event in single_source[:3]:
            source = event.sources[0] if event.sources else "?"
            lines.append(
                f"**[{source}]** {event.title[:80]} — "
                f"热度 {event.max_score:,}"
            )
            lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


# ── AI 摘要 ───────────────────────────────────────────────────────────


SUMMARY_ENABLED = True
"""全局开关：是否启用 AI 摘要。"""


def _generate_summaries(all_data: dict[str, list[dict]], cfg: dict) -> None:
    """为所有数据源的 items 生成 AI 摘要。

    将摘要注入到 item["_ai_summary"] 中。
    """
    if not SUMMARY_ENABLED:
        return

    from reporter.summary.generator import SummaryGenerator

    # 从配置获取 summary 设置
    summary_cfg = cfg.get("summary", {})
    if not summary_cfg.get("api_key"):
        # 从环境变量读取
        import os
        summary_cfg["api_key"] = os.environ.get("AI_SUMMARY_API_KEY", "")

    if not summary_cfg.get("api_key"):
        logger.info("[summary] No API key configured, skipping AI summaries")
        return

    generator = SummaryGenerator(summary_cfg)

    total = 0
    for source, items in all_data.items():
        for item in items:
            summary = generator.summarize(item, source)
            if summary:
                item["_ai_summary"] = summary
                total += 1

    stats = generator.stats()
    logger.info(
        "[summary] Generated %d summaries (cached=%d, new=%d, failed=%d, hit_rate=%.0f%%)",
        stats["total"], stats["cached"], stats["generated"],
        stats["failed"], stats["hit_rate"],
    )


# ── 主构建器 ──────────────────────────────────────────────────────────


def build_report(
    date_str: str | None = None,
    config: dict | None = None,
) -> str:
    """构建完整日报。

    Args:
        date_str: 日期，默认今天
        config: 配置字典，覆盖 DEFAULT_CONFIG

    Returns:
        完整日报 Markdown
    """
    if date_str is None:
        date_str = get_date_str()

    cfg = {**DEFAULT_CONFIG, **(config or {})}

    # 从 reporter 配置读取 UX 设置
    reporter_cfg = cfg.get("reporter", {})
    cfg["show_links"] = reporter_cfg.get("show_links", False)
    cfg["summary_length"] = reporter_cfg.get("summary_length", "medium")
    cfg["show_why_it_matters"] = reporter_cfg.get("show_why_it_matters", True)

    # 1. 加载所有数据
    all_data: dict[str, list[dict]] = {}
    source_status: dict[str, str] = {}
    active_sections: list[tuple[str, str]] = []

    for section in SECTIONS:
        source = section.source_name
        raw = load_source(date_str, source)
        if raw is None:
            source_status[source] = "no_cache"
            all_data[source] = []
        else:
            source_status[source] = raw.get("status", "error")
            all_data[source] = raw.get("items", [])

    # 1b. 生成 AI 摘要
    _generate_summaries(all_data, cfg)

    # 2. 渲染各 Section
    section_outputs: dict[str, str] = {}
    for section in SECTIONS:
        src = section.source_name
        items = all_data.get(src, [])
        status = source_status.get(src, "no_cache")

        if status != "success":
            badge = section.status_badge(status)
            section_outputs[src] = (
                f"## {badge} {section.name}\n\n"
                f"采集状态: {status}\n"
            )
            # 即使采集失败也加入 TOC（标注状态）
            active_sections.append((f"{badge} {section.name}", src))
        else:
            rendered = section.render(items, cfg)
            if rendered:
                section_outputs[src] = rendered
                active_sections.append((section.name, src))

    # 3. 组装最终报告
    lines: list[str] = []
    lines.append(f"# 🤖 AI Daily Report — {date_str}")
    lines.append("")
    lines.append("> 📡 **6 个数据源** · 自动采集 · AI 驱动")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(generate_toc(active_sections))
    lines.append("---")
    lines.append("")
    lines.append(generate_top3(all_data))
    lines.append(generate_recommendations(all_data))

    for _name, anchor in active_sections:
        content = section_outputs.get(anchor, "")
        if content:
            lines.append(content)

    return "\n".join(lines)
