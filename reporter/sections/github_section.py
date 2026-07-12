"""AI Daily — GitHub Trending Section — v3.0

新格式：
  作者 / 项目名称
  ⭐ 总 Star：xxxxx（今日 +xxx）
  📌 项目简介（AI 生成，2~4 行）
  🎯 对我的项目有没有用 （AI 评估，可选）
"""

from __future__ import annotations

import re
from typing import Any

from reporter.base_section import BaseSection


class GitHubSection(BaseSection):
    @property
    def name(self) -> str:
        return "GitHub Trending"

    @property
    def source_name(self) -> str:
        return "github_trending"

    def render(self, items: list[dict], config: dict | None = None) -> str:
        if self.should_skip(items):
            return ""
        cfg = config or {}
        show_all = cfg.get("github_show_all", True)
        max_items = cfg.get("github_max_items", 15) if not show_all else len(items)
        lines = []

        lines.append(f"## 📦 GitHub Trending\n")
        lines.append(f"今日值得关注的开源项目\n")

        for rank, item in enumerate(items[:max_items], 1):
            raw = item.get("raw", {}) or {}
            today_stars = raw.get("today_stars", 0) or 0
            total_stars = raw.get("total_stars", 0) or 0
            ai_text = self.format_ai_summary(item)

            # 作者 / 项目名
            lines.append(f"### {rank}. {self.format_github_title(item)}")
            lines.append("")

            # ⭐ 总 Star：xxxxx（今日 +xxx）
            if total_stars or today_stars:
                parts = []
                if total_stars:
                    parts.append(f"⭐ 总 Star：**{total_stars:,}**")
                if today_stars:
                    parts.append(f"今日 **+{today_stars:,}**")
                lines.append(" · ".join(parts))
                lines.append("")

            # AI 摘要
            if ai_text:
                # 解析 AI 输出，提取项目简介和实用性评估
                intro = self._extract_intro(ai_text)
                usefulness = self._extract_usefulness(ai_text)

                if intro:
                    lines.append(f"📌 {intro}")
                    lines.append("")

                if usefulness:
                    lines.append(f"🎯 对我的项目有没有用")
                    for point in usefulness:
                        lines.append(f"• {point}")
                    lines.append("")

            lines.append("---")

        return "\n".join(lines)

    @staticmethod
    def _extract_intro(text: str) -> str:
        """从 AI 输出中提取项目简介部分。"""
        # 找到所有可能格式的 📌
        idx = text.find("📌")
        if idx < 0:
            return ""
        after = text[idx + 1:].strip()
        # 去掉 "**项目简介**" 等标题
        for prefix in ["**项目简介**", "项目简介", "：", ":" ]:
            if after.startswith(prefix):
                after = after[len(prefix):].strip()
        # 取到 🎯 或末尾
        end = after.find("🎯")
        if end >= 0:
            after = after[:end]
        result = after.strip()
        # 去掉“此部分不输出”结尾
        for phrase in ["此部分不输出", "（此部分不输出", "（不输出"]:
            if phrase in result:
                result = result.split(phrase)[0].strip()
        return result

    @staticmethod
    def _extract_usefulness(text: str) -> list[str]:
        """从 AI 输出中提取「对我的项目有没有用」。"""
        idx = text.find("🎯")
        if idx < 0:
            return []
        after = text[idx + 1:].strip()
        lines_raw = after.split("\n")
        points = []
        for line in lines_raw:
            line = line.strip()
            line = line.lstrip("•-*· ")
            line = line.lstrip("0123456789. ")
            line = line.strip("*")
            line = line.strip()
            # 过滤无用行
            skip_words = ["🎯", "我的项目有没有用", "此部分不输出", "有用。", "有用**", "有用。**"]
            skip_exact = ["有用", "有用。", "**"]
            skip = any(w in line for w in skip_words) or line.strip().rstrip("*").strip() in skip_exact
            if line and len(line) > 10 and not skip:
                points.append(line)
        return points[:4]
