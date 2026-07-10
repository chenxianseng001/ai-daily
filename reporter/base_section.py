"""AI Daily — 报告 Section 基类

每个数据源对应一个 Section，继承 BaseSection 实现 render()。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.logger import get_logger

logger = get_logger("ai_daily.reporter")


class BaseSection(ABC):
    """报告 Section 基类。

    所有数据源的 Section 必须继承此类。
    后续新增数据源只需新建一个 Section 文件，无需修改已有代码。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Section 名称，用于 TOC 和日志。"""
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """对应的 Collector 数据源标识。"""
        ...

    @abstractmethod
    def render(self, items: list[dict], config: dict | None = None) -> str:
        """将采集数据渲染为 Markdown。

        Args:
            items: 该数据源的所有 items（统一 CollectionItem 格式）
            config: 该 Section 的配置参数

        Returns:
            Markdown 字符串
        """
        ...

    def should_skip(self, items: list[dict]) -> bool:
        """判断是否应跳过此 Section（无数据时）。"""
        if not items:
            logger.info("[section:%s] No items, skipping", self.name)
            return True
        return False

    def status_badge(self, status: str) -> str:
        """返回采集状态徽章。"""
        badges = {
            "success": "✅",
            "partial": "⚠️",
            "error": "❌",
            "no_cache": "⏳",
        }
        return badges.get(status, "❓")

    @staticmethod
    def format_summary(item: dict) -> str:
        """格式化 AI 摘要（如果存在）。"""
        summary = item.get("_ai_summary")
        if summary:
            return f"> 💡 **AI 摘要:** {summary}"
        return ""
