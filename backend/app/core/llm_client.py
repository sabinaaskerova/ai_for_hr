"""LLM API wrapper: Anthropic (по умолчанию) или Azure OpenAI."""
import asyncio
import json
import logging
import time
from typing import Any, Optional

import anthropic
from openai import AsyncAzureOpenAI

from app.cache import get_cache
from app.config import settings

log = logging.getLogger(__name__)

_anthropic_client: Optional[anthropic.AsyncAnthropic] = None
_azure_client: Optional[AsyncAzureOpenAI] = None

# Контекст текущего эндпоинта (устанавливается вызывающим кодом)
_current_endpoint: str = "unknown"


def set_endpoint(name: str):
    global _current_endpoint
    _current_endpoint = name


def _current_provider() -> str:
    """Определяем, какой провайдер использовать."""
    provider = (settings.llm_provider or "anthropic").strip().lower()
    if provider in {"anthropic", "azure", "azure_openai"}:
        if provider == "azure":
            provider = "azure_openai"
        return provider
    if settings.anthropic_api_key:
        return "anthropic"
    if settings.azure_openai_api_key:
        return "azure_openai"
    return "anthropic"


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY не задан — выберите другой провайдер или задайте ключ.")
        _anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


def get_azure_client() -> AsyncAzureOpenAI:
    global _azure_client
    if _azure_client is None:
        if not settings.azure_openai_api_key or not settings.azure_openai_endpoint:
            raise RuntimeError("Azure OpenAI: задайте AZURE_OPENAI_API_KEY и AZURE_OPENAI_ENDPOINT.")
        _azure_client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version or "2024-02-15-preview",
        )
    return _azure_client


async def _log_request(
    endpoint: str,
    input_text: str,
    output_text: str,
    model: str,
    temperature: float,
    tokens_used: Optional[int],
    duration_ms: int,
    from_cache: bool,
):
    """Асинхронное логирование в БД (fire and forget, ошибки не бросаем)."""
    try:
        from app.database import AsyncSessionLocal
        from app.models import AiRequestLog
        async with AsyncSessionLocal() as session:
            log_entry = AiRequestLog(
                endpoint=endpoint,
                input_text=input_text[:2000] if input_text else None,
                output_text=output_text[:2000] if output_text else None,
                model=model,
                temperature=temperature,
                tokens_used=tokens_used,
                duration_ms=duration_ms,
                from_cache=from_cache,
            )
            session.add(log_entry)
            await session.commit()
    except Exception as e:
        log.debug(f"ai_request_log запись не удалась: {e}")


async def call_llm(
    messages: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 4096,
    system: Optional[str] = None,
    retries: int = 2,
    endpoint: Optional[str] = None,
) -> str:
    """Вызов LLM с кэшированием и exponential backoff retry."""
    cache = get_cache()
    provider = _current_provider()
    model_name = settings.llm_model
    if provider == "azure_openai":
        model_name = settings.azure_openai_deployment or settings.llm_model or "gpt-4o-mini"

    cache_messages = messages
    if provider == "azure_openai" and system:
        cache_messages = [{"role": "system", "content": system}, *messages]

    cached = cache.get(cache_messages, temperature, model_name)
    ep = endpoint or _current_endpoint
    input_text = messages[-1]["content"] if messages else ""

    if cached is not None:
        asyncio.ensure_future(_log_request(ep, input_text, cached, model_name, temperature, None, 0, True))
        return cached

    if provider == "azure_openai":
        return await _call_azure_openai(
            cache_messages,
            temperature,
            max_tokens,
            system,
            retries,
            ep,
            input_text,
            model_name,
        )

    return await _call_anthropic(
        messages,
        temperature,
        max_tokens,
        system,
        retries,
        ep,
        input_text,
        model_name,
    )


async def _call_anthropic(messages, temperature, max_tokens, system, retries, endpoint_name, input_text, model_name):
    client = get_anthropic_client()
    kwargs = dict(
        model=model_name,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=messages,
    )
    if system:
        kwargs["system"] = system

    last_error = None
    for attempt in range(retries + 1):
        try:
            t0 = time.monotonic()
            response = await client.messages.create(**kwargs)
            duration_ms = int((time.monotonic() - t0) * 1000)
            text = response.content[0].text
            tokens = getattr(response.usage, "output_tokens", None)
            cache_key_messages = messages
            cache = get_cache()
            cache.set(cache_key_messages, temperature, text, model_name)
            asyncio.ensure_future(_log_request(endpoint_name, input_text, text, model_name, temperature, tokens, duration_ms, False))
            return text
        except anthropic.RateLimitError as e:
            wait = 2 ** attempt * 5
            log.warning(f"Anthropic rate limit, ждём {wait}с (попытка {attempt + 1}/{retries + 1})")
            await asyncio.sleep(wait)
            last_error = e
        except anthropic.APITimeoutError as e:
            wait = 2 ** attempt * 3
            log.warning(f"Anthropic timeout, ждём {wait}с (попытка {attempt + 1}/{retries + 1})")
            await asyncio.sleep(wait)
            last_error = e
        except Exception as e:
            log.error(f"Anthropic ошибка: {e}")
            last_error = e
            break

    raise RuntimeError(f"Anthropic недоступен после {retries + 1} попыток: {last_error}")


async def _call_azure_openai(messages, temperature, max_tokens, system, retries, endpoint_name, input_text, model_name):
    """Azure OpenAI (Chat Completions API)."""
    client = get_azure_client()
    azure_messages = []
    if system:
        azure_messages.append({"role": "system", "content": system})
    azure_messages.extend(messages)

    last_error = None
    for attempt in range(retries + 1):
        try:
            t0 = time.monotonic()
            response = await client.chat.completions.create(
                model=model_name,
                messages=azure_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            content = response.choices[0].message.content
            if isinstance(content, list):
                parts = []
                for c in content:
                    if isinstance(c, dict):
                        parts.append(c.get("text") or c.get("content") or "")
                    else:
                        parts.append(str(c))
                text = "".join(parts).strip()
            else:
                text = content or ""
            tokens = getattr(response.usage, "completion_tokens", None)
            cache = get_cache()
            cache.set(azure_messages, temperature, text, model_name)
            asyncio.ensure_future(_log_request(endpoint_name, input_text, text, model_name, temperature, tokens, duration_ms, False))
            return text
        except Exception as e:
            wait = 2 ** attempt * 4
            log.warning(f"Azure OpenAI ошибка: {e}. Повтор через {wait}с (попытка {attempt + 1}/{retries + 1})")
            await asyncio.sleep(wait)
            last_error = e

    raise RuntimeError(f"Azure OpenAI недоступен после {retries + 1} попыток: {last_error}")


async def call_llm_json(
    messages: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 4096,
    system: Optional[str] = None,
) -> dict | list:
    """Вызов LLM с ожиданием JSON-ответа."""
    text = await call_llm(messages, temperature, max_tokens, system)
    # Извлекаем JSON из ответа (может быть обёрнут в ```json ... ```)
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # Попытка найти JSON в тексте
        import re
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if match:
            return json.loads(match.group(1))
        raise ValueError(f"Не удалось распарсить JSON: {e}\nОтвет: {text[:500]}")
