"""
Event Clustering — 单元测试

测试覆盖：
  1. 文本标准化/分词
  2. Jaccard 相似度
  3. 关键词提取
  4. URL 去重
  5. 完整聚类流程
  6. Event 数据结构
"""

from __future__ import annotations

import pytest

from reporter.event_cluster import (
    EventCluster,
    Event,
    normalize_title,
    tokenize,
    jaccard_similarity,
    extract_keywords,
)


# ── 文本处理 ──────────────────────────────────────────────────────────


class TestTextProcessing:
    def test_normalize_title(self):
        assert normalize_title("OpenAI 发布 GPT-5!") == "openai 发布 gpt 5"
        assert normalize_title("") == ""

    def test_tokenize(self):
        tokens = tokenize("OpenAI releases GPT-5 model")
        assert "openai" in tokens
        assert "releases" in tokens
        assert "model" in tokens

    def test_jaccard_identical(self):
        a = {"openai", "gpt", "release"}
        b = {"openai", "gpt", "release"}
        assert jaccard_similarity(a, b) == 1.0

    def test_jaccard_partial(self):
        a = {"openai", "gpt", "release"}
        b = {"openai", "claude", "anthropic"}
        sim = jaccard_similarity(a, b)
        assert 0.0 < sim < 1.0
        assert sim == 0.2  # 1/5 shared

    def test_jaccard_disjoint(self):
        a = {"openai"}
        b = {"anthropic"}
        assert jaccard_similarity(a, b) == 0.0

    def test_jaccard_empty(self):
        assert jaccard_similarity(set(), {"a"}) == 0.0


# ── 关键词提取 ────────────────────────────────────────────────────────


class TestKeywordExtraction:
    def test_extract_ai_keyword(self):
        kw = extract_keywords("OpenAI released GPT-5 today")
        assert "openai" in kw
        assert "gpt" in kw

    def test_extract_multiple(self):
        kw = extract_keywords("Anthropic Claude and Google DeepMind")
        assert "anthropic" in kw
        assert "claude" in kw
        assert "google deepmind" in kw

    def test_no_keywords(self):
        kw = extract_keywords("Today is a sunny day")
        assert kw == []


# ── 聚类判定 ──────────────────────────────────────────────────────────


class TestClusterDecision:
    def test_same_title_clusters(self):
        a = {"title": "OpenAI releases GPT-5", "url": "https://a.com", "raw": {}}
        b = {"title": "OpenAI releases GPT-5 model", "url": "https://b.com", "raw": {}}
        clusterer = EventCluster(threshold=0.35)
        assert clusterer._should_cluster(a, b) is True

    def test_different_topic_not_cluster(self):
        a = {"title": "John Deere right to repair", "url": "https://a.com", "raw": {}}
        b = {"title": "OpenAI releases GPT-5", "url": "https://b.com", "raw": {}}
        clusterer = EventCluster()
        assert clusterer._should_cluster(a, b) is False

    def test_same_url_clusters(self):
        a = {"title": "Any title", "url": "https://example.com/news", "raw": {}}
        b = {"title": "Different title same URL", "url": "https://example.com/news", "raw": {}}
        clusterer = EventCluster()
        assert clusterer._should_cluster(a, b) is True

    def test_same_external_url_clusters(self):
        a = {"title": "HN post", "url": "https://hn.com/item?id=1",
             "raw": {"external_url": "https://example.com/article"}}
        b = {"title": "Tweet about it", "url": "https://twitter.com/user/1",
             "raw": {"external_url": "https://example.com/article"}}
        clusterer = EventCluster()
        assert clusterer._should_cluster(a, b) is True

    def test_keyword_cluster(self):
        a = {"title": "OpenAI launches new GPT model with reasoning", "url": "a", "raw": {}}
        b = {"title": "GPT-5 from OpenAI sets new benchmark", "url": "b", "raw": {}}
        clusterer = EventCluster()
        assert clusterer._should_cluster(a, b) is True


# ── Event 数据结构 ────────────────────────────────────────────────────


class TestEvent:
    def test_event_creation(self):
        event = Event(
            title="Test Event",
            description="Description",
            sources=["hacker_news", "twitter"],
            items=[{"id": "1"}, {"id": "2"}],
            total_score=100,
            max_score=60,
            item_count=2,
            source_count=2,
            top_keywords=["openai", "gpt"],
        )
        assert event.title == "Test Event"
        assert event.source_count == 2
        assert event.item_count == 2
        assert event.source_summary == "hacker_news×1, twitter×1"

    def test_single_source_summary(self):
        event = Event(
            title="Single", description="", sources=["github_trending"],
            items=[{"id": "1"}], total_score=10, max_score=10,
            item_count=1, source_count=1, top_keywords=[],
        )
        assert "github_trending" in event.source_summary


# ── 完整聚类流程 ──────────────────────────────────────────────────────


class TestFullCluster:
    def test_cluster_empty(self):
        clusterer = EventCluster()
        events = clusterer.cluster({})
        assert events == []

    def test_cluster_no_match(self):
        all_data = {
            "hn": [
                {"title": "Apple releases new iPhone", "url": "a", "raw": {}, "raw_score": 100},
            ],
            "twitter": [
                {"title": "Microsoft announces Windows update", "url": "b", "raw": {}, "raw_score": 50},
            ],
        }
        clusterer = EventCluster()
        events = clusterer.cluster(all_data)
        assert len(events) == 2

    def test_cluster_cross_source(self):
        all_data = {
            "hn": [
                {"title": "OpenAI announces GPT-5 release", "url": "a",
                 "raw": {}, "raw_score": 200},
            ],
            "twitter": [
                {"title": "GPT-5 from OpenAI is here", "url": "b",
                 "raw": {}, "raw_score": 500},
            ],
        }
        clusterer = EventCluster()
        events = clusterer.cluster(all_data)
        merged = [e for e in events if e.source_count > 1]
        assert len(merged) == 1
        assert merged[0].source_count == 2
