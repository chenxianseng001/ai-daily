"""AI Daily — Event Clustering（事件聚类）

从多个数据源中识别同一 AI 事件，合并展示。

聚类策略：
  1. URL 去重：相同外部 URL 视为同一事件
  2. 标题相似度：Jaccard 词重叠 + 关键词匹配
  3. 关键词聚类：预定义 AI 关键词匹配

不修改 Data Contract，只读取 Collector 缓存的 JSON。
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("ai_daily.cluster")

# 最小相似度阈值
SIMILARITY_THRESHOLD = 0.35

# ── Event 数据结构 ────────────────────────────────────────────────────


@dataclass
class Event:
    """一个聚类事件，聚合来自多个数据源的相关信息。"""

    title: str
    """事件标题（取最清晰的一条）"""

    description: str
    """事件描述"""

    sources: list[str]
    """涉及的数据源列表"""

    items: list[dict]
    """原始 items"""

    total_score: int
    """综合热度（各源 score 之和）"""

    max_score: int
    """最高单源热度"""

    item_count: int
    """聚合的条数"""

    source_count: int
    """涉及的数据源数量"""

    top_keywords: list[str]
    """事件关键词"""

    @property
    def source_summary(self) -> str:
        """来源摘要。"""
        counts = Counter(self.sources)
        return ", ".join(f"{s}×{c}" for s, c in counts.most_common())


# ── 文本处理 ──────────────────────────────────────────────────────────


def normalize_title(title: str) -> str:
    """标准化标题：小写、去标点、分词。"""
    if not title:
        return ""
    t = title.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def tokenize(text: str) -> set[str]:
    """分词。"""
    return set(normalize_title(text).split())


def jaccard_similarity(a: set, b: set) -> float:
    """Jaccard 相似度。"""
    if not a or not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union)


# ── 关键词提取 ────────────────────────────────────────────────────────


# AI 领域核心关键词（用于匹配同一事件）
AI_KEYWORDS = [
    # 模型名称
    "gpt", "gpt-4", "gpt-5", "claude", "gemini", "llama", "mistral",
    "deepseek", "qwen", "kimi", "minimax", "glm", "yi",
    "dall-e", "midjourney", "stable diffusion", "sora",
    # 公司/组织
    "openai", "anthropic", "google deepmind", "google ai", "microsoft",
    "meta", "xai", "apple", "amazon", "nvidia", "ibm",
    "hugging face", "cursor", "vercel", "github copilot",
    # 产品/功能
    "chatgpt", "copilot", "claude code", "codex", "gemini",
    "claude design", "grok", "perplexity",
    # 技术概念
    "rag", "agent", "llm", "fine-tuning", "open source",
    "reasoning", "multimodal", "agi", "alignment", "safety",
    "transformer", "diffusion", "embedding", "vector database",
    # 事件类型
    "launch", "release", "announce", "update", "deprecat",
    "funding", "acquisit", "partnership", "lawsuit", "regulation",
    "ban", "restrict", "open source",
]


def extract_keywords(text: str) -> list[str]:
    """从文本中提取 AI 关键词。"""
    if not text:
        return []
    lower = text.lower()
    found = []
    for kw in AI_KEYWORDS:
        if kw in lower:
            found.append(kw)
    return found


# ── Event Cluster ─────────────────────────────────────────────────────


class EventCluster:
    """事件聚类器。

    将多个数据源的 item 聚合成 Event。
    """

    def __init__(self, threshold: float = SIMILARITY_THRESHOLD):
        self.threshold = threshold

    def cluster(self, all_data: dict[str, list[dict]]) -> list[Event]:
        """对所有数据源执行聚类。

        Args:
            all_data: {source_name: [items]}

        Returns:
            按综合热度降序排列的 Event 列表
        """
        # 1. 收集所有 items
        all_items: list[tuple[str, dict]] = []  # [(source, item)]
        for source, items in all_data.items():
            for item in items:
                all_items.append((source, item))

        if not all_items:
            return []

        # 2. 构建相似度矩阵并聚类
        clusters: list[list[tuple[str, dict]]] = []
        assigned = [False] * len(all_items)

        for i in range(len(all_items)):
            if assigned[i]:
                continue
            cluster = [all_items[i]]
            assigned[i] = True

            for j in range(i + 1, len(all_items)):
                if assigned[j]:
                    continue
                if self._should_cluster(all_items[i][1], all_items[j][1]):
                    cluster.append(all_items[j])
                    assigned[j] = True

            clusters.append(cluster)

        # 3. 按热度排序
        scored_clusters = []
        for cluster in clusters:
            event = self._build_event(cluster)
            scored_clusters.append(event)

        scored_clusters.sort(
            key=lambda e: (e.source_count, e.max_score, e.total_score),
            reverse=True,
        )

        return scored_clusters

    # ── 聚类判定 ───────────────────────────────────────────────────────

    def _should_cluster(self, a: dict, b: dict) -> bool:
        """判断两个 item 是否应归为同一事件。"""
        # 策略 1: URL 去重
        if self._urls_match(a, b):
            return True

        # 策略 2: 标题相似度
        title_a = normalize_title(a.get("title", ""))
        title_b = normalize_title(b.get("title", ""))
        if not title_a or not title_b:
            return False

        tokens_a = set(title_a.split())
        tokens_b = set(title_b.split())
        sim = jaccard_similarity(tokens_a, tokens_b)

        if sim >= self.threshold:
            return True

        # 策略 3: 关键词聚类（低阈值词重叠 + 共享至少 2 个 AI 关键词）
        kw_a = extract_keywords(title_a)
        kw_b = extract_keywords(title_b)
        shared_kw = set(kw_a) & set(kw_b)

        if len(shared_kw) >= 2 and sim >= 0.15:
            return True

        return False

    @staticmethod
    def _urls_match(a: dict, b: dict) -> bool:
        """检查两个 item 是否引用相同 URL。"""
        url_a = (a.get("url") or "").rstrip("/").replace("www.", "")
        url_b = (b.get("url") or "").rstrip("/").replace("www.", "")
        if url_a and url_b and url_a == url_b:
            return True

        # 检查 raw 中的 external_url
        raw_a = a.get("raw", {}) or {}
        raw_b = b.get("raw", {}) or {}
        ext_a = (raw_a.get("external_url") or "").rstrip("/").replace("www.", "")
        ext_b = (raw_b.get("external_url") or "").rstrip("/").replace("www.", "")
        if ext_a and ext_b and ext_a == ext_b:
            return True

        return False

    # ── Event 构造 ─────────────────────────────────────────────────────

    @staticmethod
    def _build_event(cluster: list[tuple[str, dict]]) -> Event:
        """将一组 items 构造成 Event。"""
        sources = [s for s, _ in cluster]
        items = [item for _, item in cluster]

        # 选择最清晰的 title：优先选不含 "R to @" 且长度适中的
        titles = [
            item.get("title", "") for _, item in cluster
        ]
        clean_titles = [t for t in titles if not t.startswith("R to")]
        best_title = (
            max(clean_titles, key=len) if clean_titles
            else max(titles, key=len) if titles
            else ""
        )

        # 取第一个非空的 description
        description = ""
        for _, item in cluster:
            desc = item.get("description") or ""
            if desc:
                description = desc
                break

        # 热度计算
        scores = [
            item.get("raw_score", 0) or 0
            for _, item in cluster
        ]
        total_score = sum(scores)
        max_score = max(scores) if scores else 0

        # 关键词
        all_kw = []
        for _, item in cluster:
            all_kw.extend(extract_keywords(item.get("title", "")))
        top_keywords = list(dict.fromkeys(all_kw))[:5]

        return Event(
            title=best_title,
            description=description,
            sources=sources,
            items=items,
            total_score=total_score,
            max_score=max_score,
            item_count=len(cluster),
            source_count=len(set(sources)),
            top_keywords=top_keywords,
        )
