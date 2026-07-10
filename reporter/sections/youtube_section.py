"""AI Daily — YouTube Section（v2.1.2 轻量版）

仅展示：标题（可翻译为中文）、频道名称、发布时间。
不展示描述、字幕、AI 摘要。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reporter.base_section import BaseSection


class YouTubeSection(BaseSection):
    @property
    def name(self) -> str:
        return "YouTube"

    @property
    def source_name(self) -> str:
        return "youtube"

    def render(self, items: list[dict], config: dict | None = None) -> str:
        if self.should_skip(items):
            return ""

        cfg = config or {}
        max_items = cfg.get("youtube_max_items", 10)

        # 按发布时间降序
        sorted_items = sorted(
            items,
            key=lambda x: x.get("published_at", "") or "",
            reverse=True,
        )
        display_items = sorted_items[:max_items]

        lines: list[str] = []
        lines.append(f"## 🎬 YouTube\n")
        lines.append(
            f"来自 {self._count_channels(items)} 个频道，展示 {len(display_items)} 个视频\n"
        )

        for rank, item in enumerate(display_items, 1):
            raw = item.get("raw", {}) or {}
            title = item.get("title", "")
            channel = item.get("author", raw.get("channel_name", ""))
            published = item.get("published_at", "")
            duration = raw.get("duration_seconds", 0)

            # 时长格式化
            duration_str = ""
            if duration:
                m, s = divmod(int(duration), 60)
                h, m = divmod(m, 60)
                if h:
                    duration_str = f"{h}:{m:02d}:{s:02d}"
                else:
                    duration_str = f"{m}:{s:02d}"

            # 日期
            date_str = published[:10] if published else ""

            lines.append(f"### {rank}. {title}")
            lines.append("")
            parts = []
            if channel:
                parts.append(f"📺 {channel}")
            if date_str:
                parts.append(f"📅 {date_str}")
            if duration_str:
                parts.append(f"⏱ {duration_str}")
            if parts:
                lines.append(" · ".join(parts))
                lines.append("")

            lines.append("---")

        return "\n".join(lines)

    @staticmethod
    def _count_channels(items: list[dict]) -> int:
        channels = set()
        for item in items:
            ch = item.get("raw", {}).get("channel_name") or item.get("author")
            if ch:
                channels.add(ch)
        return len(channels)
