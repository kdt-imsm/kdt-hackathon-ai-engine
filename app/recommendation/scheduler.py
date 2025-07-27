"""
build_itineraries
─────────────────
슬롯·랭크된 콘텐츠를 받아 이동 거리·예산을 고려한 일정(JSON) 리스트를
반환한다.  아직 로직이 완성되지 않았으므로 간단한 더미 구현을 둔다.
"""

from datetime import date
from typing import List

from app.schemas import Itinerary, ScheduleItem

def build_itineraries(slots, ranked_jobs, ranked_spots, budget) -> List[Itinerary]:
    """
    TODO: 실제 스케줄링 알고리즘으로 교체
    현재는 첫 번째 일자리·관광지를 하루 일정으로 묶어 반환
    """
    if not ranked_jobs or not ranked_spots:
        return []

    job = ranked_jobs[0]
    spot = ranked_spots[0]

    items = [
        ScheduleItem(
            type="job",
            ref_id=job.id,
            name=job.title,
            start_time="09:00",
            end_time="12:00",
            cost=0,
        ),
        ScheduleItem(
            type="tour",
            ref_id=spot.id,
            name=spot.name,
            start_time="14:00",
            end_time="17:00",
            cost= spot.pref_vector and 0 or 0,
        ),
    ]

    return [
        Itinerary(
            date=date.today(),
            items=items,
            total_cost=sum(i.cost for i in items),
        )
    ]