"""AI Daily — GitHub Trending Section — v2.1"""

from __future__ import annotations

from typing import Any

from reporter.base_section import BaseSection


class GitHubSection(BaseSection):
    @property
    def name(self) -> str:
        return "GitHub Trending"

    @property
    def source_name(self) -> str:
        return "github_trending"

    def render(self, items: list[dict], config: dict | None = None) -> str:
        if self.should_skip(items):
            return ""
        cfg = config or {}
        show_all = cfg.get("github_show_all", True)
        max_items = cfg.get("github_max_items", 15) if not show_all else len(items)
        lines = []

        lines.append(f"## 📦 GitHub Trending\n")
        lines.append(f"{self.format_item_count(len(items), max_items)}\n")

        for rank, item in enumerate(items[:max_items], 1):
            title = item.get("title", "")
            raw = item.get("raw", {}) or {}
            today_stars = raw.get("today_stars", 0) or 0
            total_stars = raw.get("total_stars", 0) or 0
            ai_summary = self.format_ai_summary(item)

            lines.append(f"### {rank}. {title}")
            lines.append("")

            # Star 信息
            if today_stars > 0:
                total_str = f" / 总 {total_stars:,}" if total_stars else ""
                lines.append(f"⭐ 今日 **+{today_stars:,}{total_str}**")
                lines.append("")

            # AI 总结
            if ai_summary:
                lines.append(f"> {ai_summary}")
                lines.append("")

            lines.append("---")

        return "\n".join(lines)
