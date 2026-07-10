"""AI Daily — X（Twitter）Section"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reporter.base_section import BaseSection


class TwitterSection(BaseSection):
    """X（Twitter）推文日报 Section。"""

    @property
    def name(self) -> str:
        return "X (Twitter)"

    @property
    def source_name(self) -> str:
        return "twitter"

    def render(self, items: list[dict], config: dict | None = None) -> str:
        if self.should_skip(items):
            return ""

        cfg = config or {}
        max_items = cfg.get("twitter_max_items", 10)

        sorted_items = sorted(
            items,
            key=lambda x: x.get("published_at", "") or "",
            reverse=True,
        )
        display_items = sorted_items[:max_items]

        lines: list[str] = []
        lines.append(f"## 🐦 X (Twitter)\n")
        lines.append(f"来自 {self._count_authors(items)} 个账号，展示 {len(display_items)} 条\n")

        for rank, item in enumerate(display_items, 1):
            raw = item.get("raw", {})
            author = item.get("author", "?")
            text = item.get("description", "") or item.get("title", "")
            tweet_url = item.get("url", "")
            published = item.get("published_at", "")
            tags = item.get("tags", [])

            display_name = tags[0] if tags else author

            # 日期
            date_str = published[:10] if published else ""

            lines.append(f"### {rank}. @{author}")
            lines.append("")
            lines.append(f"**{display_name}**")
            if date_str:
                lines.append(f"📅 {date_str}")
            lines.append("")

            # AI 摘要
            summary = self.format_summary(item)
            if summary:
                lines.append(summary)
                lines.append("")

            if text:
                lines.append(f"> {text}")
                lines.append("")

            if tweet_url:
                lines.append(f"[🔗 推文]({tweet_url})")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _count_authors(items: list[dict]) -> int:
        authors = set()
        for item in items:
            a = item.get("author")
            if a:
                authors.add(a)
        return len(authors)
