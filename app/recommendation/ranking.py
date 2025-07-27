"""
app/recommendation/ranking.py
────────────────────────────
개인화 랭킹 스텁:
슬롯(region·month·keyword) 조건만으로 DB에서 간단히 필터 + 랜덤 정렬.

TODO:
- pgvector 코사인 유사도 기반 벡터 검색
- 거리·기간·예산 Weight 반영 등
"""

import random
from typing import Tuple, List
from sqlalchemy.orm import Session
from app.db import models

TOP_K = 10

def rank_personalized(
    slots: dict,
    user_id: int | None,
    db: Session,
) -> Tuple[List[models.JobPost], List[models.TourSpot]]:
    """
    반환: (jobs_top_k, tours_top_k)
    """
    region = slots.get("region")

    # 1) 기본 쿼리
    q_jobs = db.query(models.JobPost)
    q_tours = db.query(models.TourSpot)

    # 2) region 필터 (있을 때만)
    if region:
        q_jobs = q_jobs.filter(models.JobPost.region.contains(region))
        q_tours = q_tours.filter(models.TourSpot.region.contains(region))

    jobs = q_jobs.all()
    tours = q_tours.all()

    # 3) 랜덤 셔플 후 상위 TOP_K 선택
    random.shuffle(jobs)
    random.shuffle(tours)

    return jobs[:TOP_K], tours[:TOP_K]
