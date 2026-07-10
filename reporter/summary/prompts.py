"""AI Daily — 摘要 Prompt 模板

每个数据源有独立的摘要策略。
"""

from __future__ import annotations

from typing import Protocol


# ── Prompt 构造协议 ───────────────────────────────────────────────────


class PromptBuilder(Protocol):
    """摘要 Prompt 构造器协议。"""

    def build_prompt(self, item: dict, raw_text: str) -> str:
        """根据 item 和 raw 文件内容构造摘要 prompt。"""
        ...

    @property
    def system_prompt(self) -> str:
        """系统提示词。"""
        return "你是一个专业的中文 AI 资讯摘要助手。请用简洁的中文总结以下内容，突出核心信息。"


# ── 各数据源 Prompt 构造器 ──────────────────────────────────────────


class GitHubPromptBuilder:
    """GitHub 项目摘要。"""

    @property
    def system_prompt(self) -> str:
        return (
            "你是一个专业的中文技术摘要助手。请用简洁的中文总结该开源项目，"
            "包括：项目是做什么的、解决了什么问题、适合哪些开发者使用。"
            "控制在 100 字以内。"
        )

    def build_prompt(self, item: dict, raw_text: str) -> str:
        title = item.get("title", "")
        desc = item.get("description", "") or ""
        raw = item.get("raw", {}) or {}
        stars = raw.get("today_stars", 0)
        total = raw.get("total_stars", 0)
        lang = raw.get("primary_language", "")
        return (
            f"项目名称: {title}\n"
            f"简介: {desc}\n"
            f"今日新增 Star: {stars}, 总 Star: {total}\n"
            f"语言: {lang}\n"
            f"\nREADME 摘要:\n{raw_text[:2000]}\n"
            f"\n请用中文总结这个项目。"
        )


class HackerNewsPromptBuilder:
    """Hacker News 讨论摘要。"""

    @property
    def system_prompt(self) -> str:
        return (
            "你是一个专业的中文资讯摘要助手。请用简洁的中文总结以下 Hacker News 讨论，"
            "包括：事件本身、核心观点、讨论焦点。控制在 100 字以内。"
        )

    def build_prompt(self, item: dict, raw_text: str) -> str:
        title = item.get("title", "")
        author = item.get("author", "")
        raw = item.get("raw", {}) or {}
        points = raw.get("score", 0)
        comments = raw.get("comment_count", 0)
        return (
            f"标题: {title}\n"
            f"作者: {author}\n"
            f"Points: {points}, 评论: {comments}\n"
            f"\n正文:\n{raw_text[:2000]}\n"
            f"\n请用中文总结。"
        )


class ProductHuntPromptBuilder:
    """Product Hunt 产品摘要。"""

    @property
    def system_prompt(self) -> str:
        return (
            "你是一个专业的中文产品摘要助手。请用简洁的中文总结该产品，"
            "包括：产品是做什么的、解决什么问题、目标用户是谁、特色功能。"
            "控制在 100 字以内。"
        )

    def build_prompt(self, item: dict, raw_text: str) -> str:
        name = item.get("title", "")
        tagline = item.get("description", "") or ""
        raw = item.get("raw", {}) or {}
        votes = raw.get("votes_count", 0)
        topics = raw.get("topics", [])
        return (
            f"产品名称: {name}\n"
            f"一句话介绍: {tagline}\n"
            f"Votes: {votes}\n"
            f"分类: {', '.join(topics)}\n"
            f"\n产品描述:\n{raw_text[:2000]}\n"
            f"\n请用中文总结。"
        )


class YouTubePromptBuilder:
    """YouTube 视频摘要。"""

    @property
    def system_prompt(self) -> str:
        return (
            "你是一个专业的中文视频摘要助手。请用简洁的中文总结该视频的核心内容。"
            "控制在 100 字以内。"
        )

    def build_prompt(self, item: dict, raw_text: str) -> str:
        title = item.get("title", "")
        channel = item.get("author", "")
        raw = item.get("raw", {}) or {}
        duration = raw.get("duration_seconds", 0)
        m, s = divmod(duration, 60)
        dur_str = f"{m}:{s:02d}" if duration else "?"
        return (
            f"视频标题: {title}\n"
            f"频道: {channel}\n"
            f"时长: {dur_str}\n"
            f"\n视频描述:\n{raw_text[:2000]}\n"
            f"\n请用中文总结这个视频讲了什么。"
        )


class TwitterPromptBuilder:
    """X 推文摘要。"""

    @property
    def system_prompt(self) -> str:
        return (
            "你是一个专业的中文资讯摘要助手。请用简洁的中文总结以下推文的核心观点。"
            "控制在 50 字以内。"
        )

    def build_prompt(self, item: dict, raw_text: str) -> str:
        return (
            f"推文作者: @{item.get('author', '')}\n"
            f"\n推文内容:\n{raw_text[:1000]}\n"
            f"\n请用中文总结。"
        )


class ChinaAIPromptBuilder:
    """国产 AI 新闻摘要。"""

    @property
    def system_prompt(self) -> str:
        return (
            "你是一个专业的中文新闻摘要助手。请用简洁的中文总结以下新闻的核心内容。"
            "控制在 100 字以内。"
        )

    def build_prompt(self, item: dict, raw_text: str) -> str:
        title = item.get("title", "")
        desc = item.get("description", "") or ""
        return (
            f"标题: {title}\n"
            f"简介: {desc}\n"
            f"\n正文:\n{raw_text[:2000]}\n"
            f"\n请用中文总结。"
        )


# ── 构造器注册表 ─────────────────────────────────────────────────────

BUILDERS: dict[str, type] = {
    "github_trending": GitHubPromptBuilder,
    "hacker_news": HackerNewsPromptBuilder,
    "product_hunt": ProductHuntPromptBuilder,
    "youtube": YouTubePromptBuilder,
    "twitter": TwitterPromptBuilder,
    "china_ai": ChinaAIPromptBuilder,
}


def get_prompt_builder(source: str) -> PromptBuilder:
    """获取指定数据源的 Prompt 构造器。"""
    cls = BUILDERS.get(source)
    if cls is None:
        return GitHubPromptBuilder()
    return cls()
