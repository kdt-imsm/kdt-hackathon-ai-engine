# 고도화 기능들

이 폴더에는 향후 서비스 고도화를 위해 보관된 기능들이 포함되어 있습니다.

## 포함된 기능들

### 벡터 유사도 기반 추천 시스템
- `embedding_service.py`: OpenAI 임베딩을 활용한 벡터 유사도 계산
- `db/`: PostgreSQL + pgvector를 활용한 벡터 데이터베이스

### 자연어 처리 시스템
- `nlp/slot_extraction.py`: GPT-4o-mini를 활용한 한국어 자연어 슬롯 추출
- `nlp/itinerary_generator.py`: 복합적 자연어 처리 기반 일정 생성

### 복잡한 추천 로직
- `main_old.py`: 벡터 유사도, 사용자 프로필, 지능형 매칭을 포함한 기존 메인 애플리케이션

### 고급 유틸리티
- `utils/keyword_search.py`: 고급 키워드 검색 및 매칭
- `utils/location.py`: 지리적 거리 계산 및 최적화
- `utils/caching.py`: LRU+TTL 캐시 시스템
- `utils/image_service.py`: 이미지 처리 및 최적화
- `utils/region_mapping.py`: 복합 지역 매핑 시스템

## 향후 활용 계획

1. **A/B 테스트**: 현재 단순 규칙 기반 시스템 vs 고도화된 AI 기반 시스템
2. **성능 비교**: 추천 정확도, 사용자 만족도, 응답 시간 등 비교 분석
3. **점진적 통합**: 검증된 고도화 기능들을 현재 서비스에 단계별 적용

## 사용법

이 기능들을 테스트하려면:
1. 별도 브랜치에서 고도화 기능 통합
2. requirements.txt에 추가 의존성 설치 (`pgvector`, `pandas` 등)
3. PostgreSQL 데이터베이스 설정
4. 벡터 임베딩 생성을 위한 초기 데이터 로딩

## 주의사항

- 이 기능들은 현재 메인 서비스에서 **사용되지 않습니다**
- 배포 시 이 폴더는 제외됩니다
- 테스트 목적으로만 사용하세요