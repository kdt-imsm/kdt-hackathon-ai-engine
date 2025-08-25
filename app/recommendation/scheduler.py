"""
app/recommendation/scheduler.py
===============================
**GPT-4o 기반 다중 일정 생성** 시스템

기존의 단순한 1일차 일정 생성에서 확장하여, GPT-4o를 활용한 지능적이고 
상세한 다중 일정 생성을 지원합니다.

주요 기능
--------
1. build_itineraries(): 기존 레거시 JSON 일정 생성 (하위 호환성)
2. build_detailed_itineraries(): GPT-4o 기반 자연어 일정 생성
3. 날짜/시간/거리/예산을 종합적으로 고려한 최적화된 일정 배치

Input Parameters
----------------
slots : dict
    Slot Extraction 단계에서 추출된 JSON (start_date, end_date 등).
jobs : List[JobPost]
    벡터 검색 / 랭킹 모듈에서 선정된 JobPost 목록.
tours : List[TourSpot]
    벡터 검색 / 랭킹 모듈에서 선정된 TourSpot 목록.
budget : int
    사용자가 입력한 전체 예산(₩).
user_query : str
    원본 사용자 자연어 쿼리 (GPT-4o 컨텍스트용)

Return
------
DetailedItineraryResponse
    자연어 일정 + 기존 JSON 일정 + 메타데이터를 포함한 종합 응답
"""

from datetime import datetime
from typing import List, Dict, Any

from app.schemas import ScheduleItem, Itinerary, DetailedItineraryResponse
from app.db.models import JobPost, TourSpot


# ─────────────────────────────────────────────────────────────
# 일정 생성 메인 함수 ----------------------------------------
# ─────────────────────────────────────────────────────────────

def build_itineraries(
    slots: dict,
    jobs: List[JobPost],
    tours: List[TourSpot],
) -> List[ScheduleItem]:
    """슬롯 + 추천 콘텐츠 → ScheduleItem 리스트 생성."""
    # 1) 여행 시작 날짜 파싱 ---------------------------------------------
    start_date_str = slots.get("start_date", "") or "2025-01-01"
    start_date = datetime.fromisoformat(start_date_str)
    day1_str = start_date.date().isoformat()  # "YYYY-MM-DD"

    # 2) 활동(Activity) 리스트 구성 --------------------------------------
    activities = []
    # 2-1) 오전: 일거리(Job) 블럭 ---------------------------
    for job in jobs:
        job_start = getattr(job, 'start_time', None) or "09:00"
        job_end = getattr(job, 'end_time', None) or "12:00"
        activities.append({
            "type": "job",
            "ref_id": job.id,
            "name": job.title,
            "start_time": job_start,
            "end_time": job_end,
            "cost": 0,  # 임금/예산 고려하지 않음
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


# ─────────────────────────────────────────────────────────────
# GPT-4o 기반 상세 일정 생성 메인 함수
# ─────────────────────────────────────────────────────────────

def build_detailed_itineraries(
    slots: dict,
    jobs: List[JobPost],
    tours: List[TourSpot],
    user_query: str = ""
) -> DetailedItineraryResponse:
    """
    GPT-4o를 활용한 상세 자연어 일정 생성
    
    기존 build_itineraries() 함수의 확장 버전으로, 다음을 제공합니다:
    1. 기존 JSON 일정 (하위 호환성 유지)
    2. GPT-4o 생성 자연어 일정 (메인 기능)
    3. 최적화된 다중 일정 배치
    4. 상세 메타데이터
    
    Parameters
    ----------
    slots : dict
        슬롯 추출 결과
    jobs : List[JobPost]
        선택된 일거리 목록
    tours : List[TourSpot]
        선택된 관광지 목록
    user_query : str
        원본 사용자 쿼리
        
    Returns
    -------
    DetailedItineraryResponse
        자연어 일정 + JSON 일정 + 메타데이터 종합 응답
    """
    
    print(f"🗓️ 상세 일정 생성 시작 (GPT-4o 활용)")
    print(f"   💼 일거리: {len(jobs)}개")
    print(f"   관광지: {len(tours)}개")
    
    try:
        # 1단계: 기존 JSON 일정 생성 (하위 호환성)
        legacy_schedule_items = build_itineraries(slots, jobs, tours)
        
        # ScheduleItem을 Itinerary로 변환
        legacy_itineraries = [
            Itinerary(
                day=item.day,
                date=item.date,
                plan_items=item.plan_items,
                total_distance_km=item.total_distance_km,
                total_cost_krw=item.total_cost_krw
            )
            for item in legacy_schedule_items
        ]
        print(f"   ✅ 레거시 JSON 일정 생성 완료")
        
        # 2단계: GPT-4o 기반 상세 일정 생성
        from app.nlp.itinerary_generator import generate_detailed_itinerary
        
        detailed_result = generate_detailed_itinerary(
            slots=slots,
            selected_jobs=jobs,
            selected_tours=tours,
            user_query=user_query
        )
        
        print(f"   ✅ GPT-4o 자연어 일정 생성 완료")
        
        # 3단계: 응답 구조화
        response = DetailedItineraryResponse(
            legacy_itineraries=legacy_itineraries,
            natural_language_itinerary=detailed_result["natural_language_itinerary"],
            total_days=detailed_result["total_days"],
            date_range=detailed_result["date_range"],
            summary=detailed_result["summary"],
            success=True
        )
        
        print(f"🎉 상세 일정 생성 완료!")
        print(f"   📅 총 {detailed_result['total_days']}일 일정")
        print(f"   지역: {detailed_result['summary']['regions_covered']}")
        print(f"   💸 예상 비용: {detailed_result['estimated_total_cost']:,}원")
        
        return response
        
    except Exception as e:
        print(f"❌ 상세 일정 생성 실패: {e}")
        
        # 실패 시 폴백: 기존 방식으로 JSON 일정만 생성
        try:
            legacy_schedule_items = build_itineraries(slots, jobs, tours)
            
            # ScheduleItem을 Itinerary로 변환
            legacy_itineraries = [
                Itinerary(
                    day=item.day,
                    date=item.date,
                    plan_items=item.plan_items,
                    total_distance_km=item.total_distance_km,
                )
                for item in legacy_schedule_items
            ]
            
            # 기본 메타데이터 생성
            start_date_str = slots.get("start_date", "") or "2025-09-01"
            date_range = [start_date_str]
            
            regions_covered = list(set([
                getattr(job, 'region', '지역미상') for job in jobs
            ] + [
                getattr(tour, 'region', '지역미상') for tour in tours
            ]))
            
            fallback_summary = {
                "total_jobs": len(jobs),
                "total_tours": len(tours),
                "regions_covered": regions_covered,
                "activity_types": ["job", "tour"]
            }
            
            # 폴백 자연어 일정 생성
            fallback_itinerary = _generate_simple_fallback_itinerary(
                jobs, tours, start_date_str
            )
            
            return DetailedItineraryResponse(
                legacy_itineraries=legacy_itineraries,
                natural_language_itinerary=fallback_itinerary,
                total_days=1,
                date_range=date_range,
                summary=fallback_summary,
                success=False,
                error_message=f"GPT-4o 일정 생성 실패, 기본 일정으로 폴백: {str(e)}"
            )
            
        except Exception as fallback_error:
            print(f"❌❌ 폴백 일정 생성도 실패: {fallback_error}")
            
            # 최종 실패 응답
            return DetailedItineraryResponse(
                legacy_itineraries=[],
                natural_language_itinerary="일정 생성에 실패했습니다. 다시 시도해 주세요.",
                total_days=0,
                date_range=[],
                estimated_total_cost=0,
                summary={"total_jobs": 0, "total_tours": 0, "regions_covered": [], "activity_types": []},
                success=False,
                error_message=f"전체 일정 생성 실패: {str(e)}, 폴백도 실패: {str(fallback_error)}"
            )


def _generate_simple_fallback_itinerary(
    jobs: List[JobPost], 
    tours: List[TourSpot], 
    date: str
) -> str:
    """간단한 폴백 일정 생성 (GPT 없이) - 선택된 카드들을 명확히 반영"""
    
    itinerary = f"# 🌾 선택된 카드 기반 농촌 일여행 일정\n\n"
    itinerary += f"**일정 날짜**: {date}\n\n"
    itinerary += f"**선택된 농촌 일거리**: {len(jobs)}개\n"
    itinerary += f"**선택된 관광지**: {len(tours)}개\n\n"
    
    current_time = "08:00"
    day_count = 1
    
    # 각 선택된 일거리를 개별 일차로 배치
    for job in jobs:
        itinerary += f"## Day {day_count} - 농촌 일거리 체험\n\n"
        
        job_title = getattr(job, 'title', '농촌 일거리')
        job_region = getattr(job, 'region', '지역미상')
        job_start_time = getattr(job, 'start_time', '08:00')
        job_end_time = getattr(job, 'end_time', '17:00')
        
        itinerary += f"### 🌾 {job_title}\n"
        itinerary += f"**시간**: {job_start_time} - {job_end_time}\n"
        itinerary += f"**위치**: {job_region}\n"
        itinerary += f"**활동**: 농촌 일거리 체험을 통한 농업 경험 및 지역 문화 학습\n\n"
        
        # 점심 시간 추가
        itinerary += f"### 🍽️ 점심 식사 (12:00 - 13:00)\n"
        itinerary += f"**위치**: {job_region} 인근 지역 식당\n"
        itinerary += f"**메뉴**: 지역 특색 음식 및 농촌 체험 도시락\n\n"
        
        day_count += 1
    
    # 각 선택된 관광지를 개별 일차로 배치  
    for tour in tours:
        itinerary += f"## Day {day_count} - 관광지 체험\n\n"
        
        tour_title = getattr(tour, 'title', getattr(tour, 'name', '관광지'))
        tour_region = getattr(tour, 'region', '지역미상')
        
        itinerary += f"### 🏞️ {tour_title}\n"
        itinerary += f"**시간**: 09:00 - 17:00\n"
        itinerary += f"**위치**: {tour_region}\n"
        itinerary += f"**활동**: 관광지 탐방 및 지역 문화 체험\n\n"
        
        # 점심 시간 추가
        itinerary += f"### 🍽️ 점심 식사 (12:00 - 13:00)\n"
        itinerary += f"**위치**: {tour_region} 인근 관광지 식당\n"
        itinerary += f"**메뉴**: 지역 특산물 및 관광지 특색 음식\n\n"
        
        day_count += 1
    
    # 선택된 카드가 없는 경우
    if not jobs and not tours:
        itinerary += "## 선택된 카드가 없습니다\n\n"
        itinerary += "농촌 일거리나 관광지 카드를 선택한 후 다시 시도해 주세요.\n\n"
    
    itinerary += "---\n\n"
    itinerary += "💡 **참고사항**:\n"
    itinerary += "- 위 일정은 선택하신 카드를 기반으로 자동 생성되었습니다.\n"
    itinerary += "- 실제 운영시간은 각 농장/관광지에 문의하여 확인해 주세요.\n"
    itinerary += "- 이동 시간과 교통편은 별도로 계획해 주세요.\n\n"
    
    return itinerary
