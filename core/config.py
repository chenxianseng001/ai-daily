"""AI Daily — 统一配置加载器

从 config/config.yaml 加载配置，支持环境变量覆盖。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

# ── 默认配置（作为 YAML 文件缺失时的 fallback） ──────────────────────

DEFAULT_CONFIG: dict[str, Any] = {
    "global": {
        "log_level": "INFO",
        "max_concurrent": 5,
        "request_timeout": {"connect": 10, "read": 30},
        "max_retries": 3,
    },
    "github_trending": {
        "enabled": True,
        "token": "",
        "max_concurrent": 5,
        "show_all": True,
        "max_items": 15,
    },
    "hacker_news": {
        "enabled": True,
        "top_count": 30,
        "best_count": 30,
        "new_count": 30,
        "max_total": 60,
        "max_items": 10,
    },
    "product_hunt": {
        "enabled": True,
        "token": "",
        "max_items": 30,
        "show_top": 10,
    },
    "youtube": {
        "enabled": True,
        "max_items": 10,
    },
    "twitter": {
        "enabled": True,
        "bearer_token": "",
        "max_items": 10,
    },
    "china_ai": {
        "enabled": True,
        "max_items": 10,
    },
    "reporter": {
        "output_dir": "output",
    },
}

# ── 环境变量映射 ──────────────────────────────────────────────────────
# (config_path, env_var_name)
# 路径用点分隔，如 "github_trending.token" → GITHUB_TOKEN
ENV_OVERRIDES: list[tuple[str, str]] = [
    ("github_trending.token", "GITHUB_TOKEN"),
    ("product_hunt.token", "PRODUCT_HUNT_TOKEN"),
]


def _set_nested(d: dict, path: str, value: Any) -> None:
    """按点分隔路径设置嵌套字典的值。"""
    keys = path.split(".")
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value


def _get_nested(d: dict, path: str) -> Any:
    """按点分隔路径获取嵌套字典的值。"""
    keys = path.split(".")
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key)
        else:
            return None
    return d


def load_config() -> dict[str, Any]:
    """加载配置。

    优先级（从低到高）：
      1. DEFAULT_CONFIG（硬编码默认值）
      2. config/config.yaml（文件配置）
      3. 环境变量覆盖（如 GITHUB_TOKEN）

    Returns:
        完整的配置字典
    """
    config = DEFAULT_CONFIG.copy()

    # 合并 YAML 文件
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            file_config = yaml.safe_load(f)
        if file_config:
            _deep_merge(config, file_config)

    # 环境变量覆盖
    for config_path, env_name in ENV_OVERRIDES:
        env_val = os.environ.get(env_name)
        if env_val:
            _set_nested(config, config_path, env_val)

    return config


def get_source_config(config: dict, source_name: str) -> dict:
    """获取指定数据源的配置。"""
    return config.get(source_name, {})


def is_source_enabled(config: dict, source_name: str) -> bool:
    """判断数据源是否启用。"""
    src = config.get(source_name, {})
    return src.get("enabled", True)


def _deep_merge(base: dict, override: dict) -> None:
    """深度合并两个字典。override 的值覆盖 base。"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
