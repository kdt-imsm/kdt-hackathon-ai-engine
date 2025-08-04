"""
scripts/init_db.py
==================

Database 초기화 및 더미 데이터 로딩 스크립트
------------------------------------------------
KDT 해커톤 프로젝트의 로컬 개발·시연 환경용 PostgreSQL + pgvector 데이터베이스를
완전히 재생성하고, CSV 기반 더미 데이터를 UPSERT(삽입/갱신)하며
OpenAI Embedding API를 통해 임베딩 벡터를 저장합니다.

실행 단계
~~~~~~~~~
0. pgvector `vector` EXTENSION 설치
1. 기존 모든 테이블 **DROP**
2. `Base.metadata.create_all()` 로 테이블 **재생성**
3. `data/dummy_jobs.csv` → `JobPost` 테이블 UPSERT
4. `JobPost` 태그 임베딩 갱신
5. `TourSpot` 관광지 개요 임베딩 갱신
6. `data/dummy_prefer.csv` → 더미 사용자 선호 태그 로드

주요 함수
~~~~~~~~~
- ``upsert_from_df(df, model, db)``
  Pandas DataFrame을 ORM 테이블에 UPSERT합니다.

- ``refresh_embeddings(db, rows, attr_name="tags")``
  `embedding` 필드가 비어 있는 레코드를 임베딩 후 저장합니다.

사용 예시
~~~~~~~~~
```bash
python -m scripts.init_db
```

환경 의존성
~~~~~~~~~~~
- .env : DB URL, OpenAI API KEY 등 환경 변수
- app.embeddings.embedding_service.embed_texts : OpenAI Embedding 호출 래퍼
"""

from pathlib import Path
import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import SessionLocal, Base, engine
from app.db import models
from app.embeddings.embedding_service import embed_texts

# --------------------------------------------------------------------------- #
# 상수: 더미 CSV 파일 경로 (일거리 데이터)
# --------------------------------------------------------------------------- #
CSV_JOBS = Path("data/dummy_jobs.csv")
CSV_TOURS = Path("data/tour_api.csv")


def upsert_from_df(df: pd.DataFrame, model, db: Session):
    """DataFrame을 ORM 테이블에 UPSERT.

    Args:
        df (pd.DataFrame): 삽입/갱신할 데이터프레임 (PK 컬럼 포함).
        model (DeclarativeMeta): SQLAlchemy ORM 모델 클래스.
        db (Session): SQLAlchemy 세션 인스턴스.

    Notes:
        - `sqlalchemy.dialects.postgresql.insert` 사용.
        - Primary Key 충돌 시 `ON CONFLICT DO UPDATE`로 id 외 컬럼을 갱신합니다.
    """
    # DataFrame → list[dict] 로 변환하여 bulk insert 형태로 작성
    records = df.to_dict("records")

    insert_stmt = insert(model).values(records)

    # id(PK)를 제외한 모든 컬럼을 업데이트 대상으로 지정
    update_cols = {
        c: getattr(insert_stmt.excluded, c)
        for c in df.columns if c != "id"
    }

    stmt = insert_stmt.on_conflict_do_update(
        index_elements=[model.__table__.primary_key.columns.keys()[0]],
        set_=update_cols,
    )

    db.execute(stmt)
    db.commit()


def refresh_embeddings(db: Session, rows, attr_name: str = "tags"):
    """pref_vector가 비어 있는 레코드만 임베딩 후 저장합니다.

    Args:
        db (Session): SQLAlchemy 세션.
        rows (list[Any]): ORM 객체 리스트 (JobPost, TourSpot 등).
        attr_name (str): 임베딩 대상 텍스트가 저장된 속성명.
    """
    # 1) pref_vector가 None 인 레코드만 필터링
    needs = [r for r in rows if getattr(r, "pref_vector", None) is None]
    if not needs:
        return  # 모두 임베딩 존재

    # 2) 텍스트 추출 (list → 공백 join, str → 그대로)
    texts = []
    for r in needs:
        val = getattr(r, attr_name)
        texts.append(" ".join(val) if isinstance(val, list) else str(val))

    # 3) OpenAI Embedding API 호출 → 벡터 리스트 반환
    embeds = embed_texts(texts)

    # 4) ORM 객체 pref_vector 필드에 벡터 저장
    for obj, vec in zip(needs, embeds):
        obj.pref_vector = vec
    db.commit()


if __name__ == "__main__":
    # --------------------------- 0) pgvector 확장 --------------------------- #
    print("▶ pgvector extension 설치 중...")
    with engine.begin() as conn:  # 자동 커밋 컨텍스트
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

    # --------------------------- 1) 테이블 DROP ----------------------------- #
    print("▶ 기존 테이블(drop) 중...")
    Base.metadata.drop_all(bind=engine)

    # --------------------------- 2) 테이블 CREATE --------------------------- #
    print("▶ 테이블(create) 재생성 중...")
    Base.metadata.create_all(bind=engine)

    # SQLAlchemy 세션 생성
    db = SessionLocal()

    # ------------------- 3) dummy_jobs.csv UPSERT --------------------------- #
    print("▶ dummy_jobs.csv 로 일거리 UPSERT 중...")
    jobs_df = pd.read_csv(CSV_JOBS)
    # CSV의 job_id 컬럼을 데이터베이스 모델의 id 컬럼에 매핑
    if 'job_id' in jobs_df.columns:
        jobs_df = jobs_df.rename(columns={'job_id': 'id'})
    upsert_from_df(jobs_df, models.JobPost, db)

    # ------------------- 3-2) tour_api.csv UPSERT --------------------------- #
    print("▶ tour_api.csv 로 관광지 UPSERT 중...")
    tours_df = pd.read_csv(CSV_TOURS)
    # tour_api.csv는 id 컬럼이 없으므로 인덱스를 id로 사용
    tours_df = tours_df.reset_index()
    tours_df = tours_df.rename(columns={'index': 'id'})
    # id는 1부터 시작하도록 조정
    tours_df['id'] = tours_df['id'] + 1
    upsert_from_df(tours_df, models.TourSpot, db)

    # --------------------- 4) JobPost 임베딩 갱신 --------------------------- #
    print("▶ 일거리 embedding 갱신 중...")
    job_rows = db.query(models.JobPost).all()
    refresh_embeddings(db, job_rows, attr_name="tags")

    # --------------------- 5) TourSpot 임베딩 갱신 -------------------------- #
    print("▶ 관광지 embedding 갱신 중...")
    tour_rows = db.query(models.TourSpot).all()
    refresh_embeddings(db, tour_rows, attr_name="name")

    # ----------------- 6) 더미 사용자 선호 태그 로딩 ------------------------ #
    print("▶ 더미 사용자 선호 태그 로딩 중...")
    # 순환 import 방지를 위한 지연 import
    from app.db.crud import load_dummy_preferences
    load_dummy_preferences(db, "data/dummy_prefer.csv")
    print("✅ 더미 선호 태그 로딩 완료")

    # 세션 종료
    db.close()
    print("✅ DB 초기화 완료!")
