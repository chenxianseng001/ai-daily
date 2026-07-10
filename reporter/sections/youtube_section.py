"""AI Daily — YouTube Section"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reporter.base_section import BaseSection


class YouTubeSection(BaseSection):
    """YouTube 视频日报 Section。"""

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

        # 按发布时间降序（最新的优先）
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
            raw = item.get("raw", {})
            title = item.get("title", "")
            channel = item.get("author", raw.get("channel_name", ""))
            published = item.get("published_at", "")
            duration = raw.get("duration_seconds", 0)
            views = raw.get("view_count", 0)
            video_url = item.get("url", "")
            thumbnail = item.get("thumbnail_url", "")
            desc_path = raw.get("description_path")
            trans_path = raw.get("transcript_path")

            # 时长格式化
            duration_str = ""
            if duration:
                m, s = divmod(int(duration), 60)
                h, m = divmod(m, 60)
                if h:
                    duration_str = f"{h}:{m:02d}:{s:02d}"
                else:
                    duration_str = f"{m}:{s:02d}"

            # 日期格式化
            date_str = ""
            if published:
                date_str = published[:10]

            lines.append(f"### {rank}. [{title}]({video_url})")
            lines.append("")
            lines.append(f"📺 {channel}")
            if date_str:
                lines.append(f"📅 {date_str}")
            if duration_str:
                lines.append(f"⏱ {duration_str}")
            if views:
                lines.append(f"👁 {views:,}")
            lines.append("")

            # AI 摘要
            summary = self.format_summary(item)
            if summary:
                lines.append(summary)
                lines.append("")

            # 描述预览
            if desc_path:
                preview = self._load_preview(desc_path, 500)
                if preview:
                    lines.append(f"> {preview}")
                    lines.append("")

            # 字幕预览
            if trans_path:
                preview = self._load_preview(trans_path, 300)
                if preview:
                    lines.append(
                        f"<details><summary>📝 字幕摘要</summary>\n\n> {preview}\n</details>"
                    )
                    lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _count_channels(items: list[dict]) -> int:
        channels = set()
        for item in items:
            ch = item.get("raw", {}).get("channel_name") or item.get("author")
            if ch:
                channels.add(ch)
        return len(channels)

    @staticmethod
    def _load_preview(raw_path: str | None, max_chars: int = 500) -> str:
        if not raw_path:
            return ""
        path = Path(raw_path)
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8")
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        return text
