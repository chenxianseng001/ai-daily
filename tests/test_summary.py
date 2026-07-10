"""
AI Summary — 单元测试

测试覆盖：
  1. Prompt 构造（每个数据源）
  2. 缓存机制
  3. SummaryGenerator 流程
  4. Raw 文件加载
"""

from __future__ import annotations

from pathlib import Path

import pytest

from reporter.summary.cache import SummaryCache
from reporter.summary.prompts import (
    GitHubPromptBuilder,
    HackerNewsPromptBuilder,
    ProductHuntPromptBuilder,
    YouTubePromptBuilder,
    TwitterPromptBuilder,
    ChinaAIPromptBuilder,
    get_prompt_builder,
)
from reporter.summary.generator import SummaryGenerator


# ── Prompt 构造 ──────────────────────────────────────────────────────


class TestPromptBuilders:
    def test_github_prompt(self):
        builder = GitHubPromptBuilder()
        item = {"title": "test-repo", "description": "A test repo",
                "raw": {"today_stars": 100, "total_stars": 5000, "primary_language": "Python"}}
        prompt = builder.build_prompt(item, "README content here")
        assert "test-repo" in prompt
        assert "100" in prompt
        assert "README" in prompt

    def test_hacker_news_prompt(self):
        builder = HackerNewsPromptBuilder()
        item = {"title": "New AI breakthrough", "author": "testuser",
                "raw": {"score": 500, "comment_count": 100}}
        prompt = builder.build_prompt(item, "Article body here")
        assert "New AI breakthrough" in prompt
        assert "500" in prompt

    def test_product_hunt_prompt(self):
        builder = ProductHuntPromptBuilder()
        item = {"title": "Awesome App", "description": "Best app ever",
                "raw": {"votes_count": 300, "topics": ["ai", "productivity"]}}
        prompt = builder.build_prompt(item, "Product description")
        assert "Awesome App" in prompt
        assert "Best app ever" in prompt

    def test_youtube_prompt(self):
        builder = YouTubePromptBuilder()
        item = {"title": "Video Title", "author": "Creator",
                "raw": {"duration_seconds": 600}}
        prompt = builder.build_prompt(item, "Video description")
        assert "Video Title" in prompt
        assert "Creator" in prompt

    def test_twitter_prompt(self):
        builder = TwitterPromptBuilder()
        item = {"author": "user123"}
        prompt = builder.build_prompt(item, "Tweet text here")
        assert "user123" in prompt
        assert "Tweet text" in prompt

    def test_china_ai_prompt(self):
        builder = ChinaAIPromptBuilder()
        item = {"title": "AI News Title", "description": "Brief summary"}
        prompt = builder.build_prompt(item, "Full article")
        assert "AI News Title" in prompt

    def test_get_prompt_builder(self):
        builder = get_prompt_builder("github_trending")
        assert isinstance(builder, GitHubPromptBuilder)

        builder = get_prompt_builder("unknown_source")
        assert isinstance(builder, GitHubPromptBuilder)  # fallback


# ── 缓存机制 ──────────────────────────────────────────────────────────


class TestSummaryCache:
    def test_cache_set_get(self):
        cache = SummaryCache()
        cache.set("test_hash_123", "This is a test summary")
        result = cache.get("test_hash_123")
        assert result == "This is a test summary"

    def test_cache_miss(self):
        cache = SummaryCache()
        result = cache.get("nonexistent_hash")
        assert result is None

    def test_cache_different_hashes(self):
        cache = SummaryCache()
        cache.set("hash_a", "Summary A")
        cache.set("hash_b", "Summary B")
        assert cache.get("hash_a") == "Summary A"
        assert cache.get("hash_b") == "Summary B"


# ── SummaryGenerator ─────────────────────────────────────────────────


class TestSummaryGenerator:
    def test_no_api_key_skips(self):
        """无 API Key 时不生成摘要。"""
        gen = SummaryGenerator({"api_key": ""})
        item = {"content_hash": "test", "title": "Test"}
        result = gen.summarize(item, "github_trending")
        assert result == ""

    def test_raw_loading_from_description(self):
        """没有 raw 文件时使用 description。"""
        gen = SummaryGenerator({"api_key": ""})
        # content_hash is empty
        item = {"content_hash": "", "title": "Test"}
        result = gen.summarize(item, "github_trending")
        assert result == ""

    def test_provider_creation(self):
        """Provider 创建。"""
        from reporter.summary.generator import OpenAICompatibleProvider
        provider = OpenAICompatibleProvider(api_key="test-key", model="gpt-4o-mini")
        assert provider.api_key == "test-key"
        assert provider.model == "gpt-4o-mini"

    def test_deepseek_provider(self):
        """DeepSeek Provider 创建。"""
        from reporter.summary.generator import PROVIDER_REGISTRY, PROVIDER_META
        assert "deepseek" in PROVIDER_REGISTRY
        meta = PROVIDER_META.get("deepseek", {})
        assert "api.deepseek.com" in meta.get("base_url", "")

    def test_openrouter_provider(self):
        """OpenRouter Provider 创建。"""
        from reporter.summary.generator import PROVIDER_REGISTRY, PROVIDER_META
        assert "openrouter" in PROVIDER_REGISTRY
        meta = PROVIDER_META.get("openrouter", {})
        assert "openrouter.ai" in meta.get("base_url", "")

    def test_ollama_provider(self):
        """Ollama Provider 注册。"""
        from reporter.summary.generator import PROVIDER_REGISTRY
        assert "ollama" in PROVIDER_REGISTRY

    def test_lm_studio_provider(self):
        """LM Studio Provider 注册。"""
        from reporter.summary.generator import PROVIDER_REGISTRY
        assert "lm_studio" in PROVIDER_REGISTRY

    def test_siliconflow_provider(self):
        """SiliconFlow Provider 注册。"""
        from reporter.summary.generator import PROVIDER_REGISTRY
        assert "siliconflow" in PROVIDER_REGISTRY

    def test_all_providers_have_meta(self):
        """所有注册的 Provider 都有元信息。"""
        from reporter.summary.generator import PROVIDER_REGISTRY, PROVIDER_META
        for name in PROVIDER_REGISTRY:
            # Gemini 和 Claude 没有元信息（非 OpenAI 兼容）
            if name in ("gemini", "claude"):
                continue
            assert name in PROVIDER_META, f"Missing meta for {name}"

    def test_stats(self):
        """统计信息。"""
        gen = SummaryGenerator({"api_key": ""})
        stats = gen.stats()
        assert "total" in stats
        assert "hit_rate" in stats
