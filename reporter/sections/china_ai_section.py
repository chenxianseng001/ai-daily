"""AI Daily — 国产 AI Section — v2.1"""

from __future__ import annotations

from typing import Any

from reporter.base_section import BaseSection


class ChinaAISection(BaseSection):
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
        lines = []

        lines.append(f"## 🇨🇳 国产 AI\n")
        lines.append(f"{self.format_item_count(len(items), max_items)}\n")

        for rank, item in enumerate(items[:max_items], 1):
            title = item.get("title", "")
            source = item.get("author", "")
            ai_summary = self.format_ai_summary(item)

            lines.append(f"### {rank}. {title}")
            if source:
                lines.append(f"**{source}**")
            lines.append("")

            # AI 总结
            if ai_summary:
                lines.append(f"> {ai_summary}")
                lines.append("")
            else:
                # 回退到 description
                desc = self.safe_text(item.get("description", ""))[:200]
                if desc:
                    lines.append(f"{desc}")
                    lines.append("")

            lines.append("---")

        return "\n".join(lines)
