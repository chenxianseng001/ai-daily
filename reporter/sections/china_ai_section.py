"""AI Daily — 国产 AI Section"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reporter.base_section import BaseSection


class ChinaAISection(BaseSection):
    """国产 AI 新闻日报 Section。"""

    @property
    def name(self) -> str:
        return "国产 AI"

    @property
    def source_name(self) -> str:
        return "china_ai"

    def render(self, items: list[dict], config: dict | None = None) -> str:
        if self.should_skip(items):
            return ""

        cfg = config or {}
        max_items = cfg.get("china_ai_max_items", 10)

        sorted_items = sorted(
            items,
            key=lambda x: x.get("published_at", "") or "",
            reverse=True,
        )
        display_items = sorted_items[:max_items]

        lines: list[str] = []
        lines.append(f"## 🇨🇳 国产 AI\n")
        lines.append(f"共 {len(sorted_items)} 条，展示 {len(display_items)} 条\n")

        for rank, item in enumerate(display_items, 1):
            title = item.get("title", "")
            source_site = (item.get("tags") or [None])[0]
            author = item.get("author")
            published = item.get("published_at", "")
            url = item.get("url", "")
            desc = item.get("description", "") or ""

            date_str = published[:10] if published else ""

            lines.append(f"### {rank}. [{title}]({url})")
            lines.append("")
            src_parts = [source_site] if source_site else []
            if author:
                src_parts.append(author)
            if date_str:
                src_parts.append(date_str)
            lines.append(" · ".join(src_parts))
            lines.append("")

            # AI 摘要
            summary = self.format_summary(item)
            if summary:
                lines.append(summary)
                lines.append("")

            if desc:
                lines.append(f"{desc}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)
