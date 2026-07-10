"""AI Daily — 国产 AI Section — v2.1.5

AI Summary 失败时必须降级，绝不能空白。
"""

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

            # AI 总结 — 必须非空
            fallback = self._get_china_ai_fallback(item)
            display = ai_summary if ai_summary else fallback
            if display:
                lines.append(f"> {display}")
                lines.append("")

            lines.append("---")

        return "\n".join(lines)

    @staticmethod
    def _get_china_ai_fallback(item: dict) -> str:
        """当 AI Summary 为空时的降级方案。"""
        desc = item.get("description", "") or ""
        desc_clean = BaseSection.safe_text(desc)
        if desc_clean and len(desc_clean) > 10:
            short = desc_clean[:150]
            if len(desc_clean) > 150:
                short += "..."
            return short

        # 尝试加载 raw 文件
        raw = item.get("raw", {}) or {}
        for key in ("content_path", "text_path", "description_path"):
            rp = raw.get(key)
            if rp:
                from pathlib import Path
                p = Path(rp)
                if p.exists():
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    text = BaseSection.safe_text(text)[:200]
                    if text:
                        return text

        # 最终保底
        return "暂无可用摘要"
