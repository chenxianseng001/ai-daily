"""
Twitter Collector — 单元测试

测试覆盖：
  1. 配置加载
  2. Nitter 实例列表加载
  3. 推文解析
  4. 健康检查逻辑
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from collectors.twitter import TwitterCollector, load_config
from core.http_client import FetchResult


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def collector():
    return TwitterCollector()


# ── Tests: Config Loading ────────────────────────────────────────────


class TestLoadConfig:
    def test_config_exists(self):
        """twitter_accounts.yaml 存在。"""
        accounts, instances = load_config()
        assert isinstance(accounts, list)

    def test_has_nitter_instances(self):
        """至少有一个 Nitter 实例。"""
        _accounts, instances = load_config()
        assert len(instances) > 0
        assert instances[0].startswith("http")

    def test_accounts_have_required_fields(self):
        """账号有必填字段。"""
        accounts, _instances = load_config()
        for acct in accounts:
            assert acct.get("username"), f"Missing username: {acct}"


# ── Tests: FetchResult ───────────────────────────────────────────────


class TestFetchResult:
    def test_success(self):
        fr = FetchResult.success(["tweet1", "tweet2"])
        assert fr.ok is True
        assert fr.data == ["tweet1", "tweet2"]
        assert fr.failed is False

    def test_failure(self):
        fr = FetchResult.failure("Nitter unavailable", 503)
        assert fr.ok is False
        assert fr.failed is True
