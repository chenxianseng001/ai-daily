"""AI Daily — 统一 HTTP 客户端

提供：
  - FetchResult：所有 Fetcher 的统一返回类型
  - RateLimiter：信号量限流，所有 Collector 可复用
  - build_session()：通用 Session，含 Retry + Timeout
  - build_github_session()：GitHub 专用 Session（Token 可选）

所有 Collector ／ Fetcher 必须使用此模块发 HTTP 请求。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── 默认配置 ──────────────────────────────────────────────────────────

DEFAULT_TIMEOUT = (10, 30)  # (connect_timeout, read_timeout)
"""默认超时：连接 10s，读取 30s"""

DEFAULT_MAX_RETRIES = 3
"""默认最大重试次数"""

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# ── FetchResult ───────────────────────────────────────────────────────


@dataclass
class FetchResult:
    """所有 Fetcher 的统一返回类型。

    Collector 根据此结果决定下一步操作。
    """

    ok: bool
    """是否成功"""

    data: Any = None
    """成功时的数据。类型取决于具体 Fetcher。"""

    error: str | None = None
    """失败时的错误描述"""

    status_code: int = 0
    """HTTP 状态码。非 HTTP 请求（如解析失败）为 0。"""

    @property
    def failed(self) -> bool:
        return not self.ok

    @classmethod
    def success(cls, data: Any = None, status_code: int = 200) -> "FetchResult":
        return cls(ok=True, data=data, status_code=status_code)

    @classmethod
    def failure(cls, error: str, status_code: int = 0) -> "FetchResult":
        return cls(ok=False, error=error, status_code=status_code)


# ── RateLimiter ───────────────────────────────────────────────────────


class RateLimiter:
    """信号量限流器，限制并发请求数。

    用法:
        limiter = RateLimiter(max_concurrent=5)
        with limiter:
            resp = session.get(...)

    也支持 asyncio 兼容接口：
        await limiter.acquire()
        limiter.release()
    """

    def __init__(self, max_concurrent: int = 5):
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")
        self._sem = threading.Semaphore(max_concurrent)
        self._max = max_concurrent

    @property
    def max_concurrent(self) -> int:
        return self._max

    @property
    def available(self) -> int:
        """剩余可用许可数。"""
        return self._sem._value  # 仅用于调试

    def __enter__(self):
        self._sem.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._sem.release()

    def acquire(self):
        """asyncio 兼容接口。同步版本直接调 sem.acquire。"""
        self._sem.acquire()

    def release(self):
        self._sem.release()


# ── Session 工厂 ──────────────────────────────────────────────────────


def _retry_strategy(
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Retry:
    """构造 urllib3 Retry 策略。

    - 404 等客户端错误：不重试
    - 429（限流）：等待后重试
    - 5xx：指数退避重试
    """
    return Retry(
        total=max_retries,
        connect=max_retries,
        read=max_retries,
        backoff_factor=1.0,   # 1s → 2s → 4s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )


def build_session(
    timeout: tuple[int, int] = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    rate_limiter: RateLimiter | None = None,
    headers: dict[str, str] | None = None,
) -> requests.Session:
    """构造一个配置好的 requests Session。

    Args:
        timeout: (connect_timeout, read_timeout)
        max_retries: 最大重试次数
        rate_limiter: 可选限流器。传入后 session 自动限流
        headers: 默认请求头

    Returns:
        配置好的 Session
    """
    session = _RateLimitedSession(rate_limiter) if rate_limiter else requests.Session()

    adapter = HTTPAdapter(
        max_retries=_retry_strategy(max_retries),
        pool_connections=20,
        pool_maxsize=20,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    default_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if headers:
        default_headers.update(headers)
    session.headers.update(default_headers)

    # 保存 timeout 到 session 上，供限流 session 使用
    session._default_timeout = timeout  # type: ignore

    return session


def build_github_session(
    token: str | None = None,
    rate_limiter: RateLimiter | None = None,
) -> requests.Session:
    """构造 GitHub 专用 Session。

    Args:
        token: GitHub Token。不传时匿名访问（60 req/h）
        rate_limiter: 可选限流器

    Returns:
        GitHub 专用 Session（base_url = api.github.com）
    """
    headers = {
        "Accept": "application/vnd.github.v3+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    session = build_session(
        rate_limiter=rate_limiter,
        headers=headers,
    )

    return session


# ── 限流 Session 包装 ────────────────────────────────────────────────


class _RateLimitedSession(requests.Session):
    """自动限流的 Session 包装。"""

    def __init__(self, limiter: RateLimiter | None):
        super().__init__()
        self._limiter = limiter

    def request(self, method, url, **kwargs):
        if self._limiter:
            with self._limiter:
                return super().request(method, url, **kwargs)
        return super().request(method, url, **kwargs)


# ── 便捷函数 ──────────────────────────────────────────────────────────


def fetch_url(
    url: str,
    session: requests.Session | None = None,
    timeout: tuple[int, int] | None = None,
    **kwargs,
) -> FetchResult:
    """便捷 GET 请求，返回 FetchResult。

    适合简单场景。复杂场景直接用 session。
    """
    if session is None:
        session = build_session()

    try:
        t = timeout or getattr(session, "_default_timeout", DEFAULT_TIMEOUT)
        resp = session.get(url, timeout=t, **kwargs)
        if resp.status_code == 404:
            return FetchResult.failure("Not found", status_code=404)
        if resp.status_code >= 400:
            return FetchResult.failure(
                f"HTTP {resp.status_code}: {resp.reason}",
                status_code=resp.status_code,
            )
        return FetchResult.success(data=resp, status_code=resp.status_code)
    except requests.Timeout:
        return FetchResult.failure(f"Timeout after {t}s", status_code=0)
    except requests.ConnectionError as e:
        return FetchResult.failure(f"Connection error: {e}", status_code=0)
    except Exception as e:
        return FetchResult.failure(str(e), status_code=0)
