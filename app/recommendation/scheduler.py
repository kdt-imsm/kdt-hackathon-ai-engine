"""
app/recommendation/scheduler.py
===============================
매우 단순화된 **일정 생성(Scheduling) 프로토타입**

*현재 구현은 한 페이지(1일차) 일정만을 생성*하며, 추천된 일거리(JobPost)와
관광지(TourSpot)를 순차적으로 배치합니다. 향후 GPT 기반 `itinerary_generator`
결과를 보정하거나, 지도 API를 통한 실제 거리·소요 시간 계산 로직으로 대체될 예정입니다.

Input Parameters
----------------
slots : dict
    Slot Extraction 단계에서 추출된 JSON (start_date, end_date 등).
jobs : List[JobPost]
    벡터 검색 / 랭킹 모듈에서 선정된 JobPost 목록.
tours : List[TourSpot]
    벡터 검색 / 랭킹 모듈에서 선정된 TourSpot 목록.
budget : int
    사용자가 입력한 전체 예산(₩). *현재는 경고·제한 로직이 없음*.

Return
------
List[ScheduleItem]
    Pydantic 모델 리스트. 현재는 길이 1 (day=1) 고정
"""

from datetime import datetime
from typing import List

from app.schemas import ScheduleItem
from app.db.models import JobPost, TourSpot


# ─────────────────────────────────────────────────────────────
# 일정 생성 메인 함수 ----------------------------------------
# ─────────────────────────────────────────────────────────────

def build_itineraries(
    slots: dict,
    jobs: List[JobPost],
    tours: List[TourSpot],
    budget: int,
) -> List[ScheduleItem]:
    """슬롯 + 추천 콘텐츠 → ScheduleItem 리스트 생성."""
    # 1) 여행 시작 날짜 파싱 ---------------------------------------------
    start_date = datetime.fromisoformat(slots["start_date"])
    day1_str = start_date.date().isoformat()  # "YYYY-MM-DD"

    # 2) 활동(Activity) 리스트 구성 --------------------------------------
    activities = []
    # 2-1) 오전: 일거리(Job) 블럭 ---------------------------
    for job in jobs:
        activities.append({
            "type": "job",
            "ref_id": job.id,
            "name": job.title,
            "start_time": "09:00",
            "end_time": "12:00",
            "cost": job.wage or 0,  # 임금이 없으면 0원 처리
        })
    # 2-2) 오후: 관광(Tour) 블럭 -----------------------------
    for tour in tours:
        activities.append({
            "type": "tour",
            "ref_id": tour.id,
            "name": tour.name,
            "start_time": "13:00",
            "end_time": "17:00",
            "cost": 0,  # 입장료/이동비 미계산
        })

    # 3) 일정 요약 텍스트 및 비용 계산 ------------------------------
    total_cost = sum(a["cost"] for a in activities)
    plan_items = [
        f"[{a['type'].upper()}] {a['name']} ({a['start_time']}~{a['end_time']}) - {a['cost']}원"
        for a in activities
    ]

    # 4) ScheduleItem 객체 생성 ------------------------------------------
    schedule_item = ScheduleItem(
        day=1,
        date=day1_str,
        plan_items=plan_items,
        total_distance_km=0.0,  # 거리 계산 미구현
        total_cost_krw=total_cost,
    )

    return [schedule_item]
