"""
China AI Collector — 单元测试

测试覆盖：
  1. 配置加载
  2. RSS 解析
  3. Item Schema 校验
"""

from __future__ import annotations

import pytest

from collectors.china_ai import ChinaAICollector, load_sources
from core.http_client import FetchResult


@pytest.fixture
def collector():
    return ChinaAICollector()


class TestLoadSources:
    def test_sources_exists(self):
        """china_ai_sources.yaml 存在且格式正确。"""
        config = load_sources()
        assert "media_sources" in config

    def test_media_sources_have_required_fields(self):
        """媒体源有必填字段。"""
        config = load_sources()
        for src in config.get("media_sources", []):
            assert src.get("id"), f"Missing id: {src}"
            assert src.get("name"), f"Missing name: {src}"
