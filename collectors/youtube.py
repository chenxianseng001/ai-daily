"""AI Daily — YouTube Collector（优化版 v2）

采集指定频道的 YouTube 视频和字幕。

优化要点：
  1. 并行获取视频详情（parallel_map）
  2. 并行获取字幕（parallel_map + 超时控制）
  3. 通道级增量采集（state 记录 last_video_id）
  4. 缓存已存在的 raw 文件，避免重复下载
  5. 字幕获取失败快速跳过，不阻塞整体流程
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from concurrent.futures import TimeoutError

import yaml

from collectors.base_collector import (
    BaseCollector,
    CollectorResult,
    build_state_update,
    get_date_str,
    make_collector_result,
)

logger = logging.getLogger("ai_daily.youtube")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 字幕获取超时（秒）
TRANSCRIPT_TIMEOUT = 15
# yt-dlp 详情获取超时
DETAIL_TIMEOUT = 20


def load_channels() -> list[dict]:
    """从 config/channels.yaml 加载频道白名单。"""
    path = PROJECT_ROOT / "config" / "channels.yaml"
    if not path.exists():
        logger.warning("[youtube] channels.yaml not found")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [ch for ch in data.get("channels", []) if ch.get("enabled", True)]


class YouTubeCollector(BaseCollector):
    """YouTube 视频采集器（优化版 v2）。"""

    @property
    def source_name(self) -> str:
        return "youtube"

    def __init__(self):
        self._transcript_api = None

    @property
    def transcript_api(self):
        if self._transcript_api is None:
            from youtube_transcript_api import YouTubeTranscriptApi
            self._transcript_api = YouTubeTranscriptApi
        return self._transcript_api

    # ── 主流程 ─────────────────────────────────────────────────────────

    def collect(self, state: dict) -> CollectorResult:
        start_time = time.time()
        date_str = get_date_str()
        all_raw_files: list[str] = []
        all_items: list[dict] = []

        channels = load_channels()
        if not channels:
            return self._empty_result(start_time, date_str)

        logger.info("[youtube] %d channels configured", len(channels))

        # 1. 收集所有频道的最新视频 ID（并行化第一步：逐个频道的 yt-dlp 调用）
        all_video_tasks: list[dict] = []  # [{vid, channel_name, channel_handle}]

        # 从 state 获取每个频道上次采集的 last_video_id
        src_state = state or {}
        channel_states = src_state.get("channels", {})

        for ch in channels:
            handle = ch["handle"]
            cname = ch["channel_name"]
            max_vids = ch.get("max_videos", 5)
            ch_state = channel_states.get(handle, {})
            last_vid = ch_state.get("last_video_id")

            try:
                video_ids = self._fetch_channel_videos(handle, max_vids)
                if not video_ids:
                    logger.info("[youtube] %s: no videos", cname)
                    continue

                # 增量采集：跳过已处理过的视频
                if last_vid and last_vid in video_ids:
                    idx = video_ids.index(last_vid)
                    new_videos = video_ids[:idx]
                    logger.info(
                        "[youtube] %s: %d total, %d new (last=%s)",
                        cname, len(video_ids), len(new_videos), last_vid,
                    )
                    video_ids = new_videos
                else:
                    logger.info(
                        "[youtube] %s: %d videos (all new)", cname, len(video_ids)
                    )

                for vid in video_ids:
                    all_video_tasks.append({
                        "vid": vid,
                        "channel_name": cname,
                        "channel_handle": handle,
                    })

                # 更新该频道的 last_video_id（取第一个，最新的）
                if video_ids:
                    src_state.setdefault("channels", {})[handle] = {
                        "last_video_id": video_ids[0],
                    }

            except Exception as e:
                logger.warning("[youtube] %s skipped: %s", cname, e)
                continue

        if not all_video_tasks:
            logger.info("[youtube] No new videos")
            return self._empty_result(start_time, date_str)

        logger.info("[youtube] %d new videos to process", len(all_video_tasks))

        # 2. 并行获取视频详情
        logger.info("[youtube] Fetching video details...")
        detail_results: list[dict | None] = BaseCollector.parallel_map(
            func=lambda t: self._fetch_video_detail(t["vid"]),
            items=all_video_tasks,
            max_workers=10,
            desc="yt:details",
        )

        # 3. 并行获取字幕
        logger.info("[youtube] Fetching transcripts...")
        transcript_results: list[str | None] = BaseCollector.parallel_map(
            func=lambda t: self._fetch_transcript(t["vid"]),
            items=all_video_tasks,
            max_workers=5,
            desc="yt:transcripts",
        )

        # 4. 构建 items（顺序处理，无网络请求，速度极快）
        for i, task in enumerate(all_video_tasks):
            info = detail_results[i] if i < len(detail_results) else None
            transcript_text = transcript_results[i] if i < len(transcript_results) else None

            if not info:
                continue

            item, raw_files = self._build_item(
                info=info,
                vid=task["vid"],
                channel_name=task["channel_name"],
                channel_handle=task["channel_handle"],
                transcript_text=transcript_text,
                date_str=date_str,
            )
            if item:
                all_items.append(item)
                all_raw_files.extend(raw_files)

        # 5. 写入 JSON
        json_path = self.write_json(all_items, date_str)
        last_id = all_items[-1].get("id", "") if all_items else ""

        logger.info(
            "[youtube] Done: %d videos in %.1fs",
            len(all_items), time.time() - start_time,
        )

        return make_collector_result(
            source=self.source_name,
            status="success",
            items=all_items,
            json_path=str(json_path),
            raw_files=all_raw_files,
            state_update={
                "status": "success",
                "last_item_id": last_id,
                "last_item_count": len(all_items),
                "channels": src_state.get("channels", {}),
            },
            start_time=start_time,
        )

    def _empty_result(self, start_time: float, date_str: str) -> CollectorResult:
        return make_collector_result(
            source=self.source_name,
            status="success",
            items=[],
            json_path=str(self.today_json_path(date_str)),
            raw_files=[],
            state_update=build_state_update(
                status="success", last_item_id="", item_count=0,
            ),
            start_time=start_time,
        )

    # ── yt-dlp 操作 ────────────────────────────────────────────────────

    def _fetch_channel_videos(self, handle: str, max_videos: int) -> list[str]:
        """通过 yt-dlp 获取频道的最新视频 ID 列表。"""
        url = f"https://www.youtube.com/{handle}/videos"
        cmd = [
            "yt-dlp", "--flat-playlist", "--dump-json",
            "--playlist-end", str(max_videos),
            "--no-warnings",
            url,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.debug("[youtube] yt-dlp %s: %s", handle, result.stderr[:200])
                return []
            ids = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    try:
                        data = json.loads(line)
                        vid = data.get("id")
                        if vid:
                            ids.append(vid)
                    except json.JSONDecodeError:
                        continue
            return ids
        except subprocess.TimeoutExpired:
            logger.warning("[youtube] yt-dlp %s timeout", handle)
            return []

    def _fetch_video_detail(self, video_id: str) -> dict | None:
        """通过 yt-dlp 获取单个视频的完整详情（含超时）。"""
        url = f"https://www.youtube.com/watch?v={video_id}"
        cmd = [
            "yt-dlp", "--dump-json", "--skip-download",
            "--no-warnings", url,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=DETAIL_TIMEOUT,
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except subprocess.TimeoutExpired:
            logger.debug("[youtube] detail %s timeout", video_id)
        except json.JSONDecodeError:
            pass
        return None

    # ── 字幕获取（含超时） ─────────────────────────────────────────────

    def _fetch_transcript(self, video_id: str) -> str | None:
        """通过 yt-dlp 获取视频字幕。

        写入临时文件后读取文本。
        支持官方字幕和自动字幕。
        """
        import tempfile, os, subprocess

        tmpdir = tempfile.mkdtemp(prefix="yt_trans_")
        try:
            output_tmpl = os.path.join(tmpdir, "%(id)s.%(ext)s")
            cmd = [
                "yt-dlp", "--skip-download",
                "--write-auto-subs",   # 自动字幕（包含官方字幕）
                "--sub-langs", "en,zh-Hans,zh",
                "--sub-format", "ttml",
                "--no-warnings",
                "--output", output_tmpl,
                f"https://www.youtube.com/watch?v={video_id}",
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )

            # 查找生成的字幕文件
            output_tmpl = os.path.join(tmpdir, f"{video_id}.")
            for fname in os.listdir(tmpdir):
                if fname.startswith(video_id) and fname.endswith((".ttml", ".vtt", ".srt")):
                    fpath = os.path.join(tmpdir, fname)
                    content = Path(fpath).read_text(encoding="utf-8")
                    # 从字幕 XML/文本格式提取纯文本
                    return self._extract_subtitle_text(content)

            # 如果没有字幕文件但 yt-dlp 成功，可能是没有字幕
            if result.returncode != 0:
                logger.debug("[youtube] transcript %s: %s", video_id, result.stderr[:200])

            return None
        except subprocess.TimeoutExpired:
            logger.debug("[youtube] transcript %s timeout", video_id)
            return None
        except Exception as e:
            logger.debug("[youtube] transcript %s error: %s", video_id, e)
            return None
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    @staticmethod
    def _extract_subtitle_text(content: str) -> str:
        """从字幕文件（TTML/VTT/SRT）提取纯文本。"""
        import re
        # 移除 XML/HTML 标签
        text = re.sub(r"<[^>]+>", " ", content)
        # 移除时间轴信息 (00:00:00.000 --> 00:00:01.000)
        text = re.sub(r"\d{1,2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[.,]\d{3}", "", text)
        # 移除序号行
        text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
        # 移除 XML 声明和 metadata
        text = re.sub(r"<\?xml[^>]*\?>", "", text)
        text = re.sub(r"<[^>]*/>", "", text)
        text = re.sub(r"&lt;|&gt;|&amp;|&quot;|&#39;", " ", text)
        # 合并空白
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # ── Item 构造（缓存的 raw 文件检查） ──────────────────────────────

    def _build_item(
        self,
        info: dict,
        vid: str,
        channel_name: str,
        channel_handle: str,
        transcript_text: str | None,
        date_str: str,
    ) -> tuple[dict | None, list[str]]:
        """构造 item，利用缓存避免重复下载。"""
        raw_files: list[str] = []

        title = info.get("title", "") or ""
        description = info.get("description", "") or ""
        upload_date = info.get("upload_date")
        duration = info.get("duration", 0)
        thumbnail = info.get("thumbnail", "")
        channel = info.get("channel", channel_name)

        published_at = None
        if upload_date and len(upload_date) == 8:
            try:
                dt = datetime.strptime(upload_date, "%Y%m%d").replace(
                    tzinfo=timezone.utc
                )
                published_at = dt.isoformat()
            except ValueError:
                pass

        # 检查 description 是否已缓存
        desc_filename = f"{vid}_description.md"
        desc_path = self.today_raw_dir(date_str) / desc_filename
        if desc_path.exists():
            logger.debug("[youtube] %s description cached", vid)
            raw_files.append(str(desc_path))
        elif description:
            desc_path = self.write_raw(desc_filename, description, date_str)
            raw_files.append(str(desc_path))
        else:
            desc_path = None

        # 检查 transcript 是否已缓存
        transcript_path = None
        trans_filename = f"{vid}_transcript.md"
        trans_path = self.today_raw_dir(date_str) / trans_filename
        if trans_path.exists():
            logger.debug("[youtube] %s transcript cached", vid)
            raw_files.append(str(trans_path))
            transcript_path = str(trans_path)
        elif transcript_text:
            trans_path = self.write_raw(trans_filename, transcript_text, date_str)
            raw_files.append(str(trans_path))
            transcript_path = str(trans_path)

        video_url = f"https://www.youtube.com/watch?v={vid}"

        raw_dict: dict[str, Any] = {
            "video_id": vid,
            "channel_id": info.get("channel_id", ""),
            "channel_name": channel,
            "channel_handle": channel_handle,
            "duration_seconds": duration,
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "comment_count": info.get("comment_count"),
            "thumbnail_url": thumbnail,
            "categories": info.get("categories", []),
            "tags": info.get("tags", []),
            "description_path": str(desc_path) if desc_path else None,
            "transcript_path": transcript_path,
        }

        ai_item = self.build_item(
            item_id=vid,
            title=title,
            description=None,
            author=channel,
            published_at=published_at,
            url=video_url,
            raw_score=info.get("view_count", 0),
            language="en",
            category="video",
            tags=info.get("tags", []),
            thumbnail_url=thumbnail,
            raw=raw_dict,
        )

        return ai_item, raw_files
