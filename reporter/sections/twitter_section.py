"""AI Daily — X (Twitter) Section — v2.1.4

改进：
  - 事件去重：同一事件仅保留信息量最高的推文
  - 保持：仅展示原创 Tweet
"""

from __future__ import annotations

from typing import Any

from reporter.base_section import BaseSection

# 用于推文去重的关键词
TWITTER_KEYWORDS = [
    "openai", "chatgpt", "gpt", "claude", "gemini", "llama",
    "deepseek", "anthropic", "google", "microsoft", "meta",
    "cursor", "vercel", "copilot", "codex", "grok",
    "agent", "mcp", "release", "launch", "announce",
    "funding", "acquisit", "partnership",
]


def _extract_tweet_topics(text: str) -> set[str]:
    """从推文文本中提取话题关键词。"""
    if not text:
        return set()
    lower = text.lower()
    found = set()
    for kw in TWITTER_KEYWORDS:
        if kw in lower:
            found.add(kw)
    return found


def _dedup_tweets(items: list[dict]) -> list[dict]:
    """对推文进行事件去重。

    相同话题的推文只保留信息量最高的一条。
    """
    if not items:
        return []

    # 按话题分组
    groups: dict[frozenset, list[dict]] = {}
    for item in items:
        text = item.get("description", "") or ""
        raw = item.get("raw", {}) or {}
        source = raw.get("text", "") or text
        topics = _extract_tweet_topics(source)
        # 无关键词的推文各自独立
        key = frozenset(topics) if topics else frozenset([id(item)])
        groups.setdefault(key, []).append(item)

    # 每个分组保留 AI Summary 最长的
    result = []
    for key, group in groups.items():
        if len(group) == 1:
            result.append(group[0])
        else:
            best = max(
                group,
                key=lambda x: len(x.get("_ai_summary", "") or "")
            )
            result.append(best)
    return result


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

        # 事件去重
        deduped = _dedup_tweets(original)
        shown = deduped[:max_items]
        accounts = set(i.get("author", "") for i in shown)

        dedup_count = len(original) - len(deduped)

        lines.append(f"## 🐦 X (Twitter)\n")
        if dedup_count > 0:
            lines.append(
                f"来自 {len(accounts)} 个账号 · {len(deduped)} 条原创 "
                f"（已合并 {dedup_count} 条同话题推文），展示 {len(shown)} 条\n"
            )
        else:
            lines.append(
                f"来自 {len(accounts)} 个账号，{self.format_item_count(len(original), len(shown))}\n"
            )

        for rank, item in enumerate(shown, 1):
            author = item.get("author", "?")
            ai_summary = self.format_ai_summary(item)

            lines.append(f"### {rank}. @{author}")
            lines.append("")

            if ai_summary:
                lines.append(f"> {ai_summary}")
                lines.append("")

            if show_links:
                url = item.get("url", "")
                if url:
                    lines.append(f"[🔗 推文]({url})")
                    lines.append("")

            lines.append("---")

        return "\n".join(lines)
