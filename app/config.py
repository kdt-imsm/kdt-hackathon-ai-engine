"""
app/config.py
=============
Pydantic 기반 전역 설정 모듈

• 프로젝트 전역에서 공통으로 참조할 **환경 변수**를 `Settings` 클래스로 정의합니다.
• `.env` 파일(or 시스템 환경 변수)로부터 값을 읽어와 모델·DB·API 키·TTL 등
  런타임 설정을 관리합니다.
• `@lru_cache` 데코레이터를 사용한 `get_settings()` 헬퍼는 FastAPI 의존성
  주입(Dependency Injection) 시 매 요청마다 인스턴스를 새로 만들지 않고,
  프로세스 단위 **싱글턴**으로 재사용됩니다.

Example
~~~~~~~
```python
from fastapi import Depends
from app.config import get_settings

@app.get("/config")
def show_config(settings = Depends(get_settings)):
    return {
        "embed_model": settings.embed_model,
        "postgres_uri": settings.postgres_uri,
    }
```
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수 → 타입 안전한 설정 객체(Pydantic).

    Attributes
    ----------
    openai_api_key : str
        OpenAI API 인증 토큰.
    postgres_uri : str
        SQLAlchemy 연결 문자열. 예: `postgresql+psycopg2://user:pwd@localhost/db`.
    embed_model : str, default "text-embedding-3-small"
        벡터 임베딩에 사용할 OpenAI 모델명.
    slot_model : str, default "gpt-4o-mini"
        Slot Extraction 단계에 사용할 GPT 모델명.
    itinerary_model : str, default "gpt-4o"
        일정 생성에 사용할 GPT 모델명.
    cache_ttl : int, default 900
        임시 캐시(Time‑to‑Live) 지속 시간(초).
    tour_api_key : str
        한국관광공사 TourAPI 개인 인증키.
    tour_base_url : str, default "https://apis.data.go.kr/B551011/KorService1"
        TourAPI 베이스 URL.
    max_results : int, default 10
        벡터 검색 시 반환할 최대 결과 개수.
    """

    openai_api_key: str
    postgres_uri: str
    embed_model: str = "text-embedding-3-small"
    slot_model: str = "gpt-4o-mini"
    itinerary_model: str = "gpt-4o"
    cache_ttl: int = 900  # seconds
    tour_api_key: str
    tour_base_url: str = "https://apis.data.go.kr/B551011/KorService2"
    max_results: int = 10
    
    # 지역 검색 관련 설정
    region_search_max_distance: float = 150.0  # 지역 검색 최대 거리 (km)
    region_tour_max_distance: float = 80.0     # 관광지 검색 최대 거리 (km)
    region_boost_factor: float = 2.0           # 지역 매칭 시 점수 부스트 배율
    region_weight_exact: float = 1.0           # 정확한 지역 매칭 가중치
    region_weight_province: float = 0.8        # 시도 레벨 매칭 가중치
    region_weight_national: float = 0.3        # 전국 검색 결과 가중치
    region_search_multiplier: int = 10         # 지역 검색 시 초기 검색 배율
    region_accuracy_threshold: float = 70.0    # 지역 매칭 정확도 임계값 (%)

    # .env 파일 위치 및 인코딩 설정
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """FastAPI DI용 Settings 싱글턴을 반환합니다."""
    return Settings()
