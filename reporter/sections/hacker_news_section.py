"""AI Daily — Hacker News Section"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reporter.base_section import BaseSection
from core.logger import get_logger

logger = get_logger("ai_daily.reporter")


class HackerNewsSection(BaseSection):
    """Hacker News 日报 Section。"""

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

        # 按 Points 降序
        sorted_items = sorted(
            items, key=lambda x: (x.get("raw_score", 0) or 0), reverse=True
        )
        display_items = sorted_items[:max_items]

        lines: list[str] = []
        lines.append(f"## 📰 Hacker News\n")
        lines.append(f"共 {len(sorted_items)} 条讨论，展示 Top {len(display_items)}\n")

        for rank, item in enumerate(display_items, 1):
            raw = item.get("raw", {})
            title = item.get("title", "")
            author = item.get("author", "?")
            points = item.get("raw_score", 0) or 0
            comments = raw.get("comment_count", 0)
            hn_url = raw.get("hn_url", "")
            external_url = raw.get("external_url")
            text_path = raw.get("text_path")
            ext_path = raw.get("external_content_path")

            # 标题行（带链接）
            if external_url:
                lines.append(f"### {rank}. [{title}]({external_url})")
            else:
                lines.append(f"### {rank}. {title}")

            lines.append(f"👤 {author} · ⭐ **{points}** · 💬 {comments}")
            lines.append("")

            # AI 摘要
            summary = self.format_summary(item)
            if summary:
                lines.append(summary)
                lines.append("")

            # 外部文章预览
            if ext_path:
                preview = self._load_article_preview(ext_path, max_chars=500)
                if preview:
                    lines.append(f"> {preview}")
                    lines.append("")

            # 讨论原文预览
            if text_path and not ext_path:
                preview = self._load_article_preview(text_path, max_chars=500)
                if preview:
                    lines.append(f"> {preview}")
                    lines.append("")

            lines.append(f"[🔗 HN 讨论]({hn_url})")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _load_article_preview(raw_path: str | None, max_chars: int = 500) -> str:
        if not raw_path:
            return ""
        path = Path(raw_path)
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8")
        # 清理 HTML
        import re
        clean = re.sub(r"<[^>]+>", "", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        if len(clean) > max_chars:
            clean = clean[:max_chars] + "..."
        return clean
