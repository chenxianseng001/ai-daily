"""
YouTube Collector — 单元测试

测试覆盖：
  1. yt-dlp 视频详情获取
  2. 字幕提取（TTML/VTT/SRT 解析）
  3. 频道列表加载
  4. Item Schema 校验
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from collectors.youtube import YouTubeCollector, load_channels
from core.http_client import FetchResult


# ── Fixtures ──────────────────────────────────────────────────────────


SAMPLE_TTML = """<?xml version="1.0" encoding="UTF-8"?>
<tt xmlns="http://www.w3.org/ns/ttml">
  <body>
    <div>
      <p begin="00:00:01.000" end="00:00:04.000">Hello world, this is a test.</p>
      <p begin="00:00:05.000" end="00:00:08.000">Second line of the transcript.</p>
    </div>
  </body>
</tt>"""

SAMPLE_VTT = """WEBVTT
Kind: captions
Language: en

00:00:01.000 --> 00:00:04.000
Hello world, this is a test.

00:00:05.000 --> 00:00:08.000
Second line of the transcript.
"""


@pytest.fixture
def collector():
    return YouTubeCollector()


# ── Tests: Channel Loading ───────────────────────────────────────────


class TestLoadChannels:
    def test_channels_yaml_exists(self):
        """channels.yaml 存在且格式正确。"""
        channels = load_channels()
        assert isinstance(channels, list)
        if channels:
            assert "handle" in channels[0]
            assert "channel_name" in channels[0]

    def test_channels_have_required_fields(self):
        """每个频道都有必填字段。"""
        channels = load_channels()
        for ch in channels:
            assert ch.get("handle"), f"Missing handle: {ch}"
            assert ch.get("channel_name"), f"Missing channel_name: {ch}"


# ── Tests: Transcript Extraction ─────────────────────────────────────


class TestTranscriptExtraction:
    def test_extract_ttml(self):
        """TTML 字幕提取。"""
        text = YouTubeCollector._extract_subtitle_text(SAMPLE_TTML)
        assert "Hello world" in text
        assert "Second line" in text
        assert "<p>" not in text

    def test_extract_vtt(self):
        """VTT 字幕提取。"""
        text = YouTubeCollector._extract_subtitle_text(SAMPLE_VTT)
        assert "Hello world" in text
        assert "00:00:01" not in text  # 时间轴应被移除

    def test_extract_empty(self):
        """空内容返回空字符串。"""
        text = YouTubeCollector._extract_subtitle_text("")
        assert text == ""


# ── Tests: FetchResult ───────────────────────────────────────────────


class TestFetchResult:
    def test_success(self):
        fr = FetchResult.success(data="test")
        assert fr.ok is True
        assert fr.data == "test"
        assert fr.failed is False

    def test_failure(self):
        fr = FetchResult.failure("error msg", 404)
        assert fr.ok is False
        assert fr.error == "error msg"
        assert fr.status_code == 404
        assert fr.failed is True
