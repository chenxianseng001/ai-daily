"""AI Daily — GitHub Trending Collector

采集 GitHub Trending 页面的所有项目。
输出符合 AI Daily Data Contract v1.0 的统一 JSON。
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from collectors.base_collector import (
    BaseCollector,
    CollectorResult,
    build_state_update,
    get_date_str,
    make_collector_result,
)
from collectors.github_fetcher import GitHubFetcher, RepoInfo
from core.http_client import RateLimiter

logger = logging.getLogger("ai_daily.github_trending")


class GithubTrendingCollector(BaseCollector):
    """GitHub Trending 采集器。

    使用示例:
        collector = GithubTrendingCollector(token="ghp_xxx")
        result = collector.collect(state)
    """

    @property
    def source_name(self) -> str:
        return "github_trending"

    def __init__(
        self,
        token: str | None = None,
        max_concurrent: int = 5,
    ):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.fetcher = GitHubFetcher(
            token=self.token,
            rate_limiter=RateLimiter(max_concurrent=max_concurrent),
        )

    def collect(self, state: dict) -> CollectorResult:
        """执行 GitHub Trending 采集。

        Args:
            state: 该数据源的 state 配置

        Returns:
            CollectorResult
        """
        start_time = time.time()
        date_str = get_date_str()
        all_raw_files: list[str] = []

        # ── 1. 获取 Trending 列表 ─────────────────────────────────────
        logger.info("[github_trending] Fetching trending page...")
        trending_result = self.fetcher.fetch_trending()

        if trending_result.failed:
            return make_collector_result(
                source=self.source_name,
                status="error",
                items=[],
                json_path="",
                raw_files=[],
                error=trending_result.error,
                state_update=build_state_update(
                    status="error",
                    error=trending_result.error,
                    consecutive_failures=state.get("consecutive_failures", 0) + 1,
                ),
                start_time=start_time,
            )

        trending_items = trending_result.data
        if not trending_items:
            logger.info("[github_trending] No trending items found")
            return make_collector_result(
                source=self.source_name,
                status="success",
                items=[],
                json_path=str(self.today_json_path(date_str)),
                raw_files=[],
                state_update=build_state_update(
                    status="success",
                    last_item_id="",
                    item_count=0,
                ),
                start_time=start_time,
            )

        logger.info(
            "[github_trending] Found %d trending repos", len(trending_items)
        )

        # ── 2. 并行补充仓库信息 ───────────────────────────────────────
        logger.info("[github_trending] Fetching repo info...")
        repo_infos: list[RepoInfo | None] = self.parallel_map(
            func=lambda item: self._fetch_single_repo_info(item.owner, item.repo),
            items=trending_items,
            max_workers=5,
            desc="github:repo-info",
        )

        # ── 3. 并行下载 README ────────────────────────────────────────
        logger.info("[github_trending] Downloading READMEs...")
        readme_pairs: list[tuple[str | None, list[str]]] = self.parallel_map(
            func=lambda pair: self._fetch_single_readme(
                pair[0], pair[1], pair[2]
            ),
            items=[
                (
                    item.owner,
                    item.repo,
                    repo_infos[i].default_branch if repo_infos[i] else None,
                )
                for i, item in enumerate(trending_items)
            ],
            max_workers=5,
            desc="github:readme",
        )

        # ── 4. 构造 items ─────────────────────────────────────────────
        collected_items: list[dict] = []
        last_item_id = ""

        for i, item in enumerate(trending_items):
            readme_content, raw_files = readme_pairs[i] if i < len(readme_pairs) else (None, [])
            repo_info = repo_infos[i] if i < len(repo_infos) else None

            if readme_content:
                raw_filename = f"{item.owner}_{item.repo}_readme.md"
                readme_path = self.write_raw(
                    raw_filename, readme_content, date_str
                )
                all_raw_files.append(str(readme_path))
            else:
                readme_path = ""

            raw_dict: dict[str, Any] = {
                "full_name": f"{item.owner}/{item.repo}",
                "owner": item.owner,
                "repo": item.repo,
                "total_stars": item.total_stars,
                "today_stars": item.today_stars,
                "fork_count": repo_info.fork_count if repo_info else 0,
                "primary_language": item.language or (
                    repo_info.language if repo_info else None
                ),
                "license": repo_info.license_name if repo_info else None,
                "topics": repo_info.topics if repo_info else [],
                "built_by": item.built_by,
                "default_branch": repo_info.default_branch if repo_info else None,
            }

            if readme_path:
                raw_dict["readme_path"] = str(readme_path)

            ai_item = self.build_item(
                item_id=f"{item.owner}/{item.repo}",
                title=item.repo,
                description=item.description,
                author=item.owner,
                url=f"https://github.com/{item.owner}/{item.repo}",
                raw_score=item.today_stars,
                language="en",  # GitHub 项目默认英文
                category="open-source",
                tags=repo_info.topics if repo_info else [],
                raw=raw_dict,
            )

            collected_items.append(ai_item)
            last_item_id = f"{item.owner}/{item.repo}"

        # ── 5. 写入 JSON ──────────────────────────────────────────────
        json_path = self.write_json(collected_items, date_str)
        logger.info(
            "[github_trending] Written %d items to %s",
            len(collected_items), json_path,
        )

        # ── 6. 返回结果 ───────────────────────────────────────────────
        return make_collector_result(
            source=self.source_name,
            status="success",
            items=collected_items,
            json_path=str(json_path),
            raw_files=all_raw_files,
            state_update=build_state_update(
                status="success",
                last_item_id=last_item_id,
                item_count=len(collected_items),
            ),
            start_time=start_time,
        )

    # ── 内部辅助方法 ──────────────────────────────────────────────────

    def _fetch_single_repo_info(self, owner: str, repo: str) -> RepoInfo | None:
        """获取单个仓库的补充信息，失败返回 None。"""
        result = self.fetcher.fetch_repo_info(owner, repo)
        if result.ok and result.data:
            return result.data
        return None

    def _fetch_single_readme(
        self, owner: str, repo: str, branch: str | None
    ) -> tuple[str | None, list[str]]:
        """获取单个 README，失败返回 (None, [])。"""
        result = self.fetcher.fetch_readme_by_branch(owner, repo, branch)
        if result.ok and result.data:
            return result.data, []
        return None, []
