"""AI Daily — Hacker News Section — v2.1"""

from __future__ import annotations

from typing import Any

from reporter.base_section import BaseSection


class HackerNewsSection(BaseSection):
    @property
    def name(self) -> str:
        return "Hacker News"

    @property
    def source_name(self) -> str:
        return "hacker_news"

    def render(self, items: list[dict], config: dict | None = None) -> str:
        if self.should_skip(items):
            return ""
        cfg = config or {}
        max_items = cfg.get("hn_max_items", 10)
        lines = []

        lines.append(f"## 📰 Hacker News\n")
        lines.append(f"{self.format_item_count(len(items), max_items)}\n")

        for rank, item in enumerate(items[:max_items], 1):
            title = item.get("title", "")
            cn_title = self.translate_title(title)
            raw = item.get("raw", {}) or {}
            points = raw.get("score", 0) or 0
            comments = raw.get("comment_count", 0) or 0
            ai_summary = self.format_ai_summary(item)

            lines.append(f"### {rank}. {cn_title}")
            lines.append("")

            # AI 总结
            if ai_summary:
                lines.append(f"> {ai_summary}")
                lines.append("")

            # 热度
            if points or comments:
                points_str = f"⭐ {points:,}" if points else ""
                comments_str = f"💬 {comments}" if comments else ""
                parts = [p for p in [points_str, comments_str] if p]
                if parts:
                    lines.append(" · ".join(parts))
                    lines.append("")

            lines.append("---")

        return "\n".join(lines)
