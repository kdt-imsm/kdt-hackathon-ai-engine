"""
app/recommendation/ranking.py
=============================
단순 **개인화 랭킹 스텁(Prototype)** 모듈

현재 구현
~~~~~~~~~
• 입력 슬롯(slots)에서 *region* 키워드만 사용하여 DB를 필터링한 뒤,
  결과 리스트를 난수 셔플(`random.shuffle`) 후 **상위 TOP_K** 항목을 반환합니다.
• 벡터 유사도, 거리/기간/예산 가중치 등은 아직 반영되지 않았으며, 이는
  TODO 섹션에 정리되어 있습니다.

향후 개선 아이디어
------------------
1. **pgvector 코사인 유사도** : 사용자·콘텐츠 벡터(`pref_vector`) 기반 랭킹
2. **거리/이동 시간**        : haversine 또는 PostGIS ST_DistanceSphere 활용
3. **기간 가중치**            : 슬롯의 여행 길이에 따라 콘텐츠 체류시간 가중
4. **예산 제약**             : `wage`, 입장료 등을 합산하여 초과 시 페널티

함수
-----
``rank_personalized(slots, user_id, db) -> Tuple[List[JobPost], List[TourSpot]]``
    • region 필터 + 무작위 셔플 → TOP_K 반환.
"""

import random
from typing import Tuple, List
from sqlalchemy.orm import Session
from app.db import models

# 반환 개수 상수 -----------------------------------------------------------
TOP_K = 10  # 카드 미리보기 개수


def rank_personalized(
    slots: dict,
    user_id: int | None,
    db: Session,
) -> Tuple[List[models.JobPost], List[models.TourSpot]]:
    """슬롯 조건에 기반한 간단한 개인화 랭킹.

    Parameters
    ----------
    slots : dict
        Slot Extraction 단계에서 추출된 JSON. 현재는 `region` 키만 사용.
    user_id : int | None
        로그인 사용자 ID(미사용, 향후 선호도 반영용).
    db : Session
        SQLAlchemy 세션.

    Returns
    -------
    Tuple[List[JobPost], List[TourSpot]]
        (일거리 카드 TOP_K, 관광지 카드 TOP_K) 튜플.
    """
    region = slots.get("region")

    # 1) 기본 쿼리 ---------------------------------------------------------
    q_jobs = db.query(models.JobPost)
    q_tours = db.query(models.TourSpot)

    # 2) region 필터 (슬롯에 있을 때만 적용) ------------------------------
    if region:
        q_jobs = q_jobs.filter(models.JobPost.region.contains(region))
        q_tours = q_tours.filter(models.TourSpot.region.contains(region))

    jobs = q_jobs.all()
    tours = q_tours.all()

    # 3) 랜덤 셔플 후 상위 TOP_K -----------------------------------------
    random.shuffle(jobs)
    random.shuffle(tours)

    return jobs[:TOP_K], tours[:TOP_K]
