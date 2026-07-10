"""AI Daily — Feishu 投递模块

通过飞书 API 发送日报内容到指定频道。

配置：
  .env 或环境变量：
    FEISHU_APP_ID
    FEISHU_APP_SECRET
    FEISHU_HOME_CHANNEL  （可选，默认取 Hermes 配置）
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("ai_daily.delivery")

# 飞书 API 端点
FEISHU_AUTH_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_SEND_URL = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"


def get_tenant_token(app_id: str, app_secret: str) -> str | None:
    """获取飞书 tenant_access_token。"""
    import requests
    try:
        resp = requests.post(
            FEISHU_AUTH_URL,
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10,
        )
        data = resp.json()
        if data.get("code") == 0:
            return data["tenant_access_token"]
        logger.warning("[delivery] Feishu auth failed: %s", data)
    except Exception as e:
        logger.warning("[delivery] Feishu auth error: %s", e)
    return None


def send_message(token: str, channel_id: str, content: str) -> bool:
    """发送消息到飞书频道。

    Args:
        token: tenant_access_token
        channel_id: 飞书 chat_id（oc_xxx）
        content: 消息文本

    Returns:
        是否发送成功
    """
    import requests

    # 飞书消息体需 JSON 转义
    safe_content = json.dumps({"text": content}, ensure_ascii=False)

    try:
        resp = requests.post(
            FEISHU_SEND_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "receive_id": channel_id,
                "msg_type": "text",
                "content": safe_content,
            },
            timeout=30,
        )
        data = resp.json()
        if data.get("code") == 0:
            logger.info(
                "[delivery] Message sent to Feishu (channel=%s)",
                channel_id[:15],
            )
            return True
        logger.warning("[delivery] Feishu send failed: %s", data)
    except Exception as e:
        logger.warning("[delivery] Feishu send error: %s", e)
    return False


def load_report(date_str: str) -> str | None:
    """加载当日日报正文。"""
    project_root = Path(__file__).resolve().parent.parent.parent
    report_path = project_root / "output" / date_str / "daily_report.md"
    if not report_path.exists():
        logger.warning("[delivery] Report not found: %s", report_path)
        return None
    try:
        text = report_path.read_text(encoding="utf-8")
        # 飞书消息有长度限制，截取前 15000 字符
        if len(text) > 15000:
            text = text[:14700] + "\n\n...(剩余内容请查看完整日报)"
        return text
    except Exception as e:
        logger.warning("[delivery] Read report error: %s", e)
        return None


def deliver(date_str: str | None = None) -> bool:
    """将当日日报投递到飞书。

    Args:
        date_str: 日期（YYYY-MM-DD），默认今天

    Returns:
        是否投递成功
    """
    from datetime import datetime, timezone, timedelta

    if date_str is None:
        cst = timezone(timedelta(hours=8))
        date_str = datetime.now(cst).strftime("%Y-%m-%d")

    # 从环境变量读取飞书配置
    app_id = os.environ.get("FEISHU_APP_ID") or ""
    app_secret = os.environ.get("FEISHU_APP_SECRET") or ""
    channel_id = os.environ.get("FEISHU_HOME_CHANNEL") or ""

    if not all([app_id, app_secret, channel_id]):
        logger.warning(
            "[delivery] Feishu not configured "
            "(FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_HOME_CHANNEL)"
        )
        return False

    # 获取 token
    token = get_tenant_token(app_id, app_secret)
    if not token:
        return False

    # 加载日报
    report = load_report(date_str)
    if not report:
        return False

    # 构建发送内容
    header = f"🤖 **AI Daily Report — {date_str}**\n\n"
    content = header + report

    # 发送
    success = send_message(token, channel_id, content)
    if success:
        logger.info("[delivery] ✅ AI Daily delivered to Feishu for %s", date_str)
    return success
