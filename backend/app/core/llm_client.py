"""Anthropic API wrapper с кэшированием и retry."""
import asyncio
import json
import logging
import time
from typing import Any, Optional

import anthropic

from app.cache import get_cache
from app.config import settings

log = logging.getLogger(__name__)

_client: Optional[anthropic.AsyncAnthropic] = None

# Контекст текущего эндпоинта (устанавливается вызывающим кодом)
_current_endpoint: str = "unknown"


def set_endpoint(name: str):
    global _current_endpoint
    _current_endpoint = name


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


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
    cached = cache.get(messages, temperature, settings.llm_model)
    ep = endpoint or _current_endpoint
    input_text = messages[-1]["content"] if messages else ""

    if cached is not None:
        asyncio.ensure_future(_log_request(ep, input_text, cached, settings.llm_model, temperature, None, 0, True))
        return cached

    client = get_client()
    kwargs = dict(
        model=settings.llm_model,
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
            cache.set(messages, temperature, text, settings.llm_model)
            asyncio.ensure_future(_log_request(ep, input_text, text, settings.llm_model, temperature, tokens, duration_ms, False))
            return text
        except anthropic.RateLimitError as e:
            wait = 2 ** attempt * 5
            log.warning(f"Rate limit, ждём {wait}с (попытка {attempt + 1}/{retries + 1})")
            await asyncio.sleep(wait)
            last_error = e
        except anthropic.APITimeoutError as e:
            wait = 2 ** attempt * 3
            log.warning(f"Timeout, ждём {wait}с (попытка {attempt + 1}/{retries + 1})")
            await asyncio.sleep(wait)
            last_error = e
        except Exception as e:
            log.error(f"LLM ошибка: {e}")
            last_error = e
            break

    raise RuntimeError(f"LLM недоступен после {retries + 1} попыток: {last_error}")


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
