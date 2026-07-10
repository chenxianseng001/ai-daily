"""AI Daily — Hacker News Collector

采集 Hacker News 的 Top / Best / New Stories。
使用官方 Firebase API，不依赖网页爬取。

输出符合 AI Daily Data Contract v1.0 的统一 JSON。
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from collectors.base_collector import (
    BaseCollector,
    build_state_update,
    get_date_str,
    make_collector_result,
)
from core.http_client import build_session, fetch_url

logger = logging.getLogger("ai_daily.hacker_news")

# ── 常量 ──────────────────────────────────────────────────────────────

API_BASE = "https://hacker-news.firebaseio.com/v0"
MAX_TOP = 30       # Top Stories 取前 30
MAX_BEST = 30      # Best Stories 取前 30
MAX_NEW = 30       # New Stories 取前 30
MAX_TOTAL = 60     # 去重后最多保留 60 条

# 不需要下载正文的域名白名单
SKIP_DOMAINS = {
    "twitter.com", "x.com", "youtube.com", "www.youtube.com",
    "github.com", "news.ycombinator.com",
}


class HackerNewsCollector(BaseCollector):
    """Hacker News 采集器。

    使用示例:
        collector = HackerNewsCollector()
        result = collector.collect(state)
    """

    @property
    def source_name(self) -> str:
        return "hacker_news"

    def __init__(self):
        self.session = build_session()

    # ── 主入口 ─────────────────────────────────────────────────────────

    def collect(self, state: dict) -> CollectorResult:
        start_time = time.time()
        date_str = get_date_str()
        all_raw_files: list[str] = []

        # ── 1. 获取三类故事的 ID 列表 ──────────────────────────────
        logger.info("[hacker_news] Fetching story IDs...")

        top_ids = self._fetch_ids("topstories", MAX_TOP)
        best_ids = self._fetch_ids("beststories", MAX_BEST)
        new_ids = self._fetch_ids("newstories", MAX_NEW)

        if top_ids is None and best_ids is None and new_ids is None:
            return make_collector_result(
                source=self.source_name,
                status="error",
                items=[],
                json_path="",
                raw_files=[],
                error="All HN API endpoints failed",
                state_update=build_state_update(
                    status="error",
                    error="All HN API endpoints failed",
                    consecutive_failures=state.get("consecutive_failures", 0) + 1,
                ),
                start_time=start_time,
            )

        # 合并、去重、排序（最新的优先）
        all_ids: list[int] = list(set(
            (top_ids or []) + (best_ids or []) + (new_ids or [])
        ))
        all_ids.sort(reverse=True)
        all_ids = all_ids[:MAX_TOTAL]

        logger.info(
            "[hacker_news] Top=%d, Best=%d, New=%d, Unique=%d",
            len(top_ids or []), len(best_ids or []), len(new_ids or []),
            len(all_ids),
        )

        # ── 2. 并行获取每个故事的详情 ──────────────────────────────
        logger.info("[hacker_news] Fetching story details...")

        # 从 state 加载已缓存的 URL hash
        src_state = state or {}
        cached_url_hashes: set = set(src_state.get("seen_url_hashes", []))

        story_details: list[dict | None] = BaseCollector.parallel_map(
            func=self._fetch_item,
            items=all_ids,
            max_workers=10,
            desc="hn:items",
        )

        # 过滤掉失败和非 story 类型
        stories = [s for s in story_details if s and s.get("type") == "story"]
        logger.info("[hacker_news] Valid stories: %d", len(stories))

        # ── 3. 准备外部文章下载列表 ───────────────────────────────
        # 收集需要下载外部文章的故事（story_id, url）
        article_tasks = [
            (s["id"], s["url"])
            for s in stories
            if s.get("url") and not self._should_skip_url(s["url"])
        ]

        # 过滤已缓存的 URL
        new_article_tasks = []
        for sid, url in article_tasks:
            url_hash = hashlib.sha256(url.encode()).hexdigest()
            if url_hash in cached_url_hashes:
                logger.debug("[hacker_news] Cached URL: %s", url[:60])
            else:
                new_article_tasks.append((sid, url, url_hash))

        # ── 4. 并行下载外部文章正文 ───────────────────────────────
        article_map: dict[int, str | None] = {}
        new_url_hashes: list[str] = []

        if new_article_tasks:
            # 分离 url_hash，用于更新 state
            new_url_hashes = [t[2] for t in new_article_tasks]
            download_tasks = [(t[0], t[1]) for t in new_article_tasks]

            logger.info(
                "[hacker_news] Downloading %d new articles (%d cached)",
                len(download_tasks),
                len(article_tasks) - len(download_tasks),
            )
            article_contents: list[tuple[str | None, list[str]]] = (
                BaseCollector.parallel_map(
                    func=self._fetch_external_article,
                    items=download_tasks,
                    max_workers=5,
                    desc="hn:articles",
                )
            )
            for task, (content, _) in zip(download_tasks, article_contents):
                article_map[task[0]] = content

        # ── 5. 构造 items ─────────────────────────────────────────
        collected_items: list[dict] = []

        for story in stories:
            story_id: int = story["id"]
            title: str = story.get("title", "") or ""
            author: str | None = story.get("by")
            published_ts: int | None = story.get("time")
            published_at: str | None = (
                datetime.fromtimestamp(published_ts, tz=timezone.utc).isoformat()
                if published_ts else None
            )
            points: int | None = story.get("score")
            comment_count: int = story.get("descendants", 0)
            story_url: str = story.get("url", "") or ""
            hn_discussion_url: str = (
                f"https://news.ycombinator.com/item?id={story_id}"
            )
            story_text: str | None = story.get("text")

            raw_dict: dict[str, Any] = {
                "hn_id": story_id,
                "type": "story",
                "score": points,
                "comment_count": comment_count,
                "hn_url": hn_discussion_url,
                "external_url": story_url if story_url else None,
                "external_content_path": None,
                "text_path": None,
            }

            # 保存 self-text（Ask HN 等）
            if story_text:
                text_filename = f"{story_id}_text.md"
                text_path = self.write_raw(text_filename, story_text, date_str)
                all_raw_files.append(str(text_path))
                raw_dict["text_path"] = str(text_path)

            # 保存外部文章正文
            if story_id in article_map and article_map[story_id]:
                ext_filename = f"{story_id}_content.md"
                ext_path = self.write_raw(
                    ext_filename, article_map[story_id], date_str,
                )
                all_raw_files.append(str(ext_path))
                raw_dict["external_content_path"] = str(ext_path)

            # 构造标准 item
            ai_item = self.build_item(
                item_id=str(story_id),
                title=title,
                description=None,
                author=author,
                published_at=published_at,
                url=hn_discussion_url,
                raw_score=points,
                language="en",
                category="news",
                raw=raw_dict,
            )

            collected_items.append(ai_item)

        # ── 6. 写入 JSON ──────────────────────────────────────────
        json_path = self.write_json(collected_items, date_str)
        last_id = str(stories[-1]["id"]) if stories else ""

        # 联合 content_hash
        all_hashes = "|".join(
            item.get("content_hash", "") for item in collected_items
        )
        combined_hash = hashlib.sha256(all_hashes.encode()).hexdigest()

        logger.info(
            "[hacker_news] Written %d items to %s",
            len(collected_items), json_path,
        )

        return make_collector_result(
            source=self.source_name,
            status="success",
            items=collected_items,
            json_path=str(json_path),
            raw_files=all_raw_files,
            state_update={
                "status": "success",
                "last_item_id": last_id,
                "last_item_count": len(collected_items),
                "last_content_hash": combined_hash,
                "seen_url_hashes": list(set(
                    cached_url_hashes | set(new_url_hashes)
                ))[-1000:],  # 保留最近 1000 个
            },
            start_time=start_time,
        )

    # ── API 请求 ───────────────────────────────────────────────────────

    def _fetch_ids(self, endpoint: str, limit: int) -> list[int] | None:
        """获取指定 endpoint 的故事 ID 列表，截取前 limit 条。"""
        url = f"{API_BASE}/{endpoint}.json"
        result = fetch_url(url, session=self.session)
        if result.failed or not result.data:
            logger.warning("[hacker_news] Failed to fetch %s: %s", endpoint, result.error)
            return None
        try:
            data = result.data.json() if hasattr(result.data, "json") else result.data
            if isinstance(data, list):
                return [int(i) for i in data[:limit]]
            return None
        except (ValueError, TypeError) as e:
            logger.warning("[hacker_news] Parse %s failed: %s", endpoint, e)
            return None

    def _fetch_item(self, item_id: int) -> dict | None:
        """获取单个 HN item 的完整数据。"""
        url = f"{API_BASE}/item/{item_id}.json"
        result = fetch_url(url, session=self.session)
        if result.failed or not result.data:
            return None
        try:
            data = result.data.json() if hasattr(result.data, "json") else result.data
            return data if isinstance(data, dict) else None
        except (ValueError, TypeError):
            return None

    # ── 外部文章下载 ───────────────────────────────────────────────────

    @staticmethod
    def _should_skip_url(url: str) -> bool:
        """判断是否应跳过下载（白名单域名、非 HTTP 链接等）。"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        for skip in SKIP_DOMAINS:
            if domain == skip or domain.endswith("." + skip):
                return True
        return parsed.scheme not in ("http", "https")

    def _fetch_external_article(self, task: tuple) -> tuple[str | None, list[str]]:
        """下载单篇外部文章正文。"""
        _story_id, url = task
        result = fetch_url(url, session=self.session)
        if result.failed:
            return None, []

        try:
            content_type = result.data.headers.get("Content-Type", "")
            body = result.data.text if hasattr(result.data, "text") else str(result.data)

            # 只保存文本内容（HTML 或纯文本）
            if "text/" not in content_type and "html" not in content_type and "json" not in content_type:
                return None, []

            return body, []
        except Exception as e:
            logger.debug("[hacker_news] Read article %s failed: %s", url, e)
            return None, []
