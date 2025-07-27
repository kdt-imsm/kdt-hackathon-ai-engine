"""
embedding_service.py
~~~~~~~~~~~~~~~~~~~~
OpenAI 임베딩 래퍼 + pgvector upsert.
"""

from typing import Sequence, List
import numpy as np
import openai
from sqlalchemy.orm import Session
from app.config import get_settings
from app.db import models

settings = get_settings()
openai_client = openai.Client(api_key=settings.openai_api_key)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    주어진 문장 리스트를 OpenAI 임베딩으로 2-차원 배열 반환.
    """
    resp = openai_client.embeddings.create(
        model=settings.embed_model,
        input=texts,
        encoding_format="float"
    )
    return [e.embedding for e in resp.data]


def average_embeddings(vecs: Sequence[Sequence[float]]) -> List[float]:
    """
    여러 벡터를 평균내어 선호 벡터 업데이트.
    """
    return np.mean(vecs, axis=0).tolist()


def update_user_pref_vector(db: Session, user: models.User, new_vecs: list[list[float]]):
    """기존 벡터와 새 피드백 벡터 평균 → 사용자 선호 업데이트."""
    if user.pref_vector:
        combined = average_embeddings([user.pref_vector] + new_vecs)
    else:
        combined = average_embeddings(new_vecs)
    user.pref_vector = combined
    db.commit()
    return combined
