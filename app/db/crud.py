"""
app/db/crud.py
==============
데이터베이스 **CRUD 및 벡터/태그 갱신 헬퍼** 모듈

이 모듈은 서비스 로직에서 자주 사용되는 단순 쿼리 작업을 함수화하여
컨트롤러(즉, FastAPI 엔드포인트) 코드의 가독성과 재사용성을 높여 줍니다.

주요 기능
---------
User
^^^^
* ``get_or_create_user`` : 이메일 기준 사용자 조회 또는 신규 생성
* ``update_user_vector`` : 사용자 선호 벡터(pgvector) 업데이트
* ``load_dummy_preferences`` : CSV 파일로부터 terrain/activity 태그 벌크 로드
* ``get_user_preferences`` : 추천 로직에서 사용자 태그 조회

JobPost / TourSpot
^^^^^^^^^^^^^^^^^^
* ``get_jobs_by_ids``  : 주어진 ID 리스트에 해당하는 일거리 레코드 조회
* ``get_tours_by_ids`` : 주어진 ID 리스트에 해당하는 관광지 레코드 조회

특이 사항
~~~~~~~~~
• ORM 쿼리는 SQLAlchemy 1.4/2.x 호환 스타일을 혼용하고 있습니다.
• 대규모 데이터 마이그레이션이 필요한 경우 *load_dummy_preferences* 를 참고해
  별도 ETL 스크립트를 작성할 수 있습니다.
"""

import ast
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select, insert, update
from typing import Sequence
from app.db import models


# ─────────────────────────────────────────────────────────────
# User 관련 CRUD ---------------------------------------------------------
# ─────────────────────────────────────────────────────────────

def get_or_create_user(db: Session, email: str, vector: Sequence[float] | None = None) -> models.User:
    """email 기준으로 User 조회, 없으면 생성 후 반환.

    Parameters
    ----------
    db : Session
        SQLAlchemy 세션.
    email : str
        로그인 이메일(유니크 키).
    vector : Sequence[float] | None
        1536차원 사용자 선호 벡터. 최초 가입 시에만 사용.

    Returns
    -------
    models.User
        조회 또는 새로 생성된 User 인스턴스.
    """
    user = db.scalar(select(models.User).where(models.User.email == email))
    if user:
        return user
    stmt = (
        insert(models.User)
        .values(email=email, pref_vector=vector)
        .returning(models.User)
    )
    user = db.execute(stmt).scalar_one()
    db.commit()
    return user


def update_user_vector(db: Session, user_id: int, vector: Sequence[float]) -> None:
    """User.pref_vector 컬럼을 새로운 임베딩으로 갱신."""
    db.execute(
        update(models.User)
        .where(models.User.id == user_id)
        .values(pref_vector=vector)
    )
    db.commit()


def load_dummy_preferences(db: Session, csv_path: str):
    """CSV → terrain_tags / activity_style_tags 벌크 업데이트.

    CSV 형식 예시::

        user_id,terrain_tags,activity_style_tags
        1,"['평야','바다']","['힐링','체험']"

    Parameters
    ----------
    db : Session
    csv_path : str
        ``data/dummy_prefer.csv`` 경로.
    """
    df = pd.read_csv(csv_path)
    for row in df.itertuples():
        user = db.get(models.User, row.user_id)
        if not user:
            continue  # 존재하지 않는 사용자 → skip
        prefs = {
            "terrain_tags": ast.literal_eval(row.terrain_tags),
            "activity_style_tags": ast.literal_eval(row.activity_style_tags),
        }
        db.execute(
            update(models.User).where(models.User.id == row.user_id).values(**prefs)
        )
    db.commit()


def get_user_preferences(db: Session, user_id: int) -> models.User | None:
    """사용자 선호 태그 및 벡터 조회 (추천 파이프라인용)."""
    return db.scalar(select(models.User).where(models.User.id == user_id))


# ─────────────────────────────────────────────────────────────
# JobPost / TourSpot 조회 ----------------------------------------------
# ─────────────────────────────────────────────────────────────

def get_jobs_by_ids(db: Session, ids: list[int]) -> list[models.JobPost]:
    """ID 리스트에 해당하는 JobPost 레코드 목록 반환."""
    return (
        db.query(models.JobPost)
        .filter(models.JobPost.id.in_(ids))
        .all()
    )


def get_tours_by_ids(db: Session, ids: list[int]) -> list[models.TourSpot]:
    """ID 리스트에 해당하는 TourSpot 레코드 목록 반환."""
    return (
        db.query(models.TourSpot)
        .filter(models.TourSpot.id.in_(ids))
        .all()
    )
