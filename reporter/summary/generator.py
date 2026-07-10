"""AI Daily — 摘要生成器

统一摘要接口，支持多种 LLM Provider。

架构：
  BaseProvider（抽象基类）
  ├── OpenAIProvider（OpenAI 兼容 API）
  │   ├── DeepSeekProvider（DeepSeek 官方 API）
  │   └── 自定义（任意 OpenAI 兼容 endpoint）
  ├── GeminiProvider（Google Gemini API）
  └── ClaudeProvider（Anthropic Claude API）

所有 OpenAI 兼容的 Provider 共享同一套实现，仅 base_url / model 不同。
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path

from reporter.summary.cache import SummaryCache
from reporter.summary.prompts import get_prompt_builder

logger = logging.getLogger("ai_daily.summary")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ── Provider 注册表 ───────────────────────────────────────────────────

PROVIDER_REGISTRY: dict[str, type["BaseProvider"]] = {}

# ── Provider 元信息（默认 base_url + model） ──────────────────────────

PROVIDER_META: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openai/gpt-4o-mini",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.2",
    },
    "lm_studio": {
        "base_url": "http://localhost:1234/v1",
        "model": "local-model",
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen2.5-7B-Instruct",
    },
}


def register_provider(name: str):
    """装饰器：注册 Provider。"""
    def decorator(cls):
        PROVIDER_REGISTRY[name] = cls
        return cls
    return decorator


# ── Provider 抽象基类 ────────────────────────────────────────────────


class BaseProvider(ABC):
    """LLM Provider 抽象基类。"""

    def __init__(self, api_key: str, model: str = "", endpoint: str = ""):
        self.api_key = api_key or ""
        self.model = model
        self.endpoint = endpoint

    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM 生成文本。"""
        ...


# ── OpenAI / OpenAI-Compatible 统一实现 ──────────────────────────────


class OpenAICompatibleProvider(BaseProvider):
    """OpenAI 兼容 API 的统一 Provider。

    工作原理：
      - POST {base_url}/chat/completions
      - Authorization: Bearer {api_key}
      - 请求体格式与 OpenAI Chat Completions API 一致

    覆盖范围：
      - OpenAI
      - DeepSeek
      - OpenRouter
      - Ollama（本地）
      - LM Studio（本地）
      - SiliconFlow
      - 任何其他 OpenAI 兼容 endpoint
    """

    def __init__(self, api_key: str, model: str, endpoint: str = ""):
        super().__init__(api_key, model, endpoint)
        self.base_url = endpoint or "https://api.openai.com/v1"

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        import requests
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 300,
                    "temperature": 0.3,
                },
                timeout=60,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            logger.warning("[summary] OpenAI API error: %s", resp.text[:200])
            return ""
        except Exception as e:
            logger.warning("[summary] OpenAI request failed: %s", e)
            return ""


def _make_openai_compatible(name: str) -> type[OpenAICompatibleProvider]:
    """工厂函数：创建命名的 OpenAI 兼容 Provider 类。

    自动从 PROVIDER_META 获取默认 base_url 和 model。
    """
    meta = PROVIDER_META.get(name, {})
    default_base = meta.get("base_url", "https://api.openai.com/v1")
    default_model = meta.get("model", "gpt-4o-mini")

    class _Provider(OpenAICompatibleProvider):
        def __init__(self, api_key: str, model: str = "", endpoint: str = ""):
            super().__init__(
                api_key=api_key,
                model=model or default_model,
                endpoint=endpoint or default_base,
            )

    _Provider.__name__ = f"{name.capitalize()}Provider"
    _Provider.__qualname__ = _Provider.__name__
    return _Provider


# ── 注册所有 OpenAI 兼容 Provider ────────────────────────────────────

for provider_name in PROVIDER_META:
    cls = _make_openai_compatible(provider_name)
    register_provider(provider_name)(cls)


# ── Gemini Provider ───────────────────────────────────────────────────


@register_provider("gemini")
class GeminiProvider(BaseProvider):
    """Google Gemini API。"""

    def __init__(self, api_key: str, model: str = "", endpoint: str = ""):
        super().__init__(api_key, model or "gemini-2.0-flash", endpoint)
        self.base_url = endpoint or "https://generativelanguage.googleapis.com/v1beta"

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        import requests
        try:
            url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
            resp = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                    "generationConfig": {"maxOutputTokens": 300, "temperature": 0.3},
                },
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    return parts[0].get("text", "").strip()
            logger.warning("[summary] Gemini error: %s", resp.text[:200])
            return ""
        except Exception as e:
            logger.warning("[summary] Gemini request failed: %s", e)
            return ""


# ── Claude Provider ───────────────────────────────────────────────────


@register_provider("claude")
class ClaudeProvider(BaseProvider):
    """Anthropic Claude API。"""

    def __init__(self, api_key: str, model: str = "", endpoint: str = ""):
        super().__init__(api_key, model or "claude-sonnet-4", endpoint)
        self.base_url = endpoint or "https://api.anthropic.com/v1"

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        import requests
        try:
            resp = requests.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "max_tokens": 300,
                    "temperature": 0.3,
                },
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", [])
                if content:
                    return content[0].get("text", "").strip()
            logger.warning("[summary] Claude error: %s", resp.text[:200])
            return ""
        except Exception as e:
            logger.warning("[summary] Claude request failed: %s", e)
            return ""


# ── SummaryGenerator ──────────────────────────────────────────────────


class SummaryGenerator:
    """统一摘要生成器。

    职责：
      1. 读取 raw 文件内容
      2. 构造对应数据源的 Prompt
      3. 调用 LLM 生成摘要
      4. 缓存摘要（按 content_hash）
      5. 返回摘要文本
    """

    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.cache = SummaryCache()

        provider_name = cfg.get("provider") or os.environ.get("AI_SUMMARY_PROVIDER", "openai")
        api_key = cfg.get("api_key") or os.environ.get("AI_SUMMARY_API_KEY", "")
        model = cfg.get("model") or os.environ.get("AI_SUMMARY_MODEL", "")
        endpoint = cfg.get("endpoint") or ""

        provider_cls = PROVIDER_REGISTRY.get(provider_name)
        if not provider_cls:
            logger.warning(
                "[summary] Unknown provider '%s', falling back to openai",
                provider_name,
            )
            provider_cls = PROVIDER_REGISTRY.get("openai", OpenAICompatibleProvider)

        self.provider = provider_cls(api_key=api_key, model=model, endpoint=endpoint)
        self._stats = {"generated": 0, "cached": 0, "failed": 0}

    def summarize(self, item: dict, source: str) -> str:
        """为单个 item 生成摘要。

        策略：
          1. 检查缓存（content_hash）
          2. 未命中 → 构造 Prompt → 调用 LLM → 写入缓存
          3. 返回摘要文本
        """
        # 跳过不需要 AI 摘要的数据源
        SUMMARY_SKIP_SOURCES = {"youtube"}
        if source in SUMMARY_SKIP_SOURCES:
            return ""

        content_hash = item.get("content_hash", "")
        if not content_hash:
            return ""

        cached = self.cache.get(content_hash)
        if cached:
            self._stats["cached"] += 1
            return cached

        raw_text = self._load_raw_text(item)
        if not raw_text:
            return ""

        builder = get_prompt_builder(source)
        user_prompt = builder.build_prompt(item, raw_text)
        system_prompt = builder.system_prompt

        if not self.provider.api_key:
            logger.debug("[summary] No API key configured, skipping")
            return ""

        try:
            summary = self.provider.chat(system_prompt, user_prompt)
            if summary:
                self._stats["generated"] += 1
                self.cache.set(content_hash, summary)
                return summary

            # 一次自动重试
            logger.debug("[summary] Retry for %s...", source)
            summary = self.provider.chat(system_prompt, user_prompt)
            if summary:
                self._stats["generated"] += 1
                self.cache.set(content_hash, summary)
                return summary

            self._stats["failed"] += 1
        except Exception as e:
            logger.warning("[summary] Generation failed: %s", e)
            self._stats["failed"] += 1

        return ""

    @staticmethod
    def _load_raw_text(item: dict, max_chars: int = 1500) -> str:
        """从 item 中加载原始内容（限制长度）。"""
        raw = item.get("raw", {}) or {}
        raw_paths = [
            raw.get("readme_path"),
            raw.get("external_content_path"),
            raw.get("description_path"),
            raw.get("text_path"),
            raw.get("transcript_path"),
            raw.get("content_path"),
        ]
        for rp in raw_paths:
            if rp:
                path = Path(rp)
                if path.exists():
                    text = path.read_text(encoding="utf-8")
                    if text.strip():
                        if len(text) > max_chars:
                            text = text[:max_chars]
                        return text
        desc = item.get("description", "") or ""
        if desc:
            return desc[:max_chars]
        return ""

    def stats(self) -> dict:
        """返回摘要生成统计。"""
        s = dict(self._stats)
        total = s["cached"] + s["generated"] + s["failed"]
        s["total"] = total
        s["hit_rate"] = (s["cached"] / total * 100) if total > 0 else 0
        return s
