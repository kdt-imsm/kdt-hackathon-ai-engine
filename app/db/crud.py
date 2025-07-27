"""
crud.py
~~~~~~~
데이터베이스 CRUD 및 벡터 업데이트 헬퍼.
"""

from sqlalchemy.orm import Session
from sqlalchemy import select, insert, update
from typing import Sequence
from app.db import models


# User ------------------------------------------------------------------


def get_or_create_user(db: Session, email: str, vector: Sequence[float] | None = None) -> models.User:
    user = db.scalar(select(models.User).where(models.User.email == email))
    if user:
        return user
    stmt = insert(models.User).values(email=email, pref_vector=vector).returning(models.User)
    user = db.execute(stmt).scalar_one()
    db.commit()
    return user


def update_user_vector(db: Session, user_id: int, vector: Sequence[float]) -> None:
    db.execute(
        update(models.User)
        .where(models.User.id == user_id)
        .values(pref_vector=vector)
    )
    db.commit()
