"""
caching.py
~~~~~~~~~~
동일 입력에 대해 GPT 호출을 중복하지 않도록 간단한 LRU + TTL 캐시.
(프로토타입 단계 – 운영 환경에서는 Redis 추천)
"""

from cachetools import TTLCache
from app.config import get_settings

settings = get_settings()
_cache = TTLCache(maxsize=1024, ttl=settings.cache_ttl)


def get_cache(key: str):
    return _cache.get(key)


def set_cache(key: str, value):
    _cache[key] = value
