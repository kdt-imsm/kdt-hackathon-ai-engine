"""
app/utils/caching.py
====================
프로토타입 단계용 **LRU + TTL** 인‑메모리 캐시 헬퍼 모듈입니다

목적
----
동일한 입력에 대해 GPT·임베딩 API 호출을 반복하지 않도록 결과를
일시적으로 저장합니다. `cachetools.TTLCache` 를 래핑하여 다음 기능을 제공합니다.

* **LRU(Least Recently Used)** : 캐시 최대 용량(`maxsize`)을 초과하면 가장
  오래 사용되지 않은 항목부터 제거합니다.
* **TTL(Time-to-Live)**        : 항목이 저장된 지 `settings.cache_ttl` 초가
  지나면 자동 만료됩니다(기본 900초 = 15분).

⚠️  운영 환경 팁
    멀티 프로세스·컨테이너 환경에서는 현재 구현이 *프로세스 로컬*이므로
    **Redis**·Memcached 등 외부 캐시로 교체하는 것을 권장합니다.
"""

from cachetools import TTLCache  # LRU+TTL 기능이 포함된 경량 캐시 라이브러리
from app.config import get_settings

# ---------------------------------------------------------------------------
# 전역 캐시 인스턴스(singleton)
# ---------------------------------------------------------------------------
settings = get_settings()  # 환경 설정(싱글턴) 로드
_cache = TTLCache(maxsize=1024, ttl=settings.cache_ttl)  # 최대 1,024개 / TTL 15분


def get_cache(key: str):
    """주어진 *key* 에 해당하는 캐시 값을 반환합니다. 없으면 ``None``."""
    return _cache.get(key)


def set_cache(key: str, value):
    """*key* 에 *value* 를 저장합니다. 동일 키가 있으면 덮어씁니다."""
    _cache[key] = value
