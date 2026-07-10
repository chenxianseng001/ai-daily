"""AI Daily — Product Hunt Collector

采集 Product Hunt 当天产品。

支持两种模式：
  1. GraphQL API（配置 PRODUCT_HUNT_TOKEN 时使用，推荐）
  2. 网页降级（无 Token 时自动使用 cloudscraper 解析）

输出符合 AI Daily Data Contract v1.0 的统一 JSON。
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

from collectors.base_collector import (
    BaseCollector,
    CollectorResult,
    build_state_update,
    get_date_str,
    make_collector_result,
)
from core.http_client import FetchResult, build_session, fetch_url

logger = logging.getLogger("ai_daily.product_hunt")

# ── 常量 ──────────────────────────────────────────────────────────────

API_URL = "https://api.producthunt.com/v2/api/graphql"
WEB_URL = "https://www.producthunt.com/"
MAX_ITEMS = 30                     # 最多采集 30 个产品

# 重点关注分类
FOCUS_TOPICS = {"ai", "developer-tools", "productivity"}


class ProductHuntCollector(BaseCollector):
    """Product Hunt 采集器。

    使用示例:
        collector = ProductHuntCollector(token="...")
        result = collector.collect(state)
    """

    @property
    def source_name(self) -> str:
        return "product_hunt"

    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("PRODUCT_HUNT_TOKEN")
        self.session = build_session()

    def collect(self, state: dict) -> CollectorResult:
        start_time = time.time()
        date_str = get_date_str()
        all_raw_files: list[str] = []

        # ── 1. 优先使用 API ───────────────────────────────────────
        if self.token:
            logger.info("[product_hunt] Using GraphQL API")
            items, raw_files, error = self._collect_via_api(date_str)
            all_raw_files.extend(raw_files)
        else:
            logger.info("[product_hunt] No token, using web scrape fallback")
            items, raw_files, error = self._collect_via_web(date_str)
            all_raw_files.extend(raw_files)

        # ── 2. 写入 JSON ──────────────────────────────────────────
        status = "error" if error and not items else "success"
        json_path = self.write_json(items, date_str, status=status)

        last_item = items[-1] if items else {}
        last_id = str(last_item.get("raw", {}).get("ph_id", ""))

        logger.info(
            "[product_hunt] Done: %d items, status=%s",
            len(items), status,
        )

        return make_collector_result(
            source=self.source_name,
            status=status,
            items=items,
            json_path=str(json_path),
            raw_files=all_raw_files,
            state_update=build_state_update(
                status=status,
                last_item_id=last_id,
                item_count=len(items),
            ),
            start_time=start_time,
        )

    # ── API 模式 ───────────────────────────────────────────────────────

    def _collect_via_api(
        self, date_str: str,
    ) -> tuple[list[dict], list[str], str | None]:
        """使用 GraphQL API 采集。"""
        # 获取当天日期的 UTC 起始时间
        today_start = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        query = """
        query {
          posts(
            first: %d,
            order: VOTES,
            postedAfter: "%sT00:00:00Z"
          ) {
            edges {
              node {
                id
                name
                tagline
                description
                votesCount
                createdAt
                url
                website
                topics {
                  edges {
                    node {
                      name
                      slug
                    }
                  }
                }
                makers {
                  edges {
                    node {
                      name
                      username
                    }
                  }
                }
              }
            }
          }
        }
        """ % (MAX_ITEMS, today_start)

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            resp = self.session.post(
                API_URL,
                json={"query": query},
                headers=headers,
                timeout=30,
            )
            if resp.status_code != 200:
                return [], [], f"API HTTP {resp.status_code}: {resp.text[:200]}"

            data = resp.json()
            posts = data.get("data", {}).get("posts", {}).get("edges", [])
            if not posts:
                return [], [], "No posts found from API"

            items, raw_files = self._process_posts(posts, date_str)
            return items, raw_files, None

        except Exception as e:
            return [], [], f"API request failed: {e}"

    # ── 网页降级模式 ───────────────────────────────────────────────────

    def _collect_via_web(
        self, date_str: str,
    ) -> tuple[list[dict], list[str], str | None]:
        """通过网页解析采集（cloudscraper 绕过 Cloudflare）。"""
        try:
            import cloudscraper
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(WEB_URL, timeout=30)

            if resp.status_code != 200:
                return [], [], f"Web fetch HTTP {resp.status_code}"

            # 从 Apollo SSR 数据中提取产品
            posts_data = self._parse_apollo_posts(resp.text)
            if not posts_data:
                return [], [], "No posts found in page data"

            # 转换为统一格式
            items, raw_files = [], []
            for post in posts_data[:MAX_ITEMS]:
                ph_id = post.get("id", "")
                name = post.get("name", "")
                tagline = post.get("tagline", "")
                description = post.get("description", "")
                votes = post.get("votesCount", 0)

                # 提取 topics
                topics_data = post.get("topics", {}).get("edges", [])
                topics = [
                    t.get("node", {}).get("slug", t.get("node", {}).get("name", ""))
                    for t in topics_data
                ]

                # 提取 makers
                makers_data = post.get("makers", {}).get("edges", [])
                makers = [
                    {
                        "name": m.get("node", {}).get("name", ""),
                        "username": m.get("node", {}).get("username", ""),
                    }
                    for m in makers_data
                ]

                website = post.get("website", "")
                ph_url = post.get("url", "")
                created_at = post.get("createdAt")

                # 保存产品描述到 raw
                raw_dict: dict[str, Any] = {
                    "ph_id": ph_id,
                    "name": name,
                    "tagline": tagline,
                    "votes_count": votes,
                    "topics": topics,
                    "website_url": website,
                    "makers": makers,
                    "ph_url": ph_url,
                    "description_path": None,
                }

                if description:
                    desc_filename = f"{ph_id}_description.md"
                    desc_path = self.write_raw(desc_filename, description, date_str)
                    raw_files.append(str(desc_path))
                    raw_dict["description_path"] = str(desc_path)

                ai_item = self.build_item(
                    item_id=str(ph_id),
                    title=name,
                    description=tagline,
                    author=(
                        makers[0]["name"] if makers else None
                    ),
                    published_at=created_at,
                    url=ph_url or website,
                    raw_score=votes,
                    language="en",
                    category="product",
                    tags=topics,
                    thumbnail_url=None,
                    raw=raw_dict,
                )

                items.append(ai_item)

            return items, raw_files, None

        except ImportError:
            return [], [], "cloudscraper not installed"
        except Exception as e:
            return [], [], f"Web scrape failed: {e}"

    # ── Apollo 数据解析 ───────────────────────────────────────────────

    @staticmethod
    def _parse_apollo_posts(html: str) -> list[dict]:
        """从 Product Hunt 页面的 Apollo SSR 数据中提取产品列表。"""
        # 找到 Apollo 数据脚本
        scripts = re.findall(
            r'<script[^>]*>(.*?)</script>', html, re.DOTALL
        )

        apollo_script = None
        for s in scripts:
            if 'ApolloSSRDataTransport' in s:
                apollo_script = s
                break

        if not apollo_script:
            return []

        # 找到所有 Post 类型的 JSON 对象
        posts = []
        seen_ids = set()

        for match in re.finditer(r'\"__typename\":\"Post\"', apollo_script):
            start = max(0, match.start() - 3000)
            end = min(len(apollo_script), match.start() + 3000)
            chunk = apollo_script[start:end]

            # 找到闭合的 JSON 对象
            brace_start = chunk.rfind("{", 0, match.start() - start)
            if brace_start < 0:
                continue

            depth = 0
            for k in range(brace_start, len(chunk)):
                if chunk[k] == "{":
                    depth += 1
                elif chunk[k] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            obj = json.loads(chunk[brace_start : k + 1])
                            obj_id = obj.get("id", "")
                            if (
                                obj_id
                                and obj_id not in seen_ids
                                and "name" in obj
                                and "tagline" in obj
                            ):
                                posts.append(obj)
                                seen_ids.add(obj_id)
                        except (json.JSONDecodeError, KeyError):
                            pass
                        break

        return posts

    # ── 通用处理（API + Web 共用） ─────────────────────────────────────

    def _process_posts(
        self, posts: list[dict], date_str: str,
    ) -> tuple[list[dict], list[str]]:
        """处理从 API GraphQL 返回的 posts。"""
        items: list[dict] = []
        raw_files: list[str] = []

        for edge in posts:
            post = edge.get("node", edge)  # 兼容 API 和 Web 格式
            ph_id = post.get("id", "")
            name = post.get("name", "")
            tagline = post.get("tagline", "")
            description = post.get("description", "")
            votes = post.get("votesCount", 0)

            # topics
            topics_data = post.get("topics", {}).get("edges", [])
            topics = [
                t.get("node", {}).get("slug", t.get("node", {}).get("name", ""))
                for t in topics_data
            ]

            # makers
            makers_data = post.get("makers", {}).get("edges", [])
            makers = [
                {"name": m.get("node", {}).get("name", ""),
                 "username": m.get("node", {}).get("username", "")}
                for m in makers_data
            ]

            website = post.get("website", "")
            ph_url = post.get("url", "")
            created_at = post.get("createdAt")

            raw_dict: dict[str, Any] = {
                "ph_id": ph_id,
                "name": name,
                "tagline": tagline,
                "votes_count": votes,
                "topics": topics,
                "website_url": website,
                "makers": makers,
                "ph_url": ph_url,
                "description_path": None,
            }

            if description:
                desc_filename = f"{ph_id}_description.md"
                desc_path = self.write_raw(desc_filename, description, date_str)
                raw_files.append(str(desc_path))
                raw_dict["description_path"] = str(desc_path)

            ai_item = self.build_item(
                item_id=str(ph_id),
                title=name,
                description=tagline,
                author=makers[0]["name"] if makers else None,
                published_at=created_at,
                url=ph_url or website,
                raw_score=votes,
                language="en",
                category="product",
                tags=topics,
                raw=raw_dict,
            )

            items.append(ai_item)

        return items, raw_files
