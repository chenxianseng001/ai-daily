"""AI Daily — Product Hunt Section — v2.1"""

from __future__ import annotations

from typing import Any

from reporter.base_section import BaseSection


class ProductHuntSection(BaseSection):
    @property
    def name(self) -> str:
        return "Product Hunt"

    @property
    def source_name(self) -> str:
        return "product_hunt"

    def render(self, items: list[dict], config: dict | None = None) -> str:
        if self.should_skip(items):
            return ""
        cfg = config or {}
        max_items = cfg.get("ph_max_items", 10)
        lines = []

        lines.append(f"## 🚀 Product Hunt\n")
        lines.append(f"{self.format_item_count(len(items), max_items)}\n")

        for rank, item in enumerate(items[:max_items], 1):
            name = item.get("title", "")
            raw = item.get("raw", {}) or {}
            votes = raw.get("votes_count", 0)
            ai_summary = self.format_ai_summary(item)

            lines.append(f"### {rank}. {name}")
            lines.append("")

            # AI 总结
            if ai_summary:
                lines.append(f"> {ai_summary}")
                lines.append("")

            # 热度
            score_str = self.format_raw_score(item)
            if not score_str:
                score_str = f"⭐ {votes}" if votes else ""
            if score_str:
                lines.append(score_str)
                lines.append("")

            lines.append("---")

        return "\n".join(lines)
