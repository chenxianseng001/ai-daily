"""AI Daily — 报告 Section 基类

每个数据源对应一个 Section，继承 BaseSection 实现 render()。

v2.1 改进：
  - 所有输出统一为中文
  - 默认隐藏链接
  - 格式统一为：标题 + AI 总结 + 为什么值得关注
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from core.logger import get_logger
from core.utils import clean_html, load_raw_preview

logger = get_logger("ai_daily.reporter")


class BaseSection(ABC):
    """报告 Section 基类。"""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...

    @abstractmethod
    def render(self, items: list[dict], config: dict | None = None) -> str:
        ...

    def should_skip(self, items: list[dict]) -> bool:
        if not items:
            logger.info("[section:%s] No items, skipping", self.name)
            return True
        return False

    def status_badge(self, status: str) -> str:
        badges = {
            "success": "✅",
            "partial": "⚠️",
            "error": "❌",
            "no_cache": "⏳",
        }
        return badges.get(status, "❓")

    # ── 共享工具 ───────────────────────────────────────────────────

    @staticmethod
    def safe_text(text: str | None, default: str = "") -> str:
        """安全获取文本，去除 HTML 标签。"""
        if not text:
            return default
        return clean_html(text)

    @staticmethod
    def should_show_link(config: dict | None) -> bool:
        """是否显示链接（默认不显示）。"""
        if config is None:
            return False
        return bool(config.get("show_links", False))

    @staticmethod
    def format_item_count(total: int, shown: int) -> str:
        """格式化条目计数。"""
        if shown >= total:
            return f"共 {total} 条"
        return f"共 {total} 条，展示 {shown} 条"

    @staticmethod
    def format_ai_summary(item: dict) -> str:
        """获取 AI 摘要文本。不存在返回空字符串。"""
        return item.get("_ai_summary", "") or ""

    @staticmethod
    def format_raw_score(item: dict) -> str:
        """格式化热度。"""
        score = item.get("raw_score", 0) or 0
        if score > 0:
            return f"🔥 {score:,}"
        return ""

    @staticmethod
    def format_github_title(item: dict) -> str:
        """格式化为 作者/项目名 格式。"""
        title = item.get("title", "")
        author = item.get("author", "")
        if author:
            return f"{author} / {title}"
        return title

    @staticmethod
    def translate_title(title: str, max_chars: int = 30) -> str:
        """翻译英文标题为自然中文（浅调用，使用当前 AI Provider）。"""
        if not title or len(title) < 5:
            return title
        # 检查是否已经是中文
        import re
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', title)
        if len(chinese_chars) >= 3:
            return title  # 已有足够中文，不翻译

        # 简短标题直接返回
        if len(title) < 15:
            return title

        # 调用 AI 翻译
        try:
            import os
            from reporter.summary.generator import PROVIDER_REGISTRY, OpenAICompatibleProvider
            api_key = os.environ.get("AI_SUMMARY_API_KEY", "")
            provider = os.environ.get("AI_SUMMARY_PROVIDER", "openai")
            model = os.environ.get("AI_SUMMARY_MODEL", "")
            cls = PROVIDER_REGISTRY.get(provider, OpenAICompatibleProvider)
            p = cls(api_key=api_key, model=model)
            system = "你是一个翻译助手。将以下英文标题翻译成自然中文。只输出中文翻译，不要多余字符。不超过20个字。"
            result = p.chat(system, f"翻译为中文：{title}")
            if result and len(result) > 3:
                return result.strip().strip('"').strip('「」')
        except Exception:
            pass
        return title

    @staticmethod
    def twitter_is_original_tweet(text: str) -> bool:
        """判断推文是否为原创（过滤回复、转发等）。"""
        if not text:
            return False
        # 过滤回复 (starts with @username)
        if re.match(r"^\s*@\w+", text):
            return False
        # 过滤 "R to @" 回复
        if text.strip().startswith("R to @"):
            return False
        # 过滤单句感叹/感谢/套话
        short = text.strip().lower()
        one_liners = {"thanks", "awesome", "great", "nice", "wow", "this",
                      "yes", "no", "lol", "lmao", "😂", "🔥", "❤️", "🙏",
                      "amazing", "haha", "cool", "👍", "💯", "interesting"}
        if short in one_liners or len(short.split()) <= 3:
            return False
        return True

    @staticmethod
    def format_link(url: str | None, label: str) -> str:
        """格式化链接。"""
        if not url:
            return ""
        return f"[{label}]({url})"
