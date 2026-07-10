"""AI Daily — 公共工具函数

统一封装各 Collector/Reporter 复用的工具：
  - HTML 清理
  - RSS 日期解析
  - Raw 文件预览加载
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any


def clean_html(html_text: str, max_chars: int = 0) -> str:
    """清理 HTML 标签，返回纯文本。

    Args:
        html_text: 原始 HTML
        max_chars: 截取最大字符数（0 表示不截取）

    Returns:
        清理后的纯文本
    """
    if not html_text:
        return ""
    text = html_text
    # 移除 HTML 标签
    text = re.sub(r"<[^>]+>", " ", text)
    # 合并空白
    text = re.sub(r"\s+", " ", text).strip()
    # 解码 HTML 实体
    import html as html_mod
    text = html_mod.unescape(text)
    if max_chars and len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text


def parse_rss_date(date_str: str | None) -> str | None:
    """解析 RSS pubDate 为 ISO 格式。

    支持格式:
      - RFC 2822 (Thu, 09 Jul 2026 20:04:01 GMT)
      - ISO 8601 (2026-07-09T20:04:01+00:00)
    """
    if not date_str:
        return None
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.isoformat()
    except (ValueError, TypeError):
        pass
    try:
        from dateutil.parser import parse as dt_parse
        return dt_parse(date_str).isoformat()
    except Exception:
        return date_str[:10]


def load_raw_preview(
    raw_path: str | None, max_chars: int = 500
) -> str:
    """加载 raw 文件并返回纯文本预览。

    Args:
        raw_path: raw 文件路径
        max_chars: 最大字符数

    Returns:
        预览文本，文件不存在返回空字符串
    """
    if not raw_path:
        return ""
    path = Path(raw_path)
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
        return clean_html(text, max_chars)
    except (OSError, UnicodeDecodeError):
        return ""


def safe_filename(name: str) -> str:
    """生成安全的文件名。

    替换文件系统不允许的字符。
    """
    safe = name.replace(":", "_").replace("/", "_").replace("?", "_")
    safe = re.sub(r'[^\w\-_.]', "_", safe)
    return safe


def compute_md5(*parts: str) -> str:
    """计算 MD5 hash（用于去重）。"""
    raw = "|".join(parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()
