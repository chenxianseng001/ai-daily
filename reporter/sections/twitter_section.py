"""AI Daily — X (Twitter) Section — v2.1"""

from __future__ import annotations

from typing import Any

from reporter.base_section import BaseSection


class TwitterSection(BaseSection):
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
        show_links = self.should_show_link(cfg)
        lines = []

        # 过滤：只保留原创推文
        original = []
        for item in items:
            text = item.get("description", "") or ""
            raw = item.get("raw", {}) or {}
            raw_text = raw.get("text", "") or ""
            if self.twitter_is_original_tweet(text) or self.twitter_is_original_tweet(raw_text):
                original.append(item)

        shown = original[:max_items]
        accounts = set(i.get("author", "") for i in shown)

        lines.append(f"## 🐦 X (Twitter)\n")
        lines.append(f"来自 {len(accounts)} 个账号，{self.format_item_count(len(original), len(shown))}\n")

        for rank, item in enumerate(shown, 1):
            author = item.get("author", "?")
            ai_summary = self.format_ai_summary(item)

            lines.append(f"### {rank}. @{author}")
            lines.append("")

            # AI 总结
            if ai_summary:
                lines.append(f"> {ai_summary}")
                lines.append("")

            # 可选择显示链接
            if show_links:
                url = item.get("url", "")
                if url:
                    lines.append(f"[🔗 推文]({url})")
                    lines.append("")

            lines.append("---")

        return "\n".join(lines)
