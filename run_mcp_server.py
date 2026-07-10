#!/usr/bin/env python3
"""AI Daily — MCP Server

标准 Model Context Protocol (MCP) Server。
所有 Tool 只读取本地数据，禁止联网。

支持客户端：
  - Hermes
  - Claude Desktop
  - Cursor
  - 任何 MCP 兼容客户端

启动方式：
  python3 run_mcp_server.py
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import load_config

logger = logging.getLogger("ai_daily.mcp")

CST = timezone(timedelta(hours=8))

# ── MCP Server ────────────────────────────────────────────────────────

server = Server("ai-daily")


# ── 工具函数 ──────────────────────────────────────────────────────────


def get_date_str() -> str:
    return datetime.now(CST).strftime("%Y-%m-%d")


def load_json(path: Path) -> dict | None:
    """加载 JSON 文件，不存在或损坏返回 None。"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def read_text(path: Path, max_chars: int = 0) -> str:
    """读取文本文件。"""
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
        if max_chars and len(text) > max_chars:
            text = text[:max_chars] + "..."
        return text
    except OSError:
        return ""


def load_items(source: str, date_str: str | None = None) -> list[dict]:
    """加载指定数据源和日期的 items。"""
    if date_str is None:
        date_str = get_date_str()
    path = PROJECT_ROOT / "storage" / source / "json" / f"{date_str}.json"
    data = load_json(path)
    if data and data.get("status") == "success":
        return data.get("items", [])
    return []


# ── Tool 定义 ──────────────────────────────────────────────────────────


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """返回所有可用工具列表。"""
    return [
        types.Tool(
            name="get_today_report",
            description="获取今日 AI Daily 日报（完整 Markdown）",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="get_history_report",
            description="获取指定日期的历史日报",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "日期，格式 YYYY-MM-DD（如 2026-07-10）",
                    }
                },
                "required": ["date"],
            },
        ),
        types.Tool(
            name="search_news",
            description="跨源搜索新闻（支持标题、关键词匹配）",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                    "date": {
                        "type": "string",
                        "description": "日期（可选，默认今天）",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大结果数（默认 10）",
                    },
                },
                "required": ["keyword"],
            },
        ),
        types.Tool(
            name="get_today_events",
            description="获取今日事件聚类结果（跨源合并的事件列表）",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_events": {
                        "type": "integer",
                        "description": "最大事件数（默认 10）",
                    },
                },
            },
        ),
        types.Tool(
            name="get_github_trending",
            description="获取 GitHub Trending 项目列表",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "日期（可选）"},
                    "max_items": {"type": "integer", "description": "最大条数"},
                },
            },
        ),
        types.Tool(
            name="get_hacker_news",
            description="获取 Hacker News 热门讨论",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "日期（可选）"},
                    "max_items": {"type": "integer", "description": "最大条数"},
                },
            },
        ),
        types.Tool(
            name="get_youtube_videos",
            description="获取 YouTube 最新 AI 视频",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "日期（可选）"},
                    "max_items": {"type": "integer", "description": "最大条数"},
                },
            },
        ),
        types.Tool(
            name="get_twitter_posts",
            description="获取 X (Twitter) 最新推文",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "日期（可选）"},
                    "max_items": {"type": "integer", "description": "最大条数"},
                },
            },
        ),
        types.Tool(
            name="get_china_ai",
            description="获取国产 AI 新闻",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "日期（可选）"},
                    "max_items": {"type": "integer", "description": "最大条数"},
                },
            },
        ),
        types.Tool(
            name="get_system_status",
            description="获取系统状态、采集统计、缓存使用情况",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


# ── Tool 处理 ──────────────────────────────────────────────────────────


def _format_items(items: list[dict], fields: list[str], max_items: int = 10) -> list[dict]:
    """格式化 items，只保留指定字段。"""
    result = []
    for item in items[:max_items]:
        row = {}
        for f in fields:
            val = item.get(f)
            # 从 raw 中取深层的值
            if val is None:
                raw = item.get("raw", {}) or {}
                val = raw.get(f)
            if val is not None:
                row[f] = val
        result.append(row)
    return result


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """处理 Tool 调用请求。"""
    date_str = arguments.get("date", get_date_str())
    max_items = arguments.get("max_items", 10)

    try:
        if name == "get_today_report":
            path = PROJECT_ROOT / "output" / get_date_str() / "daily_report.md"
            content = read_text(path)
            if not content:
                return [types.TextContent(type="text", text="今日日报尚未生成。请先运行 python run_daily.py")]
            return [types.TextContent(type="text", text=content)]

        elif name == "get_history_report":
            path = PROJECT_ROOT / "output" / date_str / "daily_report.md"
            content = read_text(path)
            if not content:
                return [types.TextContent(type="text", text=f"{date_str} 的日报不存在")]
            return [types.TextContent(type="text", text=content)]

        elif name == "search_news":
            keyword = arguments.get("keyword", "").lower()
            max_results = arguments.get("max_results", 10)
            results = []
            sources = ["hacker_news", "github_trending", "youtube", "twitter", "china_ai", "product_hunt"]
            for src in sources:
                items = load_items(src, date_str)
                for item in items:
                    title = (item.get("title", "") or "").lower()
                    desc = (item.get("description", "") or "").lower()
                    if keyword in title or keyword in desc:
                        results.append({
                            "source": src,
                            "title": item.get("title"),
                            "url": item.get("url"),
                            "score": item.get("raw_score"),
                        })
            results = results[:max_results]
            return [types.TextContent(
                type="text",
                text=json.dumps({"keyword": keyword, "total": len(results), "results": results},
                                ensure_ascii=False, indent=2),
            )]

        elif name == "get_today_events":
            max_events = arguments.get("max_events", 10)
            try:
                all_data = {}
                for src in ["hacker_news", "github_trending", "product_hunt", "youtube", "twitter", "china_ai"]:
                    items = load_items(src, date_str)
                    if items:
                        all_data[src] = items
                from reporter.event_cluster import EventCluster
                clusterer = EventCluster()
                events = clusterer.cluster(all_data)
                results = []
                for ev in events[:max_events]:
                    results.append({
                        "title": ev.title,
                        "sources": ev.sources,
                        "source_summary": ev.source_summary,
                        "total_score": ev.total_score,
                        "max_score": ev.max_score,
                        "item_count": ev.item_count,
                        "keywords": ev.top_keywords,
                    })
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"total_events": len(events), "events": results},
                                    ensure_ascii=False, indent=2),
                )]
            except Exception as e:
                return [types.TextContent(type="text", text=f"事件聚类失败: {e}")]

        elif name == "get_github_trending":
            items = load_items("github_trending", date_str)
            data = _format_items(items, ["title", "description", "raw_score", "url", "author"], max_items)
            return [types.TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]

        elif name == "get_hacker_news":
            items = load_items("hacker_news", date_str)
            data = _format_items(items, ["title", "author", "raw_score", "url", "published_at"], max_items)
            return [types.TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]

        elif name == "get_youtube_videos":
            items = load_items("youtube", date_str)
            data = _format_items(items, ["title", "author", "raw_score", "url", "published_at"], max_items)
            return [types.TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]

        elif name == "get_twitter_posts":
            items = load_items("twitter", date_str)
            data = _format_items(items, ["title", "author", "url", "published_at"], max_items)
            return [types.TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]

        elif name == "get_china_ai":
            items = load_items("china_ai", date_str)
            data = _format_items(items, ["title", "description", "url", "published_at", "author"], max_items)
            return [types.TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]

        elif name == "get_system_status":
            status = _get_system_status()
            return [types.TextContent(type="text", text=json.dumps(status, ensure_ascii=False, indent=2))]

        else:
            return [types.TextContent(type="text", text=f"未知工具: {name}")]

    except Exception as e:
        logger.exception("Tool %s failed: %s", name, e)
        return [types.TextContent(type="text", text=f"错误: {e}")]


def _get_system_status() -> dict:
    """获取系统状态统计。"""
    config = load_config()
    today = get_date_str()

    sources = ["github_trending", "hacker_news", "product_hunt", "youtube", "twitter", "china_ai"]
    source_status = {}
    total_items = 0

    for src in sources:
        items = load_items(src, today)
        cfg = config.get(src, {})
        enabled = cfg.get("enabled", True)
        source_status[src] = {
            "enabled": enabled,
            "items_today": len(items),
            "configured": src in config,
        }
        total_items += len(items)

    # 缓存统计
    cache_dir = PROJECT_ROOT / "cache"
    cache_size = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file()) if cache_dir.exists() else 0

    return {
        "version": "1.2.0",
        "today": today,
        "total_items": total_items,
        "source_count": len(sources),
        "sources": source_status,
        "cache_size_bytes": cache_size,
        "data_dir_size_bytes": sum(
            f.stat().st_size for f in (PROJECT_ROOT / "storage").rglob("*") if f.is_file()
        ) if (PROJECT_ROOT / "storage").exists() else 0,
    }


# ── 启动 ──────────────────────────────────────────────────────────────


async def main():
    """启动 MCP Server（stdio 模式）。"""
    logger.info("AI Daily MCP Server starting...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())
