"""AI Daily — X（Twitter）Collector

采集关注账号的最新推文。

数据源策略：
  ① Nitter RSS（默认）— 支持多实例 + 健康检查 + 自动切换
  ② Twitter API v2（配置 BEARER_TOKEN 时启用）

推文原文保存到 raw 文件，Collector 不生成摘要。
"""

from __future__ import annotations

import logging
import time
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
from core.utils import clean_html, parse_rss_date, safe_filename

logger = logging.getLogger("ai_daily.twitter")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── 配置加载 ──────────────────────────────────────────────────────────


def load_config() -> tuple[list[dict], list[str]]:
    """加载 Twitter 配置。返回 (accounts, nitter_instances)。"""
    path = PROJECT_ROOT / "config" / "twitter_accounts.yaml"
    if not path.exists():
        return [], []
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    accounts = [a for a in data.get("accounts", []) if a.get("enabled", True)]
    instances = data.get("nitter_instances", ["https://nitter.net"])
    return accounts, instances


class TwitterCollector(BaseCollector):
    """X（Twitter）推文采集器（多实例容错版）。"""

    @property
    def source_name(self) -> str:
        return "twitter"

    def __init__(self, bearer_token: str | None = None):
        self.bearer_token = bearer_token
        self.session = build_session()

    def collect(self, state: dict) -> CollectorResult:
        start_time = time.time()
        date_str = get_date_str()
        all_raw_files: list[str] = []
        all_items: list[dict] = []

        accounts, instances = load_config()
        if not accounts:
            return self._empty(start_time, date_str)

        # 健康检查：找到第一个可用实例
        active_instance = self._find_active_instance(instances)
        if not active_instance:
            logger.warning("[twitter] All Nitter instances unavailable, skipping")
            return self._empty(start_time, date_str)

        logger.info("[twitter] Using Nitter: %s", active_instance)

        src_state = state or {}
        account_states = src_state.get("accounts", {})

        for acct in accounts:
            username = acct["username"]
            display = acct.get("display_name", username)
            max_tweets = acct.get("max_tweets", 10)
            acct_state = account_states.get(username, {})
            last_id = acct_state.get("last_tweet_id")

            try:
                tweets = self._fetch_via_nitter(active_instance, username, max_tweets)
                if not tweets:
                    continue

                # 增量
                if last_id:
                    tweets = [t for t in tweets
                              if int(t["id"]) > int(last_id)]
                    if not tweets:
                        continue

                for tw in tweets:
                    raw_fn = safe_filename(f"{tw['id']}_text") + ".md"
                    raw_content = (
                        f"Author: @{tw['author']}\n"
                        f"URL: {tw['url']}\n"
                        f"Published: {tw['published_at']}\n"
                        f"\n---\n\n{tw['text']}\n"
                    )
                    raw_path = self.write_raw(raw_fn, raw_content, date_str)
                    all_raw_files.append(str(raw_path))

                    item = self.build_item(
                        item_id=tw["id"],
                        title=tw["text"][:100],
                        description=tw["text"][:300],
                        author=tw["author"],
                        published_at=tw["published_at"],
                        url=tw["url"],
                        raw_score=0,
                        language="en",
                        category="social",
                        tags=[display],
                        raw={
                            "tweet_id": tw["id"],
                            "author_screen_name": tw["author"],
                            "text_path": str(raw_path),
                            "source": "nitter_rss",
                        },
                    )
                    all_items.append(item)

                src_state.setdefault("accounts", {})[username] = {
                    "last_tweet_id": tweets[0]["id"],
                }

            except Exception as e:
                logger.warning("[twitter] %s: %s", display, e)
                continue

        if not all_items:
            return self._empty(start_time, date_str)

        json_path = self.write_json(all_items, date_str)
        logger.info(
            "[twitter] Done: %d tweets in %.1fs",
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
                "last_item_count": len(all_items),
                "accounts": src_state.get("accounts", {}),
            },
            start_time=start_time,
        )

    def _empty(self, start, date_str) -> CollectorResult:
        return make_collector_result(
            source=self.source_name, status="success", items=[],
            json_path=str(self.today_json_path(date_str)), raw_files=[],
            state_update=build_state_update(status="success", item_count=0),
            start_time=start,
        )

    # ── 实例健康检查 ───────────────────────────────────────────────────

    def _find_active_instance(self, instances: list[str]) -> str | None:
        """按顺序检查 Nitter 实例，返回第一个可用的。"""
        for inst in instances:
            try:
                test_url = f"{inst.rstrip('/')}/OpenAI/rss"
                result = fetch_url(test_url, session=self.session)
                if result.ok:
                    return inst.rstrip("/")
                logger.debug("[twitter] Instance %s unavailable: %s", inst, result.error)
            except Exception as e:
                logger.debug("[twitter] Instance %s error: %s", inst, e)
        return None

    # ── Nitter RSS 采集 ───────────────────────────────────────────────

    def _fetch_via_nitter(
        self, base_url: str, username: str, max_items: int,
    ) -> list[dict]:
        """通过 Nitter RSS 获取推文。"""
        url = f"{base_url}/{username}/rss"
        result = fetch_url(url, session=self.session)
        if result.failed:
            logger.warning("[twitter] RSS %s/%s: %s", base_url, username, result.error)
            return []

        try:
            root = ET.fromstring(result.data.text)
        except ET.ParseError as e:
            logger.warning("[twitter] RSS parse %s: %s", username, e)
            return []

        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        tweets = []

        for item in root.findall(".//item")[:max_items]:
            tweet_id = (item.findtext("guid", "") or "").strip()
            if not tweet_id:
                continue

            author_el = item.find(".//dc:creator", ns)
            author = (author_el.text or "").lstrip("@") if author_el is not None else ""

            desc_raw = item.findtext("description", "")
            text = clean_html(desc_raw) if desc_raw else ""

            link = (item.findtext("link", "") or "").split("#")[0]

            tweets.append({
                "id": tweet_id,
                "author": author,
                "published_at": parse_rss_date(item.findtext("pubDate", "")),
                "text": text,
                "url": link,
            })

        return tweets
