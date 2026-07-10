"""AI Daily — 统一 Logger

所有模块共用此 Logger，保证日志格式一致。
"""

import logging
import sys
from pathlib import Path

LOG_FORMAT = "[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(
    name: str = "ai_daily",
    level: int = logging.INFO,
    log_file: str | Path | None = None,
    console: bool = True,
) -> logging.Logger:
    """配置并返回 Logger。

    Args:
        name: Logger 名称。
        level: 日志级别，默认 INFO。
        log_file: 日志文件路径。不传则只输出到控制台。
        console: 是否输出到控制台。

    Returns:
        配置好的 Logger 实例。
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 清除已有 handlers，避免重复
    logger.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "ai_daily") -> logging.Logger:
    """获取已配置的 Logger，不重复配置。"""
    return logging.getLogger(name)
