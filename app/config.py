"""
config.py
~~~~~~~~~
Pydantic 기반 전역 설정 객체.
환경 변수(.env)에 의존해 OpenAI 모델명, DB URI, 캐시 TTL 등을 관리한다.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str
    postgres_uri: str
    embed_model: str = "text-embedding-3-small"
    slot_model: str = "gpt-4o-mini"
    itinerary_model: str = "gpt-4o"
    cache_ttl: int = 900  # seconds
    tour_api_key: str
    tour_base_url: str = "https://apis.data.go.kr/B551011/KorService1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """FastAPI 종속성 주입용 singleton."""
    return Settings()
