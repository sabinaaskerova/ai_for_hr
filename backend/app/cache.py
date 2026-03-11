"""LLM response cache — in-memory по хешу (model + messages + temperature)."""
import hashlib
import json
import logging
from typing import Any, Optional

log = logging.getLogger(__name__)


class LLMCache:
    def __init__(self):
        self._cache: dict[str, Any] = {}
        self._hits = 0
        self._misses = 0

    def _make_key(self, messages: list[dict], temperature: float, model: str = "") -> str:
        payload = json.dumps(
            {"model": model, "messages": messages, "temperature": temperature},
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
        return hashlib.md5(payload).hexdigest()

    def get(self, messages: list[dict], temperature: float, model: str = "") -> Optional[Any]:
        key = self._make_key(messages, temperature, model)
        result = self._cache.get(key)
        if result is not None:
            self._hits += 1
            log.debug(f"Cache HIT (hits={self._hits})")
        else:
            self._misses += 1
        return result

    def set(self, messages: list[dict], temperature: float, response: Any, model: str = "") -> None:
        key = self._make_key(messages, temperature, model)
        self._cache[key] = response

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "size": len(self._cache),
        }

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0


# Singleton
_cache = LLMCache()


def get_cache() -> LLMCache:
    return _cache
