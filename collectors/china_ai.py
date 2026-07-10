"""AI Daily — 国产 AI Collector

采集中国 AI 媒体和企业的官方动态。

数据源策略：
  ① RSS 优先（量子位、36Kr、少数派等）
  ② 页面解析降级（无 RSS 的源）

所有文章正文保存到 raw，Collector 不生成摘要。
"""

from __future__ import annotations

import html
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import yaml

from collectors.base_collector import (
    BaseCollector,
    CollectorResult,
    build_state_update,
    get_date_str,
    make_collector_result,
)
from core.http_client import build_session, fetch_url

logger = logging.getLogger("ai_daily.china_ai")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_sources() -> dict:
    """加载国产 AI 源配置。"""
    path = PROJECT_ROOT / "config" / "china_ai_sources.yaml"
    if not path.exists():
        logger.warning("[china_ai] china_ai_sources.yaml not found")
        return {"media_sources": [], "enterprise_sources": []}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


class ChinaAICollector(BaseCollector):
    """国产 AI 新闻采集器。"""

    @property
    def source_name(self) -> str:
        return "china_ai"

    def __init__(self):
        self.session = build_session()

    def collect(self, state: dict) -> CollectorResult:
        start_time = time.time()
        date_str = get_date_str()
        all_raw_files: list[str] = []
        all_items: list[dict] = []

        config = load_sources()
        media_sources = [
            s for s in config.get("media_sources", [])
            if s.get("enabled", True)
        ]

        if not media_sources:
            return self._empty_result(start_time, date_str)

        logger.info("[china_ai] %d media sources", len(media_sources))

        # 从 state 获取 hash 去重
        src_state = state or {}
        seen_hashes = set(src_state.get("seen_hashes", []))

        for source in media_sources:
            sid = source["id"]
            sname = source["name"]
            stype = source.get("type", "rss")

            try:
                if stype == "rss":
                    articles = self._fetch_rss(source, seen_hashes)
                else:
                    continue

                if not articles:
                    logger.info("[china_ai] %s: no new articles", sname)
                    continue

                for article in articles:
                    item, raw_files = self._build_article_item(
                        article, sname, date_str,
                    )
                    if item:
                        all_items.append(item)
                        all_raw_files.extend(raw_files)
                        seen_hashes.add(article.get("hash", ""))

                logger.info(
                    "[china_ai] %s: %d articles", sname, len(articles),
                )

            except Exception as e:
                logger.warning("[china_ai] %s error: %s", sname, e)
                continue

        if not all_items:
            return self._empty_result(start_time, date_str)

        json_path = self.write_json(all_items, date_str)

        logger.info(
            "[china_ai] Done: %d articles in %.1fs",
            len(all_items), time.time() - start_time,
        )

        return make_collector_result(
            source=self.source_name,
            status="success",
            items=all_items,
            json_path=str(json_path),
            raw_files=all_raw_files,
            state_update={
                "status": "success",
                "last_item_id": all_items[-1].get("id", ""),
                "last_item_count": len(all_items),
                "seen_hashes": list(seen_hashes)[-500:],  # 保留最近 500 个 hash
            },
            start_time=start_time,
        )

    def _empty_result(self, start_time: float, date_str: str) -> CollectorResult:
        return make_collector_result(
            source=self.source_name,
            status="success",
            items=[],
            json_path=str(self.today_json_path(date_str)),
            raw_files=[],
            state_update=build_state_update(
                status="success", last_item_id="", item_count=0,
            ),
            start_time=start_time,
        )

    # ── RSS 采集 ───────────────────────────────────────────────────────

    def _fetch_rss(
        self, source: dict, seen_hashes: set,
    ) -> list[dict]:
        """通过 RSS 获取文章列表。"""
        rss_url = source.get("rss")
        sid = source["id"]
        filter_kw = source.get("filter_keyword", "")

        if not rss_url:
            return []

        result = fetch_url(rss_url, session=self.session)
        if result.failed:
            logger.warning("[china_ai] RSS %s: %s", rss_url, result.error)
            return []

        try:
            root = ET.fromstring(result.data.text)
        except ET.ParseError as e:
            logger.warning("[china_ai] RSS parse %s: %s", sid, e)
            return []

        # 处理标准 RSS 和 Atom 格式
        items = []
        # RSS 2.0: channel → item
        for item in root.findall(".//channel/item"):
            items.append(item)
        # Atom: entry
        if not items:
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            if not items:
                # Try without namespace
                items = root.findall("entry")

        articles = []
        for item in items:
            article = self._parse_rss_item(item, sid)
            if not article:
                continue

            # 关键词过滤
            if filter_kw and filter_kw.lower() not in article.get("title", "").lower():
                continue

            # URL 去重
            article_hash = article.get("hash", "")
            if article_hash in seen_hashes:
                continue

            articles.append(article)

        return articles

    def _parse_rss_item(self, item, source_id: str) -> dict | None:
        """解析单个 RSS item，返回统一字典。"""
        title = self._get_text(item, "title")
        link = self._get_text(item, "link")
        pubdate = self._get_text(item, "pubDate") or self._get_text(item, "published")
        author = self._get_text(item, "author") or self._get_text(item, "dc:creator")
        description = self._get_text(item, "description")

        if not title:
            return None

        # 提取文章 ID
        guid = self._get_text(item, "guid")
        if not guid and link:
            # 从 URL 提取 ID
            guid = link.split("/")[-1].split(".")[0] if link else ""
        if not guid:
            guid = title[:50]

        article_id = f"{source_id}:{guid}"

        # 计算 hash
        import hashlib
        content_hash = hashlib.md5(
            f"{title}{link}".encode()
        ).hexdigest()

        # 清理 description 中的 HTML
        desc_text = ""
        if description:
            desc_text = html.unescape(description)
            desc_text = re.sub(r"<[^>]+>", " ", desc_text)
            desc_text = re.sub(r"\s+", " ", desc_text).strip()

        return {
            "id": article_id,
            "title": title,
            "link": link or "",
            "published_at": self._parse_date(pubdate),
            "author": author or "",
            "description": desc_text[:500] if desc_text else "",
            "full_html": description or "",
            "hash": content_hash,
        }

    @staticmethod
    def _get_text(element, tag: str) -> str | None:
        """从 XML 元素中获取文本，支持带 namespace 的标签。"""
        # 尝试直接查找
        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()

        # 尝试带 namespace
        for child in element.iter():
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if local == tag and child.text:
                return child.text.strip()

        return None

    @staticmethod
    def _parse_date(date_str: str | None) -> str | None:
        """解析日期为 ISO 格式。"""
        if not date_str:
            return None
        from email.utils import parsedate_to_datetime
        try:
            dt = parsedate_to_datetime(date_str)
            return dt.isoformat()
        except (ValueError, TypeError):
            pass
        try:
            from dateutil.parser import parse as dt_parse
            return dt_parse(date_str).isoformat()
        except Exception:
            return date_str[:10]

    # ── Item 构造 ─────────────────────────────────────────────────────

    def _build_article_item(
        self, article: dict, source_name: str, date_str: str,
    ) -> tuple[dict | None, list[str]]:
        """构造标准 CollectionItem。"""
        raw_files: list[str] = []

        # 保存文章正文到 raw
        if article.get("full_html"):
            content = article["full_html"]
        else:
            content = article.get("description", "")

        raw_path = None
        if content:
            # 安全的文件名
            safe_name = article["id"].replace(":", "_").replace("/", "_").replace("?", "_")
            safe_name = re.sub(r'[^\w\-_]', '_', safe_name)
            raw_filename = f"{safe_name}_content.md"
            raw_path = self.write_raw(raw_filename, content, date_str)
            raw_files.append(str(raw_path))

        raw_dict: dict[str, Any] = {
            "article_id": article["id"],
            "source_site": source_name,
            "link": article.get("link", ""),
            "content_path": str(raw_path) if content else None,
            "full_html": bool(article.get("full_html")),
        }

        ai_item = self.build_item(
            item_id=article["id"],
            title=article.get("title", ""),
            description=article.get("description"),
            author=article.get("author"),
            published_at=article.get("published_at"),
            url=article.get("link", ""),
            raw_score=0,
            language="zh",
            category="news",
            tags=[source_name],
            raw=raw_dict,
        )

        return ai_item, raw_files
