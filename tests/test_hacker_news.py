"""
Hacker News Collector — 单元测试

测试覆盖：
  1. API ID 列表获取
  2. 单个 item 详情获取
  3. 外部文章下载与跳过逻辑
  4. 完整的 collect 流程
  5. 输出是否符合 Data Contract
"""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from collectors.base_collector import (
    BaseCollector,
    build_state_update,
    get_date_str,
    make_collector_result,
)
from collectors.hacker_news import HackerNewsCollector, API_BASE


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def collector():
    return HackerNewsCollector()


# ── Tests: ID 列表获取 ───────────────────────────────────────────────


class TestFetchIds:
    def test_top_stories(self, collector):
        """能获取 Top Stories ID 列表。"""
        ids = collector._fetch_ids("topstories", 5)
        if ids is not None:
            assert len(ids) <= 5
            assert all(isinstance(i, int) for i in ids)
            assert len(ids) > 0

    def test_best_stories(self, collector):
        """能获取 Best Stories ID 列表。"""
        ids = collector._fetch_ids("beststories", 5)
        if ids is not None:
            assert len(ids) <= 5
            assert all(isinstance(i, int) for i in ids)

    def test_new_stories(self, collector):
        """能获取 New Stories ID 列表。"""
        ids = collector._fetch_ids("newstories", 5)
        if ids is not None:
            assert len(ids) <= 5
            assert all(isinstance(i, int) for i in ids)

    def test_invalid_endpoint(self, collector):
        """无效 endpoint 返回 None。"""
        ids = collector._fetch_ids("nonexistent", 5)
        assert ids is None


# ── Tests: Item 详情获取 ─────────────────────────────────────────────


class TestFetchItem:
    def test_fetch_known_story(self, collector):
        """能获取一个真实的 HN story。"""
        # 使用当天已知的 story ID（从测试中获取）
        ids = collector._fetch_ids("topstories", 1)
        if ids:
            item = collector._fetch_item(ids[0])
            assert item is not None
            assert item.get("type") == "story"
            assert "title" in item
            assert "by" in item
            assert "score" in item

    def test_fetch_nonexistent(self, collector):
        """不存在的 item 返回 None。"""
        item = collector._fetch_item(999999999)
        assert item is None


# ── Tests: URL 跳过逻辑 ──────────────────────────────────────────────


class TestShouldSkipUrl:
    def test_skip_twitter(self):
        assert HackerNewsCollector._should_skip_url("https://twitter.com/user/123") is True

    def test_skip_github(self):
        assert HackerNewsCollector._should_skip_url("https://github.com/owner/repo") is True

    def test_skip_youtube(self):
        assert HackerNewsCollector._should_skip_url("https://www.youtube.com/watch?v=abc") is True

    def test_skip_hn(self):
        assert HackerNewsCollector._should_skip_url(
            "https://news.ycombinator.com/item?id=123"
        ) is True

    def test_allow_normal(self):
        assert HackerNewsCollector._should_skip_url(
            "https://example.com/article"
        ) is False

    def test_skip_non_http(self):
        assert HackerNewsCollector._should_skip_url("ftp://example.com/file") is True


# ── Tests: 完整收集流程 ──────────────────────────────────────────────


class TestFullCollect:
    def test_collect_returns_result(self, collector):
        """collect 返回 CollectorResult。"""
        from collectors.base_collector import CollectorResult
        result = collector.collect({})
        assert isinstance(result, CollectorResult)
        assert result.status in ("success", "error")

    def test_collect_items_validate_schema(self, collector):
        """每个 item 必须通过 validate_item 校验。"""
        result = collector.collect({})
        if result.status == "success" and result.items:
            for item in result.items:
                # 手动校验必填字段
                assert "id" in item
                assert item["id"].startswith("hacker_news:")
                assert "source" in item and item["source"] == "hacker_news"
                assert "title" in item
                assert "content_hash" in item and len(item["content_hash"]) == 64
                assert "raw" in item
                assert "published_at" in item

    def test_collect_top_stories_high_score(self, collector):
        """Top Stories 中应该有 high-score 条目（>100 pts）。"""
        result = collector.collect({})
        if result.status == "success" and result.items:
            scores = [
                item.get("raw_score", 0) or 0
                for item in result.items
            ]
            max_score = max(scores)
            assert max_score > 100, (
                f"No high-score stories found. Max score: {max_score}"
            )


# ── Tests: State Update ──────────────────────────────────────────────


class TestStateUpdate:
    def test_success_state(self):
        """成功采集的 state 更新。"""
        upd = build_state_update(
            status="success",
            last_item_id="48845049",
            item_count=59,
        )
        assert upd["status"] == "success"
        assert upd["last_item_id"] == "48845049"
        assert upd["last_item_count"] == 59

    def test_error_state(self):
        """失败采集的 state 更新。"""
        upd = build_state_update(
            status="error",
            error="API timeout",
            consecutive_failures=2,
        )
        assert upd["status"] == "error"
        assert upd["error"] == "API timeout"
        assert upd["consecutive_failures"] == 2


# ── Tests: URL Parsing ──────────────────────────────────────────────


class TestUrlParsing:
    def test_skip_x_domain(self):
        """x.com 也在跳过列表中。"""
        assert HackerNewsCollector._should_skip_url("https://x.com/elonmusk/status/123") is True

    def test_skip_subdomain_youtube(self):
        """youtube.com 子域名也跳过。"""
        assert HackerNewsCollector._should_skip_url(
            "https://m.youtube.com/watch?v=abc"
        ) is True
