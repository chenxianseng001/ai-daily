"""AI Daily — GitHub Fetcher

封装 GitHub Trending 页面解析、仓库信息补充、README 获取。

三层职责：
  GitHubHTMLClient  → github.com/trending 页面解析
  GitHubAPIClient   → api.github.com 仓库信息 + README
  GitHubFetcher     → 协调两个 Client，对外提供完整接口

所有方法返回 FetchResult（统一的结果包装）。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core.http_client import (
    FetchResult,
    RateLimiter,
    build_session,
    fetch_url,
)

logger = logging.getLogger("ai_daily.github_fetcher")

# ── 数据类 ────────────────────────────────────────────────────────────


@dataclass
class TrendingItem:
    """GitHub Trending 页面解析后的原始数据。"""

    owner: str
    repo: str
    description: str
    total_stars: int
    today_stars: int
    language: str | None
    built_by: list[str]


@dataclass
class RepoInfo:
    """仓库补充信息（来自 API）。"""

    default_branch: str | None
    license_name: str | None
    topics: list[str]
    fork_count: int
    language: str | None


# ── GitHubHTMLClient ──────────────────────────────────────────────────


class GitHubHTMLClient:
    """解析 github.com/trending 页面。"""

    TRENDING_URL = "https://github.com/trending"

    def __init__(self, session):
        self.session = session

    def fetch_trending(self) -> FetchResult:
        """获取 Trending 页面并解析为 TrendingItem 列表。

        返回:
            FetchResult: data 为 list[TrendingItem]
        """
        result = fetch_url(self.TRENDING_URL, session=self.session)
        if result.failed:
            return result

        try:
            items = self._parse_trending_html(result.data.text)
            return FetchResult.success(data=items)
        except Exception as e:
            return FetchResult.failure(f"HTML parse error: {e}")

    @staticmethod
    def _parse_trending_html(html: str) -> list[TrendingItem]:
        """解析 Trending 页面 HTML，返回 TrendingItem 列表。"""
        soup = BeautifulSoup(html, "lxml")
        articles = soup.find_all("article")
        items: list[TrendingItem] = []

        for article in articles:
            try:
                # 仓库名: "owner / repo"
                h2 = article.find("h2")
                if not h2:
                    continue
                h2_link = h2.find("a")
                if not h2_link:
                    continue
                full_name = h2_link.get_text(strip=True).replace(" ", "")
                if "/" not in full_name:
                    continue
                owner, repo = full_name.split("/", 1)

                # 描述
                desc_tag = article.find("p")
                description = desc_tag.get_text(strip=True) if desc_tag else ""

                # Built by 贡献者（footer 区域的头像链接）
                built_by = []
                footer_div = article.find("div", class_="f6")
                if footer_div:
                    for a in footer_div.find_all("a"):
                        if a.find("img"):
                            href = a.get("href", "")
                            if href.startswith("/") and "login" not in href:
                                username = href.lstrip("/")
                                if username and "/" not in username:
                                    built_by.append(username)

                # 语言
                lang_span = article.find("span", itemprop="programmingLanguage")
                language = lang_span.get_text(strip=True) if lang_span else None

                # 总 Star 和 Today Star
                text = article.get_text()
                today_stars = 0
                total_stars = 0

                # 匹配 "X,XXX stars today" 和 "star X,XXX"
                today_match = re.search(
                    r"([\d,]+)\s*stars?\s*today", text, re.IGNORECASE
                )
                if today_match:
                    today_stars = int(today_match.group(1).replace(",", ""))

                star_links = article.find_all(
                    "a", href=lambda h: h and "/stargazers" in h
                )
                if star_links:
                    total_text = star_links[0].get_text(strip=True)
                    total_match = re.search(r"[\d,]+", total_text)
                    if total_match:
                        total_stars = int(total_match.group().replace(",", ""))

                items.append(TrendingItem(
                    owner=owner,
                    repo=repo,
                    description=description,
                    total_stars=total_stars,
                    today_stars=today_stars,
                    language=language,
                    built_by=built_by[:5],  # 最多 5 个
                ))

            except Exception as e:
                logger.warning("Skip malformed trending item: %s", e)
                continue

        return items


# ── GitHubAPIClient ───────────────────────────────────────────────────


class GitHubAPIClient:
    """通过 GitHub REST API 获取仓库信息和 README。

    支持 Token 认证和匿名访问。
    """

    API_BASE = "https://api.github.com"

    def __init__(self, session, token: str | None = None):
        self.session = session
        self.token = token

    def _api_url(self, path: str) -> str:
        return urljoin(self.API_BASE + "/", path.lstrip("/"))

    def fetch_repo_info(self, owner: str, repo: str) -> FetchResult:
        """获取仓库补充信息（default_branch, license, topics 等）。

        返回:
            FetchResult: data 为 RepoInfo，404 返回 success(data=None)
        """
        url = self._api_url(f"repos/{owner}/{repo}")
        result = fetch_url(url, session=self.session)

        if result.failed:
            if result.status_code == 404:
                return FetchResult.success(data=None, status_code=404)
            return result

        try:
            data = result.data.json() if hasattr(result.data, 'json') else result.data
            repo_info = RepoInfo(
                default_branch=data.get("default_branch"),
                license_name=data.get("license", {}).get("spdx_id")
                if data.get("license") else None,
                topics=data.get("topics", []),
                fork_count=data.get("forks_count", 0),
                language=data.get("language"),
            )
            return FetchResult.success(data=repo_info)
        except Exception as e:
            return FetchResult.failure(f"Parse repo info error: {e}")

    def fetch_readme(self, owner: str, repo: str) -> FetchResult:
        """通过 API 获取仓库 README。

        返回:
            FetchResult: data 为 README 原文（markdown 字符串）
        """
        url = self._api_url(f"repos/{owner}/{repo}/readme")
        headers = {"Accept": "application/vnd.github.v3.raw"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        result = fetch_url(url, session=self.session)

        if result.failed:
            if result.status_code == 404:
                return FetchResult.success(data=None, status_code=404)
            return result

        try:
            text = result.data.text if hasattr(result.data, 'text') else str(result.data)
            return FetchResult.success(data=text)
        except Exception as e:
            return FetchResult.failure(f"Parse README error: {e}")


# ── GitHubFetcher ─────────────────────────────────────────────────────


class GitHubFetcher:
    """GitHub 数据获取总协调器。

    对外提供完整采集能力。内部协调 HTMLClient 和 APIClient。
    """

    def __init__(
        self,
        token: str | None = None,
        rate_limiter: RateLimiter | None = None,
    ):
        # 共享 session（自动继承限流器）
        self.session = build_session(rate_limiter=rate_limiter)
        self.html_client = GitHubHTMLClient(self.session)
        self.api_client = GitHubAPIClient(self.session, token=token)
        self._rate_limiter = rate_limiter
        self.token = token

    def fetch_trending(self) -> FetchResult:
        """获取 Trending 列表。"""
        return self.html_client.fetch_trending()

    def fetch_repo_info(self, owner: str, repo: str) -> FetchResult:
        """获取仓库补充信息。"""
        return self.api_client.fetch_repo_info(owner, repo)

    def fetch_readme_by_branch(
        self, owner: str, repo: str, branch: str | None = None
    ) -> FetchResult:
        """按分支名获取 README。

        优先级:
          1. raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md
          2. raw.githubusercontent.com/{owner}/{repo}/main/README.md
          3. raw.githubusercontent.com/{owner}/{repo}/master/README.md
          4. GitHub API（降级）
        """
        branches_to_try = []
        if branch:
            branches_to_try.append(branch)
        # 总是添加常见分支作为后备
        for fallback in ["main", "master"]:
            if fallback not in branches_to_try:
                branches_to_try.append(fallback)

        # 方式 1-3：raw.githubusercontent.com
        candidates = ["README.md", "readme.md", "Readme.md"]
        for try_branch in branches_to_try:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{try_branch}/"
            for candidate in candidates:
                result = fetch_url(raw_url + candidate, session=self.session)
                if result.ok and result.status_code == 200:
                    text = result.data.text if hasattr(result.data, 'text') else str(result.data)
                    return FetchResult.success(data=text)
                elif result.status_code not in (404,):
                    # 非 404 错误，重试其他文件名
                    continue

        # 方式 4：API 降级
        return self.api_client.fetch_readme(owner, repo)
