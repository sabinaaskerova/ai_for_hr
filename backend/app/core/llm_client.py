"""Anthropic API wrapper с кэшированием и retry."""
import asyncio
import json
import logging
from typing import Any, Optional

import anthropic

from app.cache import get_cache
from app.config import settings

log = logging.getLogger(__name__)

_client: Optional[anthropic.AsyncAnthropic] = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def call_llm(
    messages: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 4096,
    system: Optional[str] = None,
    retries: int = 2,
) -> str:
    """Вызов LLM с кэшированием и exponential backoff retry."""
    cache = get_cache()
    cached = cache.get(messages, temperature, settings.llm_model)
    if cached is not None:
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
            response = await client.messages.create(**kwargs)
            text = response.content[0].text
            cache.set(messages, temperature, text, settings.llm_model)
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
