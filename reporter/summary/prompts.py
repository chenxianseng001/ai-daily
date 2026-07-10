"""AI Daily — 摘要 Prompt 模板（v2.1.3 主编版）

Reporter 扮演 AI 行业主编。
每总结一条内容，需回答：
  1. 发生了什么？
  2. 为什么值得关注？
  3. 它代表了什么行业趋势？
  4. 对开发者 / AI Agent / 开源生态 / 企业应用有什么影响？

禁止机械翻译标题。禁止复述原文。禁止只介绍产品功能。
帮助用户判断：这条新闻值不值得继续花时间了解。
"""

from __future__ import annotations

from typing import Protocol


SYSTEM_CORE = (
    "你是一位资深 AI 行业主编。\n"
    "用中文总结以下信息，回答四个问题：\n"
    "1. 发生了什么？\n"
    "2. 为什么值得关注？\n"
    "3. 代表了什么行业趋势？\n"
    "4. 对开发者/AI Agent/开源生态/企业应用有什么影响？\n\n"
    "要求：\n"
    "- 不是翻译，不是复述原文\n"
    "- 控制在 100~150 字\n"
    "- 不输出原文标签或格式\n"
)


# ── GitHub ──────────────────────────────────────────────────────────


class GitHubPromptBuilder:
    @property
    def system_prompt(self) -> str:
        return SYSTEM_CORE + (
            "重点判断："
            "这个项目是否适合 AI Agent / MCP？"
            "是否值得收藏或尝试？"
            "对开发者有什么实际价值？"
        )

    def build_prompt(self, item: dict, raw_text: str) -> str:
        title = item.get("title", "")
        desc = item.get("description", "") or ""
        raw = item.get("raw", {}) or {}
        stars = raw.get("today_stars", 0) or 0
        total = raw.get("total_stars", 0) or 0
        topics = raw.get("topics", [])
        topic_str = ", ".join(topics[:5]) if topics else ""
        readme = raw_text[:800] if raw_text else ""
        parts = [f"仓库: {title}", f"简介: {desc}"]
        if stars:
            parts.append(f"今日 {stars} Star (总 {total})")
        if topic_str:
            parts.append(f"标签: {topic_str}")
        if readme:
            parts.append(f"\nREADME:\n{readme}")
        return "\n".join(parts)


# ── Hacker News ─────────────────────────────────────────────────────


class HackerNewsPromptBuilder:
    @property
    def system_prompt(self) -> str:
        return SYSTEM_CORE + (
            "重点判断：这篇文章对整个 AI / 科技行业有什么影响？"
            "是否代表了值得关注的趋势或风险。"
        )

    def build_prompt(self, item: dict, raw_text: str) -> str:
        title = item.get("title", "")
        author = item.get("author", "")
        raw = item.get("raw", {}) or {}
        points = raw.get("score", 0) or 0
        comments = raw.get("comment_count", 0) or 0
        body = raw_text[:1500] if raw_text else ""
        cmt_note = "（注意：评论数为 0，请输出【社区观点】暂无社区讨论）" if comments == 0 else ""
        return (
            f"标题: {title}\n作者: {author}\n"
            f"热度: {points} pts, 评论: {comments}{cmt_note}\n"
            f"\n正文:\n{body}"
        )


# ── Product Hunt ────────────────────────────────────────────────────


class ProductHuntPromptBuilder:
    @property
    def system_prompt(self) -> str:
        return SYSTEM_CORE + (
            "重点判断：这个产品值不值得体验？"
            "解决了什么真实问题？"
            "对哪类用户最有价值。"
        )

    def build_prompt(self, item: dict, raw_text: str) -> str:
        name = item.get("title", "")
        tagline = item.get("description", "") or ""
        raw = item.get("raw", {}) or {}
        votes = raw.get("votes_count", 0)
        desc = raw_text[:1200] if raw_text else ""
        return f"产品: {name}\n一句话: {tagline}\n票数: {votes}\n\n描述:\n{desc}"


# ── YouTube — 不生成 AI 摘要 ────────────────────────────────────────


class YouTubePromptBuilder:
    @property
    def system_prompt(self) -> str:
        return ""

    def build_prompt(self, item: dict, raw_text: str) -> str:
        return ""


# ── Twitter ─────────────────────────────────────────────────────────


class TwitterPromptBuilder:
    @property
    def system_prompt(self) -> str:
        return SYSTEM_CORE + (
            "重点判断：这条推文透露了什么行业信号？"
            "是否值得关注其背后的趋势。"
        )

    def build_prompt(self, item: dict, raw_text: str) -> str:
        return (
            f"作者: @{item.get('author', '')}\n"
            f"\n内容:\n{raw_text[:800]}"
        )


# ── 国产 AI ─────────────────────────────────────────────────────────


class ChinaAIPromptBuilder:
    @property
    def system_prompt(self) -> str:
        return SYSTEM_CORE + (
            "重点判断：这条新闻对国内 AI 行业格局有什么影响？"
            "是否代表了国产 AI 的新方向。"
        )

    def build_prompt(self, item: dict, raw_text: str) -> str:
        title = item.get("title", "")
        desc = item.get("description", "") or ""
        body = raw_text[:1500] if raw_text else desc[:500]
        return f"标题: {title}\n简介: {desc}\n\n正文:\n{body}"


# ── 热点事件标题生成 ────────────────────────────────────────────────


class TopEventPromptBuilder:
    """为事件聚类生成中文标题。"""

    @property
    def system_prompt(self) -> str:
        return (
            "你是一位 AI 资讯主编。\n"
            "根据以下跨数据源的事件信息，用一句中文概括核心事件。\n"
            "要求：\n"
            "- 20~30 个汉字\n"
            "- 一眼即可理解事件\n"
            "- 不要使用原标题，用自己的话重新概括\n"
            "- 只输出标题本身，不要多余字符\n"
        )

    def build_prompt(self, title: str, source_summary: str, description: str) -> str:
        return (
            f"涉及来源: {source_summary}\n"
            f"原始标题: {title}\n"
            f"概述: {description[:300]}\n"
            f"\n请生成一句自然、准确的中文标题（20~30 字）。"
        )


# ── 注册表 ─────────────────────────────────────────────────────────

BUILDERS: dict[str, type] = {
    "github_trending": GitHubPromptBuilder,
    "hacker_news": HackerNewsPromptBuilder,
    "product_hunt": ProductHuntPromptBuilder,
    "youtube": YouTubePromptBuilder,
    "twitter": TwitterPromptBuilder,
    "china_ai": ChinaAIPromptBuilder,
}


def get_prompt_builder(source: str) -> PromptBuilder:
    cls = BUILDERS.get(source)
    if cls is None:
        return GitHubPromptBuilder()
    return cls()
