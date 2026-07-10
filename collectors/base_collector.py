"""
AI Daily — BaseCollector
=======================

抽象基类、CollectorResult 定义、State 管理、工具函数。

所有 Collector 必须继承 BaseCollector 并实现 collect() 方法。
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("ai_daily.collector")

# ── 路径常量 ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = PROJECT_ROOT / "state"
STORAGE_DIR = PROJECT_ROOT / "storage"
STATE_FILE = STATE_DIR / "collector_state.json"

CST = timezone(timedelta(hours=8))

# ── Schema ─────────────────────────────────────────────────────────────

SCHEMA_VERSION = "1.0"
"""当前 Data Contract Schema 版本。升级时递增，保持向后兼容。"""


# ── CollectorResult ────────────────────────────────────────────────────


@dataclass
class CollectorResult:
    """每个 Collector 采集完成后返回的结果。

    run_collector.py 根据此结果更新 state 和日志。
    """

    source: str
    """数据源标识，如 'github_trending'"""

    status: str  # "success" | "partial" | "error"
    """采集状态"""

    collected_at: str
    """ISO 8601 格式的采集完成时间"""

    items: list[dict] = field(default_factory=list)
    """统一 JSON 格式的 items（符合 CollectionItem Schema）"""

    state_update: dict = field(default_factory=dict)
    """要写入 state.json 的更新（仅含变化字段）"""

    raw_files: list[str] = field(default_factory=list)
    """写入的 raw 文件绝对路径列表"""

    json_path: str = ""
    """写入的 JSON 文件绝对路径"""

    error: str | None = None
    """错误信息"""

    item_count: int = 0
    """有效条目数"""

    execution_seconds: float = 0.0
    """采集耗时（秒）"""

    def to_dict(self) -> dict:
        return asdict(self)


# ── State 管理 ────────────────────────────────────────────────────────


class CollectorStateManager:
    """管理 collector_state.json 的读取与写入。"""

    def __init__(self, state_file: Path = STATE_FILE):
        self.state_file = state_file

    def load(self) -> dict:
        """加载 state.json，不存在时返回默认值。"""
        if not self.state_file.exists():
            return self._default_state()

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 确保所有已知 source 都有条目
            for source_key in self._known_sources():
                if source_key not in data.get("sources", {}):
                    data["sources"][source_key] = self._default_source_state()
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load state file, using defaults: %s", e)
            return self._default_state()

    def save(self, state: dict) -> None:
        """写入 state.json。"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        tmp.replace(self.state_file)

    def update_source(self, source: str, updates: dict) -> dict:
        """更新单个数据源的 state 并返回更新后的完整 state。"""
        state = self.load()
        if source not in state["sources"]:
            state["sources"][source] = self._default_source_state()
        state["sources"][source].update(updates)
        state["last_global_run"] = _now_iso()
        self.save(state)
        return state

    def should_collect(self, source: str, today: str | None = None) -> bool:
        """判断指定数据源今天是否需要采集。"""
        if today is None:
            today = get_date_str()

        state = self.load()
        src_state = state.get("sources", {}).get(source)
        if src_state is None:
            return True  # 新源，需要采集
        if not src_state.get("enabled", True):
            return False  # 已禁用
        if src_state.get("last_collected_date") == today:
            logger.info("[%s] Already collected today, skipping", source)
            return False
        return True

    def mark_disabled(self, source: str) -> dict:
        """达到失败阈值后自动禁用数据源。"""
        return self.update_source(source, {
            "enabled": False,
            "status": "disabled",
            "error": "Auto-disabled after consecutive failures",
        })

    @staticmethod
    def _default_state() -> dict:
        return {
            "last_global_run": None,
            "sources": {},
        }

    @staticmethod
    def _default_source_state() -> dict:
        return {
            "enabled": True,
            "last_collected": None,
            "last_collected_date": None,
            "last_item_id": None,
            "last_item_count": 0,
            "last_content_hash": None,
            "status": "pending",
            "error": None,
            "consecutive_failures": 0,
        }

    @staticmethod
    def _known_sources() -> list[str]:
        return [
            "github_trending",
            "hacker_news",
            "product_hunt",
            "youtube",
            "twitter",
            "china_ai",
        ]


# ── BaseCollector 抽象基类 ────────────────────────────────────────────


class BaseCollector(ABC):
    """所有 Collector 必须继承的抽象基类。

    子类只需实现：
      - source_name (property)
      - collect(state) (method)
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源标识，必须与 Schema 的 source enum 一致。"""
        ...

    @abstractmethod
    def collect(self, state: dict) -> CollectorResult:
        """执行采集逻辑。

        参数:
            state: 该数据源在 collector_state.json 中的配置。

        返回:
            CollectorResult
        """
        ...

    # ── 工具方法（子类可直接使用） ────────────────────────────────────

    @property
    def storage_dir(self) -> Path:
        """返回 storage/{source}/ 目录。"""
        return STORAGE_DIR / self.source_name

    @property
    def json_dir(self) -> Path:
        """返回 storage/{source}/json/ 目录。"""
        return self.storage_dir / "json"

    @property
    def raw_dir(self) -> Path:
        """返回 storage/{source}/raw/ 目录。"""
        return self.storage_dir / "raw"

    def today_json_path(self, date_str: str | None = None) -> Path:
        """返回今天 JSON 文件的完整路径。"""
        if date_str is None:
            date_str = get_date_str()
        return self.json_dir / f"{date_str}.json"

    def today_raw_dir(self, date_str: str | None = None) -> Path:
        """返回今天 raw 文件目录。"""
        if date_str is None:
            date_str = get_date_str()
        return self.raw_dir / date_str

    def ensure_dirs(self, date_str: str | None = None) -> None:
        """确保所需的目录结构存在。"""
        if date_str is None:
            date_str = get_date_str()
        self.json_dir.mkdir(parents=True, exist_ok=True)
        self.today_raw_dir(date_str).mkdir(parents=True, exist_ok=True)

    def write_json(self, items: list[dict], date_str: str | None = None,
                    status: str = "success") -> Path:
        """将 items 写入当天的 JSON 文件，返回路径。

        Args:
            items: 采集到的 items
            date_str: 日期字符串，默认今天
            status: 采集状态，默认 "success"，可选 "partial", "error"
        """
        if date_str is None:
            date_str = get_date_str()
        self.ensure_dirs(date_str)
        path = self.today_json_path(date_str)

        payload = {
            "schema_version": SCHEMA_VERSION,
            "source": self.source_name,
            "collected_at": _now_iso(),
            "status": status,
            "error": None,
            "items": items,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return path

    def write_raw(self, filename: str, content: str, date_str: str | None = None) -> Path:
        """将原始内容写入 raw 目录，返回路径。

        filename 示例: 'MadsLorentzen_ai-job-search_readme.md'
        """
        if date_str is None:
            date_str = get_date_str()
        self.ensure_dirs(date_str)
        path = self.today_raw_dir(date_str) / filename
        path.write_text(content, encoding="utf-8")
        return path

    def build_item(
        self,
        *,
        item_id: str,
        title: str,
        description: str | None = None,
        author: str | None = None,
        published_at: str | None = None,
        url: str,
        raw_score: int | float | None = None,
        language: str = "unknown",
        category: str | None = None,
        tags: list[str] | None = None,
        thumbnail_url: str | None = None,
        raw: dict | None = None,
    ) -> dict:
        """构造一个标准的 CollectionItem 字典。

        所有 Collector 必须使用此方法创建 item，确保符合 Schema。
        """
        collected_at = _now_iso()
        _raw = raw or {}

        # 计算 content_hash（统一调用独立函数）
        content_hash = compute_content_hash(title, url, _raw)

        item: dict = {
            "id": f"{self.source_name}:{item_id}",
            "source": self.source_name,
            "title": title,
            "description": description,
            "author": author,
            "published_at": published_at,
            "collected_at": collected_at,
            "updated_at": None,
            "raw_score": raw_score,
            "url": url,
            "content_hash": content_hash,
            "language": language,
            "category": category,
            "tags": tags or [],
            "thumbnail_url": thumbnail_url,
            "raw": _raw,
        }

        self._validate_item(item)

        return item

    @staticmethod
    def _validate_item(item: dict) -> None:
        """校验 item 是否包含所有必填字段。

        如果缺少必填字段或类型错误，立即抛出 ValueError。
        """
        required_fields = [
            "id", "source", "title", "published_at",
            "collected_at", "raw", "content_hash",
        ]
        for field_name in required_fields:
            if field_name not in item:
                raise ValueError(
                    f"Item missing required field '{field_name}': id={item.get('id', 'N/A')}"
                )
            # content_hash 不能为空
            if field_name == "content_hash" and not item[field_name]:
                raise ValueError(
                    f"Item has empty content_hash: id={item.get('id', 'N/A')}"
                )

    def should_collect(self, state: dict, today: str | None = None) -> bool:
        """判断今天是否应该执行采集。

        子类可重写此方法实现自定义增量策略。
        默认行为：检查 state 中 enabled 和 last_collected_date。
        """
        if today is None:
            today = get_date_str()

        if not state.get("enabled", True):
            logger.info("[%s] Disabled in state, skipping", self.source_name)
            return False

        if state.get("last_collected_date") == today:
            logger.info("[%s] Already collected today (%s), skipping", self.source_name, today)
            return False

        return True

    @staticmethod
    def parallel_map(
        func: Callable,
        items: list,
        max_workers: int = 5,
        desc: str = "",
    ) -> list:
        """并行执行函数，返回按输入顺序排列的结果。

        所有 Collector 应通过此方法执行并行任务，而不是直接管理
        ThreadPoolExecutor。以后如果迁移到 asyncio，只需修改这里。

        Args:
            func: 接收单个 item 参数的可调用对象
            items: 输入列表
            max_workers: 最大并行数，默认 5
            desc: 日志描述前缀

        Returns:
            与 items 对应的结果列表（失败项为 None）
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: list = [None] * len(items)
        total = len(items)

        if total == 0:
            return []

        logger.info("[parallel] %s: %d items, %d workers", desc or "task", total, max_workers)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(func, item): idx
                for idx, item in enumerate(items)
            }
            for future in as_completed(future_map):
                idx = future_map[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.warning("[parallel] %s item[%d] failed: %s", desc, idx, e)
                    results[idx] = None  # 失败返回 None，不中断整体流程

        success_count = sum(1 for r in results if r is not None)
        logger.info("[parallel] %s done: %d/%d success", desc or "task", success_count, total)
        return results


# ── 工具函数 ──────────────────────────────────────────────────────────


def get_date_str(dt: datetime | None = None) -> str:
    """返回 YYYY-MM-DD 格式的日期字符串。"""
    if dt is None:
        dt = datetime.now(CST)
    return dt.strftime("%Y-%m-%d")


def _now_iso() -> str:
    """返回当前时间的 ISO 8601 格式字符串（东八区）。"""
    return datetime.now(CST).isoformat(timespec="seconds")


def compute_content_hash(title: str, url: str, raw_dict: dict) -> str:
    """计算 item 的 content_hash（SHA256）。"""
    raw_json = json.dumps(raw_dict, sort_keys=True, ensure_ascii=False)
    hash_input = f"{title}\n{url}\n{raw_json}"
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()


def ensure_storage_dirs(source: str, date_str: str | None = None) -> tuple[Path, Path]:
    """确保指定数据源的存储目录存在，返回 (json_dir, raw_dir)。"""
    if date_str is None:
        date_str = get_date_str()
    json_dir = STORAGE_DIR / source / "json"
    raw_dir = STORAGE_DIR / source / "raw" / date_str
    json_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    return json_dir, raw_dir


def make_collector_result(
    source: str,
    status: str,
    items: list[dict],
    json_path: str,
    raw_files: list[str],
    error: str | None = None,
    state_update: dict | None = None,
    start_time: float | None = None,
) -> CollectorResult:
    """便捷地构造 CollectorResult。

    Args:
        source: 数据源标识
        status: success/partial/error
        items: 采集到的 items
        json_path: JSON 文件路径
        raw_files: raw 文件路径列表
        error: 错误信息
        state_update: state 更新字典
        start_time: 开始采集的 time.time()，用于计算耗时

    Returns:
        构造好的 CollectorResult
    """
    elapsed = 0.0
    if start_time is not None:
        elapsed = time.time() - start_time

    return CollectorResult(
        source=source,
        status=status,
        collected_at=_now_iso(),
        items=items,
        state_update=state_update or {},
        raw_files=raw_files,
        json_path=str(json_path),
        error=error,
        item_count=len(items),
        execution_seconds=elapsed,
    )


def build_state_update(
    status: str,
    collected_date: str | None = None,
    last_item_id: str | None = None,
    item_count: int = 0,
    content_hash: str | None = None,
    error: str | None = None,
    consecutive_failures: int = 0,
) -> dict:
    """构造 state_update 字典。

    所有 Collector 的 collect() 方法应使用此函数生成 state_update。
    """
    if collected_date is None:
        collected_date = get_date_str()

    update = {
        "last_collected": _now_iso(),
        "last_collected_date": collected_date,
        "status": status,
        "error": error,
        "consecutive_failures": consecutive_failures,
    }

    if last_item_id is not None:
        update["last_item_id"] = last_item_id
    if item_count >= 0:
        update["last_item_count"] = item_count
    if content_hash is not None:
        update["last_content_hash"] = content_hash

    return update
