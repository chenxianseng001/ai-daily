"""AI Daily — GitHub Trending Section"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reporter.base_section import BaseSection
from core.logger import get_logger

logger = get_logger("ai_daily.reporter")


class GitHubSection(BaseSection):
    """GitHub Trending 日报 Section。"""

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
        max_items = len(items) if show_all else min(cfg.get("github_max_items", 15), len(items))

        # 按 today_stars 降序
        sorted_items = sorted(
            items, key=lambda x: (x.get("raw_score", 0) or 0), reverse=True
        )
        display_items = sorted_items[:max_items]

        lines: list[str] = []
        lines.append(f"## 📦 GitHub Trending\n")
        lines.append(f"共 {len(sorted_items)} 个项目")
        if max_items < len(sorted_items):
            lines.append(f"（展示前 {max_items} 名）")
        lines.append("")

        for rank, item in enumerate(display_items, 1):
            raw = item.get("raw", {})
            stars = item.get("raw_score", 0) or 0
            total = raw.get("total_stars", 0)
            desc = item.get("description", "") or ""
            author = item.get("author", "")
            lang = raw.get("primary_language") or ""
            built_by = raw.get("built_by", [])
            topics = raw.get("topics", [])

            lines.append(f"### {rank}. {item['title']}")
            if author:
                lines.append(f"**{author}**")
            lines.append("")
            lines.append(f"⭐ 今日 **+{stars:,}** / 总 {total:,}")
            if lang:
                lines.append(f"🔤 `{lang}`")
            if built_by:
                lines.append(f"👥 {', '.join(built_by[:3])}")
            if topics:
                lines.append(f"🏷️ {', '.join(topics[:5])}")
            lines.append("")
            if desc:
                lines.append(f"{desc}")
            lines.append("")

            # AI 摘要
            summary = self.format_summary(item)
            if summary:
                lines.append(summary)
                lines.append("")

            # README 预览
            readme_path = raw.get("readme_path")
            if readme_path:
                preview = self._load_raw_preview(readme_path, max_chars=800)
                if preview:
                    lines.append("<details><summary>README 摘要</summary>\n")
                    lines.append(f"> {preview}")
                    lines.append("</details>")
                    lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _load_raw_preview(raw_path: str | None, max_chars: int = 800) -> str:
        if not raw_path:
            return ""
        path = Path(raw_path)
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8")
        # 提取有意义的文本，跳过 HTML 标签
        import re
        clean = re.sub(r"<[^>]+>", "", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        if len(clean) > max_chars:
            clean = clean[:max_chars] + "..."
        return clean
