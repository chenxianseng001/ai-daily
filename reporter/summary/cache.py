"""AI Daily — 摘要缓存

按 content_hash 缓存摘要内容，避免重复调用 LLM。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("ai_daily.summary_cache")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = PROJECT_ROOT / "cache" / "summaries"


class SummaryCache:
    """摘要缓存管理器。

    以 content_hash 为键，缓存 AI 摘要文本。
    cache/summaries/{hash[:2]}/{hash[2:]}.json
    """

    def __init__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get(self, content_hash: str) -> str | None:
        """获取缓存的摘要。不存在返回 None。"""
        path = self._path(content_hash)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("summary")
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, content_hash: str, summary: str) -> None:
        """保存摘要到缓存。"""
        path = self._path(content_hash)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"hash": content_hash, "summary": summary}, ensure_ascii=False),
            encoding="utf-8",
        )

    def hit_rate(self) -> float:
        """计算缓存命中率（基于当前 session 统计）。"""
        if self._total == 0:
            return 0.0
        return self._hits / self._total

    def _path(self, content_hash: str) -> Path:
        return CACHE_DIR / content_hash[:2] / f"{content_hash[2:]}.json"

    # session 统计
    _hits: int = 0
    _total: int = 0

    def get_with_stats(self, content_hash: str) -> str | None:
        """带统计的缓存读取。"""
        self._total += 1
        result = self.get(content_hash)
        if result:
            self._hits += 1
        return result
