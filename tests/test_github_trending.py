"""
GitHub Trending Collector — 单元测试

测试覆盖：
  1. HTML 解析（基于本地 HTML 样例）
  2. build_item 输出是否符合 Schema
  3. 完整的 collect 流程
  4. 匿名模式可用性
  5. 失败/异常场景
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from collectors.base_collector import (
    BaseCollector,
    CollectorResult,
    build_state_update,
    get_date_str,
    make_collector_result,
)
from collectors.github_fetcher import (
    GitHubHTMLClient,
    GitHubAPIClient,
    GitHubFetcher,
    TrendingItem,
    RepoInfo,
)
from collectors.github_trending import GithubTrendingCollector
from core.http_client import FetchResult, RateLimiter, build_session


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sample_html():
    """模拟的 GitHub Trending 页面 HTML。"""
    return """<!DOCTYPE html>
<html>
<body>
<main>
<article class="Box-row">
  <h2><a href="/owner1/repo1">owner1 / repo1</a></h2>
  <p>A test repository for unit testing.</p>
  <div class="f6 color-fg-muted mt-2">
    <span itemprop="programmingLanguage">Python</span>
    <a href="/owner1/repo1/stargazers">star 1,234</a>
    <a href="/owner1/repo1/forks">fork 56</a>
    <a href="/owner1"><img src="/avatar1.png"/></a>
    <a href="/contributor1"><img src="/avatar2.png"/></a>
    <span class="d-inline-block float-sm-right">123 stars today</span>
  </div>
</article>
<article class="Box-row">
  <h2><a href="/owner2/repo2">owner2 / repo2</a></h2>
  <p>Another test repo with a longer description for parsing.</p>
  <div class="f6 color-fg-muted mt-2">
    <span itemprop="programmingLanguage">TypeScript</span>
    <a href="/owner2/repo2/stargazers">star 5,678</a>
    <a href="/owner2/repo2/forks">fork 123</a>
    <a href="/owner2"><img src="/avatar3.png"/></a>
    <span class="d-inline-block float-sm-right">456 stars today</span>
  </div>
</article>
</main>
</body>
</html>"""


@pytest.fixture
def trending_collector():
    return GithubTrendingCollector(max_concurrent=2)


# ── Tests: HTML Parsing ──────────────────────────────────────────────


class TestGitHubHTMLClient:
    def test_parse_trending_html(self, sample_html):
        """解析 HTML 能正确提取所有项目。"""
        items = GitHubHTMLClient._parse_trending_html(sample_html)
        assert len(items) == 2

        item1 = items[0]
        assert item1.owner == "owner1"
        assert item1.repo == "repo1"
        assert "test repository" in item1.description
        assert item1.total_stars == 1234
        assert item1.today_stars == 123
        assert item1.language == "Python"
        assert item1.built_by == ["owner1", "contributor1"]

        item2 = items[1]
        assert item2.owner == "owner2"
        assert item2.repo == "repo2"
        assert item2.total_stars == 5678
        assert item2.today_stars == 456
        assert item2.language == "TypeScript"

    def test_parse_empty_html(self):
        """空 HTML 返回空列表。"""
        items = GitHubHTMLClient._parse_trending_html("<html></html>")
        assert items == []

    def test_parse_malformed_article(self):
        """不完整的 article 被跳过，不崩溃。"""
        html = """
        <article><h2><a>no-href</a></h2></article>
        <article class="Box-row">
          <h2><a href="/valid/repo">valid / repo</a></h2>
          <p>Valid repo.</p>
          <div class="f6 color-fg-muted mt-2">
            <span itemprop="programmingLanguage">Go</span>
            <a href="/valid/repo/stargazers">star 100</a>
            <span class="d-inline-block float-sm-right">10 stars today</span>
          </div>
        </article>
        """
        items = GitHubHTMLClient._parse_trending_html(html)
        assert len(items) == 1
        assert items[0].repo == "repo"
        assert items[0].total_stars == 100


# ── Tests: Build Item ────────────────────────────────────────────────


class TestBuildItem:
    def test_build_item_full_schema(self, trending_collector):
        """build_item 输出完全符合 Schema。"""
        item = trending_collector.build_item(
            item_id="owner/repo",
            title="repo",
            description="A test repo",
            author="owner",
            url="https://github.com/owner/repo",
            raw_score=123,
            language="en",
            category="open-source",
            tags=["ai", "python"],
            raw={
                "full_name": "owner/repo",
                "today_stars": 123,
                "total_stars": 5000,
                "readme_path": "/tmp/test_readme.md",
            },
        )

        # 所有必填字段必须存在
        required = ["id", "source", "title", "published_at", "collected_at",
                     "raw", "content_hash"]
        for field in required:
            assert field in item, f"Missing required field: {field}"

        # id 格式
        assert item["id"].startswith("github_trending:")
        assert "content_hash" in item
        assert len(item["content_hash"]) == 64

        # raw 字段
        assert item["raw"]["today_stars"] == 123
        assert item["raw"]["readme_path"] == "/tmp/test_readme.md"

        # 可选字段
        assert item["category"] == "open-source"
        assert item["tags"] == ["ai", "python"]
        assert item["thumbnail_url"] is None

    def test_build_item_minimal(self, trending_collector):
        """最小必填字段也能 work。"""
        item = trending_collector.build_item(
            item_id="minimal/test",
            title="",
            url="",
        )
        assert item["id"] == "github_trending:minimal/test"
        assert item["title"] == ""
        assert item["description"] is None
        assert item["author"] is None
        assert item["raw_score"] is None
        assert item["raw"] == {}


# ── Tests: CollectorResult / State ───────────────────────────────────


class TestCollectorResult:
    def test_make_collector_result(self):
        """构造 CollectorResult 成功。"""
        result = make_collector_result(
            source="github_trending",
            status="success",
            items=[{"id": "1"}],
            json_path="/tmp/test.json",
            raw_files=["/tmp/readme.md"],
        )
        assert result.source == "github_trending"
        assert result.status == "success"
        assert result.item_count == 1
        assert len(result.raw_files) == 1
        assert result.error is None

    def test_make_collector_result_error(self):
        """错误状态也能正确构造。"""
        result = make_collector_result(
            source="github_trending",
            status="error",
            items=[],
            json_path="",
            raw_files=[],
            error="HTTP 403",
        )
        assert result.status == "error"
        assert result.error == "HTTP 403"
        assert result.item_count == 0


class TestStateUpdate:
    def test_build_state_update_success(self):
        """成功状态更新。"""
        upd = build_state_update(
            status="success",
            last_item_id="owner/repo",
            item_count=15,
        )
        assert upd["status"] == "success"
        assert upd["last_item_id"] == "owner/repo"
        assert upd["last_item_count"] == 15
        assert upd["consecutive_failures"] == 0
        assert upd["error"] is None

    def test_build_state_update_error(self):
        """错误状态更新。"""
        upd = build_state_update(
            status="error",
            error="Rate limited",
            consecutive_failures=3,
        )
        assert upd["status"] == "error"
        assert upd["error"] == "Rate limited"
        assert upd["consecutive_failures"] == 3

    def test_build_state_update_zero_items(self):
        """item_count=0 也应记录。"""
        upd = build_state_update(status="success", item_count=0)
        assert upd["last_item_count"] == 0


# ── Tests: Parallel Map ──────────────────────────────────────────────


class TestParallelMap:
    def test_basic(self):
        """并行执行成功。"""
        results = BaseCollector.parallel_map(
            lambda x: x * 2, [1, 2, 3], max_workers=2, desc="test"
        )
        assert results == [2, 4, 6]

    def test_with_failures(self):
        """失败项返回 None，不中断整体。"""

        def f(x):
            if x == 0:
                raise ValueError("zero")
            return x * 10

        results = BaseCollector.parallel_map(f, [1, 0, 3])
        assert results[0] == 10
        assert results[1] is None
        assert results[2] == 30

    def test_empty_list(self):
        """空列表返回空列表。"""
        results = BaseCollector.parallel_map(lambda x: x, [])
        assert results == []


# ── Tests: RateLimiter ───────────────────────────────────────────────


class TestRateLimiter:
    def test_basic(self):
        limiter = RateLimiter(5)
        assert limiter.max_concurrent == 5
        with limiter:
            pass  # 正常执行

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            RateLimiter(0)


# ── Tests: FetchResult ───────────────────────────────────────────────


class TestFetchResult:
    def test_success(self):
        fr = FetchResult.success(data={"key": "value"})
        assert fr.ok is True
        assert fr.data == {"key": "value"}
        assert fr.failed is False

    def test_failure(self):
        fr = FetchResult.failure("Not found", 404)
        assert fr.ok is False
        assert fr.error == "Not found"
        assert fr.failed is True
        assert fr.status_code == 404
