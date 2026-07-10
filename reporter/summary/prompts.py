"""AI Daily — 摘要 Prompt 模板

每个数据源有独立的摘要策略。
所有输出必须为中文。
"""

from __future__ import annotations

from typing import Protocol


# ── Prompt 构造协议 ───────────────────────────────────────────────────


class PromptBuilder(Protocol):
    """摘要 Prompt 构造器协议。"""

    def build_prompt(self, item: dict, raw_text: str) -> str:
        ...

    @property
    def system_prompt(self) -> str:
        return ""


# ── 统一系统提示 ─────────────────────────────────────────────────────

SYSTEM_CORE = (
    "你是一个专业的中文 AI 资讯摘编助手。你的任务是用自然中文总结以下内容。\n"
    "规则：\n"
    "1. 所有输出必须为纯中文。\n"
    "2. 不是翻译——是阅读原文后，用自己的话重新表达。\n"
    "3. 每段总结控制在 100~150 字。\n"
    "4. 最后增加一段「为什么值得关注」，1~2 句话，说明这件事的重要性。\n"
    "5. 不要输出任何 URL、标签、JSON。\n"
    "6. 不要使用 AI 套话，直接说重点。\n"
)


# ── 各数据源 Prompt 构造器 ──────────────────────────────────────────


class GitHubPromptBuilder:
    """GitHub 项目：AI 总结中文输出。"""

    @property
    def system_prompt(self) -> str:
        return SYSTEM_CORE + (
            "阅读以下 GitHub 仓库信息，输出中文总结。\n"
            "格式要求：\n"
            "【项目总结】100~150 字：这个项目是做什么的？解决什么问题？适合哪些人？\n"
            "【为什么关注】1~2 句话说明该项目今日热度高的原因。\n"
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
            f"编程语言: {lang}\n"
            f"\nREADME 概要:\n{raw_text[:1500]}\n"
            f"\n请用中文总结。"
        )


class HackerNewsPromptBuilder:
    """Hacker News：AI 总结中文 + 社区讨论 + 为什么关注。"""

    @property
    def system_prompt(self) -> str:
        return SYSTEM_CORE + (
            "阅读以下 Hacker News 讨论，输出中文总结。\n"
            "格式要求：\n"
            "【事件总结】100~150 字：这篇文章/讨论的核心内容是什么？\n"
            "【社区观点】100 字左右：社区的支持观点、反对观点、争议焦点。\n"
            "【为什么关注】1~2 句话：为什么这条讨论值得今天关注。\n"
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
    """Product Hunt：AI 总结中文 + 为什么关注。"""

    @property
    def system_prompt(self) -> str:
        return SYSTEM_CORE + (
            "阅读以下产品信息，输出中文总结。\n"
            "格式要求：\n"
            "【产品总结】100~150 字：这是什么产品？解决什么问题？适合哪些用户？有什么特色功能？\n"
            "【为什么关注】1~2 句话：为什么这款产品值得今天关注。\n"
        )

    def build_prompt(self, item: dict, raw_text: str) -> str:
        name = item.get("title", "")
        tagline = item.get("description", "") or ""
        raw = item.get("raw", {}) or {}
        votes = raw.get("votes_count", 0)
        return (
            f"产品名称: {name}\n"
            f"一句话介绍: {tagline}\n"
            f"Votes: {votes}\n"
            f"\n产品描述:\n{raw_text[:2000]}\n"
            f"\n请用中文总结。"
        )


class YouTubePromptBuilder:
    """YouTube 视频：AI 总结中文。"""

    @property
    def system_prompt(self) -> str:
        return SYSTEM_CORE + (
            "阅读以下视频信息，输出中文总结。\n"
            "格式要求：\n"
            "【视频总结】100~150 字：这个视频讲了什么核心内容？\n"
            "【为什么关注】1~2 句话：为什么值得看。\n"
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
            f"\n请用中文总结。"
        )


class TwitterPromptBuilder:
    """X 推文：AI 总结中文 + 为什么关注。"""

    @property
    def system_prompt(self) -> str:
        return SYSTEM_CORE + (
            "阅读以下推文，输出中文总结。\n"
            "格式要求：\n"
            "【内容总结】50~100 字：这条推文的核心里点。\n"
            "【为什么关注】1 句话：为什么这条推文值得关注。\n"
        )

    def build_prompt(self, item: dict, raw_text: str) -> str:
        return (
            f"作者: @{item.get('author', '')}\n"
            f"\n推文内容:\n{raw_text[:1000]}\n"
            f"\n请用中文总结。"
        )


class ChinaAIPromptBuilder:
    """国产 AI 新闻：AI 总结中文 + 为什么关注。"""

    @property
    def system_prompt(self) -> str:
        return SYSTEM_CORE + (
            "阅读以下 AI 新闻，输出中文总结。\n"
            "格式要求：\n"
            "【新闻总结】100~150 字：这条新闻的核心内容是什么？\n"
            "【为什么关注】1~2 句话：为什么这条新闻值得关注。\n"
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
