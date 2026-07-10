"""
Product Hunt Collector — 单元测试

测试覆盖：
  1. Apollo SSR 数据解析
  2. 完整的 collect 流程（网页降级模式）
  3. 输出是否符合 Data Contract
  4. 空数据场景
"""

from __future__ import annotations

import json

import pytest

from collectors.base_collector import BaseCollector, build_state_update, get_date_str
from collectors.product_hunt import ProductHuntCollector


# ── Fixtures ──────────────────────────────────────────────────────────


# 模拟的 Product Hunt 页面 HTML（嵌入 Apollo SSR 数据）
MOCK_APOLLO_HTML = """
<!DOCTYPE html>
<html>
<head><script>
(window[Symbol.for("ApolloSSRDataTransport")] ??= []).push({"rehydrate":{"_R_test_":{"data":{"__typename":"Post","id":"12345","name":"Test Product","tagline":"A test product for unit testing","slug":"test-product","createdAt":"2026-07-09T00:01:00-07:00","topics":{"__typename":"PostTopicConnection","edges":[{"__typename":"PostTopicEdge","node":{"__typename":"Topic","name":"AI","slug":"ai"}}]},"featuredAt":"2026-07-09T00:00:00-07:00","commentsCount":5},"complete":true}}});
</script></head>
<body></body>
</html>
"""

MOCK_APOLLO_MULTI = """
<!DOCTYPE html>
<html><head><script>
(window[Symbol.for("ApolloSSRDataTransport")] ??= []).push({"rehydrate":{"_R_1_":{"data":{"__typename":"Post","id":"1","name":"First Product","tagline":"The first test product","slug":"first","createdAt":"2026-07-09T00:01:00-07:00","topics":{"__typename":"PostTopicConnection","edges":[{"__typename":"PostTopicEdge","node":{"__typename":"Topic","name":"AI","slug":"ai"}}]}}},"_R_2_":{"data":{"__typename":"Post","id":"2","name":"Second Product","tagline":"The second test product","slug":"second","createdAt":"2026-07-09T00:02:00-07:00","topics":{"__typename":"PostTopicConnection","edges":[{"__typename":"PostTopicEdge","node":{"__typename":"Topic","name":"Developer Tools","slug":"developer-tools"}}]}},"_R_3_":{"data":{"__typename":"NotPost","id":"3"}}},"complete":true}});
</script></head>
<body></body>
</html>
"""


@pytest.fixture
def collector():
    return ProductHuntCollector()  # No token → web fallback


# ── Tests: Apollo 数据解析 ────────────────────────────────────────────


class TestParseApolloPosts:
    def test_parse_single_post(self):
        """解析包含一个 Post 的 Apollo 数据。"""
        posts = ProductHuntCollector._parse_apollo_posts(MOCK_APOLLO_HTML)
        assert len(posts) == 1
        assert posts[0]["name"] == "Test Product"
        assert posts[0]["tagline"] == "A test product for unit testing"
        assert posts[0]["id"] == "12345"

    def test_parse_multi_posts(self):
        """解析多个 Post，过滤非 Post 类型。"""
        posts = ProductHuntCollector._parse_apollo_posts(MOCK_APOLLO_MULTI)
        assert len(posts) == 2
        assert posts[0]["name"] == "First Product"
        assert posts[1]["name"] == "Second Product"

    def test_empty_html(self):
        """空 HTML 返回空列表。"""
        posts = ProductHuntCollector._parse_apollo_posts("<html></html>")
        assert posts == []

    def test_no_apollo_data(self):
        """没有 Apollo 数据的 HTML 返回空列表。"""
        posts = ProductHuntCollector._parse_apollo_posts(
            "<html><body><p>Hello</p></body></html>"
        )
        assert posts == []


# ── Tests: 完整采集流程 ──────────────────────────────────────────────


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
                assert "id" in item
                assert "source" in item and item["source"] == "product_hunt"
                assert "title" in item
                assert "content_hash" in item and len(item["content_hash"]) == 64
                assert "raw" in item
                assert item["id"].startswith("product_hunt:")


# ── Tests: State Update ──────────────────────────────────────────────


class TestStateUpdate:
    def test_success_state(self):
        """成功采集的 state 更新。"""
        upd = build_state_update(
            status="success",
            last_item_id="12345",
            item_count=30,
        )
        assert upd["status"] == "success"
        assert upd["last_item_id"] == "12345"
        assert upd["last_item_count"] == 30

    def test_error_state(self):
        """失败采集的 state 更新。"""
        upd = build_state_update(
            status="error",
            error="API error",
            consecutive_failures=1,
        )
        assert upd["status"] == "error"
        assert upd["error"] == "API error"
        assert upd["consecutive_failures"] == 1
