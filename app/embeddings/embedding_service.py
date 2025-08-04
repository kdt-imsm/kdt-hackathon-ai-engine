"""
app/embeddings/embedding_service.py
===================================
OpenAI Embedding API 래퍼 + 벡터 후처리 유틸리티 모듈

기능
----
1. **embed_texts(texts) -> List[List[float]]**
   • 문자열 리스트를 OpenAI Embeddings API로 호출하여 1536차원 벡터 리스트 반환.

2. **embed_text(text) -> List[float]**
   • 편의 함수. 단일 문장을 임베딩하여 1차원 벡터 반환.

3. **average_embeddings(vecs) -> List[float]**
   • N개의 벡터를 numpy로 산술 평균하여 하나의 벡터로 축약.

4. **update_user_pref_vector(db, user, new_vecs) -> List[float]**
   • 주어진 사용자(User)의 기존 선호 벡터와 새로운 벡터들의 평균값을 계산해
     `user.pref_vector` 를 갱신하고 DB에 커밋.

주의
~~~~
• OpenAI 호출 비용 절감을 위해 **앱 레벨 캐싱**(`app.utils.caching`)과 함께 사용하세요.
• 초기화 시 ``openai_client`` 는 프로젝트 전체에서 재사용되는 싱글턴입니다.
"""

from typing import Sequence, List
import time
import numpy as np
import openai
from sqlalchemy.orm import Session
from app.config import get_settings
from app.db import models

# ─────────────────────────────────────────────────────────────
# OpenAI 클라이언트 초기화 ------------------------------------
# ─────────────────────────────────────────────────────────────
settings = get_settings()
openai_client = openai.Client(api_key=settings.openai_api_key)  # snake_case official SDK


def embed_texts(texts: List[str]) -> List[List[float]]:
    """여러 문장을 한 번에 임베딩하여 벡터 리스트를 반환."""
    # OpenAI API 제한 대응: 배치 단위로 처리 (최대 1000개씩)
    batch_size = 1000
    all_embeddings = []
    
    total_batches = (len(texts) + batch_size - 1) // batch_size
    print(f"📦 임베딩 배치 처리: {len(texts)}개 텍스트를 {total_batches}개 배치로 분할")
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        
        print(f"🔄 배치 {batch_num}/{total_batches} 처리 중... ({len(batch)}개)")
        
        resp = openai_client.embeddings.create(
            model=settings.embed_model,
            input=batch,
        )
        batch_embeddings = [e.embedding for e in resp.data]
        all_embeddings.extend(batch_embeddings)
        
        # API 호출 간격 조절 (Rate limiting 방지)
        if i + batch_size < len(texts):  # 마지막 배치가 아닌 경우
            time.sleep(0.1)
    
    return all_embeddings


def embed_text(text: str) -> List[float]:
    """단일 문장 편의 래퍼."""
    vecs = embed_texts([text])
    return vecs[0]


def average_embeddings(vecs: Sequence[Sequence[float]]) -> List[float]:
    """N개의 벡터 → 산술 평균 벡터."""
    return np.mean(vecs, axis=0).tolist()


def update_user_pref_vector(
    db: Session,
    user: models.User,
    new_vecs: List[List[float]],
) -> List[float]:
    """User.pref_vector 갱신 후 평균 벡터 반환."""
    if user.pref_vector:
        combined = average_embeddings([user.pref_vector] + new_vecs)
    else:
        combined = average_embeddings(new_vecs)

    user.pref_vector = combined
    db.commit()
    return combined
