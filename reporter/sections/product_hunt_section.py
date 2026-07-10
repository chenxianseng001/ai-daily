"""AI Daily — Product Hunt Section"""

from __future__ import annotations

from typing import Any

from reporter.base_section import BaseSection


class ProductHuntSection(BaseSection):
    """Product Hunt 日报 Section。"""

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

        sorted_items = sorted(
            items, key=lambda x: (x.get("raw_score", 0) or 0), reverse=True
        )
        display_items = sorted_items[:max_items]

        lines: list[str] = []
        lines.append(f"## 🚀 Product Hunt\n")
        lines.append(f"共 {len(sorted_items)} 个产品，展示 Top {len(display_items)}\n")

        for rank, item in enumerate(display_items, 1):
            raw = item.get("raw", {})
            name = item.get("title", "")
            tagline = item.get("description", "") or ""
            votes = raw.get("votes_count", 0)
            topics = raw.get("topics", [])
            makers = raw.get("makers", [])
            website = raw.get("website_url")
            ph_url = raw.get("ph_url")

            lines.append(f"### {rank}. {name}")
            lines.append("")
            lines.append(f"{tagline}")
            lines.append("")

            # AI 摘要
            summary = self.format_summary(item)
            if summary:
                lines.append(summary)
                lines.append("")

            lines.append(f"⭐ **{votes}** votes")
            if topics:
                lines.append(f"🏷️ {', '.join(topics[:5])}")
            if makers:
                maker_names = [m.get("name", m.get("username", "")) for m in makers[:2]]
                lines.append(f"👤 {', '.join(maker_names)}")
            lines.append("")
            if website:
                lines.append(f"🔗 [官网]({website})")
            if ph_url:
                lines.append(f"[Product Hunt]({ph_url})")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)
