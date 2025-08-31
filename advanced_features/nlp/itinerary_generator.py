"""
app/nlp/itinerary_generator.py
==============================
GPT-4o 기반 **자연어 일정 생성** 모듈

역할
----
1. 사용자 슬롯 정보 + 선택된 일거리/관광지 정보를 바탕으로
2. GPT-4o를 활용하여 실제적이고 최적화된 다중 일정을 자연어로 생성
3. 날짜, 시간, 거리, 예산을 종합적으로 고려한 현실적인 일정 제안

주요 기능
--------
- generate_detailed_itinerary(): 메인 일정 생성 함수
- _calculate_travel_time(): 거리 기반 이동 시간 계산
- _optimize_daily_schedule(): 일별 일정 최적화
- _format_itinerary_output(): 자연어 일정 포맷팅
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import openai
from dataclasses import dataclass

from app.config import get_settings
from app.db.models import JobPost, TourSpot
from app.utils.caching import get_cache, set_cache

settings = get_settings()

# OpenAI 클라이언트 초기화 (프록시 관련 에러 회피)
import httpx

# SSL 검증 비활성화된 httpx 클라이언트로 OpenAI 클라이언트 생성
custom_http_client = httpx.Client(verify=False)
client = openai.Client(
    api_key=settings.openai_api_key,
    http_client=custom_http_client
)


@dataclass
class ActivityInfo:
    """활동 정보 데이터 클래스"""
    id: int
    name: str
    type: str  # 'job' or 'tour'
    region: str  # 지역 (관광지용)
    address: str  # 주소 (농가용 - System_Improvements.md 요구사항)
    lat: Optional[float]
    lon: Optional[float]
    start_time: Optional[str]
    end_time: Optional[str] 
    estimated_duration: int  # 분 단위
    cost: int
    tags: List[str]
    description: str


def generate_detailed_itinerary(
    slots: dict,
    selected_jobs: List[JobPost],
    selected_tours: List[TourSpot],
    user_query: str = ""
) -> Dict[str, Any]:
    """
    GPT-4o를 활용한 상세 자연어 일정 생성
    
    Parameters
    ----------
    slots : dict
        슬롯 추출 결과 (날짜, 지역, 활동 태그 등)
    selected_jobs : List[JobPost]
        사용자가 선택한 일거리 목록
    selected_tours : List[TourSpot]
        사용자가 선택한 관광지 목록
    user_query : str
        원본 사용자 쿼리
        
    Returns
    -------
    Dict[str, Any]
        생성된 일정 정보 (자연어 일정, 구조화된 데이터 포함)
    """
    # 캐시 키 생성
    cache_key = f"itinerary::{user_query}::{len(selected_jobs)}::{len(selected_tours)}"
    cached_result = get_cache(cache_key)
    if cached_result:
        return cached_result
    
    print(f"🗓️ GPT-4o 기반 상세 일정 생성 시작")
    print(f"   📅 기간: {slots.get('start_date', '미정')} ~ {slots.get('end_date', '미정')}")
    print(f"   💼 선택 일거리: {len(selected_jobs)}개")
    print(f"   선택 관광지: {len(selected_tours)}개")
    
    # 1단계: 활동 정보 수집 및 전처리
    activities = _prepare_activity_data(selected_jobs, selected_tours)
    
    # 2단계: 날짜 범위 계산
    date_range = _calculate_date_range(slots)
    
    # 3단계: 지역별 활동 그룹화 및 최적화
    optimized_schedule = _optimize_activities_by_region_and_time(activities, date_range)
    
    # 4단계: GPT-4o로 자연어 일정 생성
    natural_language_itinerary = _generate_natural_language_itinerary(
        slots, optimized_schedule, user_query, date_range
    )
    
    # 5단계: 결과 구조화
    result = {
        "success": True,
        "natural_language_itinerary": natural_language_itinerary,
        "structured_schedule": optimized_schedule,
        "date_range": date_range,
        "total_days": len(date_range),
        "estimated_total_cost": _calculate_total_cost(activities),
        "summary": {
            "total_jobs": len(selected_jobs),
            "total_tours": len(selected_tours),
            "regions_covered": list(set(activity.region for activity in activities)),
            "activity_types": list(set(activity.type for activity in activities))
        }
    }
    
    # 캐시에 저장
    set_cache(cache_key, result)
    
    print(f"✅ 일정 생성 완료: {len(date_range)}일 일정")
    return result


def _prepare_activity_data(jobs: List[JobPost], tours: List[TourSpot]) -> List[ActivityInfo]:
    """일거리와 관광지 데이터를 ActivityInfo 객체로 변환"""
    activities = []
    
    # 일거리 데이터 변환 (System_Improvements.md: address 필드 사용)
    for job in jobs:
        activities.append(ActivityInfo(
            id=job.id,
            name=job.title,
            type="job",
            region=job.region or "지역미상",
            address=getattr(job, 'address', job.region or "주소미상"),  # address 필드 우선 사용
            lat=getattr(job, 'lat', None),
            lon=getattr(job, 'lon', None),
            start_time=getattr(job, 'start_time', "09:00"),
            end_time=getattr(job, 'end_time', "17:00"),
            estimated_duration=_calculate_duration(
                getattr(job, 'start_time', "09:00"),
                getattr(job, 'end_time', "17:00")
            ),
            cost=0,  # 비용 고려하지 않음
            tags=job.tags.split(',') if job.tags else [],
            description=f"{job.title} - {getattr(job, 'address', job.region or '주소미상')}"
        ))
    
    # 관광지 데이터 변환
    for tour in tours:
        activities.append(ActivityInfo(
            id=tour.id,
            name=tour.name,
            type="tour",
            region=tour.region or "지역미상",
            address=tour.region or "지역미상",  # 관광지는 region과 같은 값 사용
            lat=getattr(tour, 'lat', None),
            lon=getattr(tour, 'lon', None),
            start_time=None,
            end_time=None,
            estimated_duration=120,  # 기본 2시간
            cost=0,  # 비용 고려하지 않음
            tags=tour.tags.split(',') if tour.tags else [],
            description=f"{tour.name} - {tour.region}"
        ))
    
    return activities


def _calculate_duration(start_time: str, end_time: str) -> int:
    """시작/종료 시간으로부터 지속 시간(분) 계산"""
    try:
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        duration = (end - start).total_seconds() / 60
        return max(60, int(duration))  # 최소 1시간
    except:
        return 480  # 기본 8시간


def _calculate_date_range(slots: dict) -> List[str]:
    """슬롯 정보로부터 날짜 범위 계산"""
    start_date_str = slots.get("start_date", "")
    end_date_str = slots.get("end_date", "")
    
    # 날짜가 없으면 2025년 9월 첫째 주로 기본 설정
    if not start_date_str:
        start_date = datetime(2025, 9, 1).date()  # 2025년 9월 1일
    else:
        try:
            parsed_date = datetime.fromisoformat(start_date_str).date()
            # 2025년으로 조정
            start_date = parsed_date.replace(year=2025)
        except:
            start_date = datetime(2025, 9, 1).date()
    
    if not end_date_str:
        end_date = start_date + timedelta(days=2)  # 기본 3일
    else:
        try:
            parsed_date = datetime.fromisoformat(end_date_str).date()
            # 2025년으로 조정
            end_date = parsed_date.replace(year=2025)
        except:
            end_date = start_date + timedelta(days=2)
    
    # 최소 1일, 최대 7일로 제한
    if end_date <= start_date:
        end_date = start_date + timedelta(days=1)
    
    days_diff = (end_date - start_date).days + 1
    if days_diff > 7:
        end_date = start_date + timedelta(days=6)
    
    # 날짜 범위 생성
    date_range = []
    current_date = start_date
    while current_date <= end_date:
        date_range.append(current_date.isoformat())
        current_date += timedelta(days=1)
    
    return date_range


def _optimize_activities_by_region_and_time(
    activities: List[ActivityInfo], 
    date_range: List[str]
) -> Dict[str, List[ActivityInfo]]:
    """지역과 시간을 고려한 활동 최적화 배치"""
    print(f"🔄 활동 최적화 시작: {len(activities)}개 활동을 {len(date_range)}일에 배치")
    
    # 지역별 그룹화
    region_groups = {}
    for activity in activities:
        region = activity.region
        if region not in region_groups:
            region_groups[region] = []
        region_groups[region].append(activity)
    
    print(f"   지역별 분포: {[(region, len(acts)) for region, acts in region_groups.items()]}")
    
    # 일별 일정 배치
    daily_schedule = {}
    activity_pool = activities.copy()
    
    for i, date in enumerate(date_range):
        daily_schedule[date] = []
        day_number = i + 1
        
        # 각 날짜별로 활동 배치 (지역 근접성 고려)
        if activity_pool:
            # 첫날은 일거리 우선, 나머지 날은 관광지 우선
            if day_number == 1:
                # 일거리 우선 선택
                jobs_today = [act for act in activity_pool if act.type == "job"]
                tours_today = [act for act in activity_pool if act.type == "tour"]
                
                # 일거리가 있으면 1-2개 선택
                selected_jobs = jobs_today[:min(2, len(jobs_today))]
                for job in selected_jobs:
                    daily_schedule[date].append(job)
                    activity_pool.remove(job)
                
                # 같은 지역 관광지 추가
                if selected_jobs:
                    main_region = selected_jobs[0].region
                    same_region_tours = [t for t in tours_today if t.region == main_region]
                    selected_tours = same_region_tours[:min(2, len(same_region_tours))]
                    for tour in selected_tours:
                        daily_schedule[date].append(tour)
                        activity_pool.remove(tour)
            else:
                # 나머지 날은 남은 활동들을 지역별로 배치
                remaining_per_day = max(1, len(activity_pool) // (len(date_range) - i))
                selected_activities = activity_pool[:remaining_per_day]
                
                for activity in selected_activities:
                    daily_schedule[date].append(activity)
                    activity_pool.remove(activity)
    
    # 남은 활동들을 마지막 날에 추가
    if activity_pool and date_range:
        last_date = date_range[-1]
        daily_schedule[last_date].extend(activity_pool)
    
    print(f"   ✅ 일별 배치 완료:")
    for date, acts in daily_schedule.items():
        print(f"      {date}: {len(acts)}개 활동")
    
    return daily_schedule


def _generate_natural_language_itinerary(
    slots: dict,
    optimized_schedule: Dict[str, List[ActivityInfo]],
    user_query: str,
    date_range: List[str]
) -> str:
    """GPT-4o를 활용한 자연어 일정 생성"""
    
    print(f"🤖 GPT-4o 자연어 일정 생성 중...")
    
    # 일정 정보를 텍스트로 구성
    schedule_text = ""
    for i, date in enumerate(date_range, 1):
        activities = optimized_schedule.get(date, [])
        schedule_text += f"\n{i}일차 ({date}):\n"
        
        if not activities:
            schedule_text += "  - 휴식일\n"
            continue
            
        jobs = [act for act in activities if act.type == "job"]
        tours = [act for act in activities if act.type == "tour"]
        
        if jobs:
            schedule_text += "  [일거리]\n"
            for job in jobs:
                schedule_text += f"    - {job.name} ({job.address}) [{job.start_time}-{job.end_time}]\n"
        
        if tours:
            schedule_text += "  [관광지]\n"
            for tour in tours:
                schedule_text += f"    - {tour.name} ({tour.region})\n"
    
    # GPT-4o 프롬프트 구성
    system_prompt = """
당신은 농촌 일자리와 관광을 결합한 일여행 일정을 전문적으로 계획하는 여행 가이드입니다.

⚠️ **중요한 제약사항**:
- 제공된 농가/관광지 정보를 우선적으로 사용하세요
- 만약 제공된 정보가 부족하면, 실제 지역에 맞는 일반적인 농장/관광 활동으로 보완하세요
- 사용자의 요청에 최대한 맞는 일정을 생성하세요

**반드시 다음 형식으로 일정을 작성해주세요:**

🗓️ Day 1 (MM/DD) [주요 활동명]
[구체적인 활동 내용]
[장소명/주소 정보]

🗓️ Day 2 ~ 4 (MM/DD ~ MM/DD) [주요 활동명]
HH:MM ~ HH:MM [구체적인 시간대와 활동]
[추가 정보나 제공사항]

**형식 지침**:
1. 각 일차는 🗓️ 이모지로 시작
2. 연속된 날짜는 Day 2 ~ 4 형식으로 그룹화
3. 농가 일정은 정확한 시간대 (08:00 ~ 15:00) 표시
4. 관광지는 방문 시간과 함께 명시
5. 주소나 위치 정보가 있으면 포함
6. 간결하고 실용적인 설명

**내용 지침**:
- 제공된 일거리 정보의 시간대를 정확히 준수
- 제공된 관광지 정보만 사용하여 배치
- 실제 지역명과 장소명을 정확히 사용
- 일반적인 식사 시간과 휴식 시간만 제안

**톤앤매너**:
- 간결하고 명확한 설명
- 농촌 체험의 매력 강조
- 구체적인 팁과 주의사항 포함
"""

    user_prompt = f"""
사용자 요청: "{user_query}"

추출된 선호사항:
- 지역: {slots.get('region_pref', [])}
- 활동: {slots.get('activity_tags', [])}
- 기간: {len(date_range)}일

선택된 실제 농가 및 관광지 일정:
{schedule_text}

⚠️ **중요**: 위에 제공된 실제 농가와 관광지 정보만을 사용하여 일정을 작성해주세요.
- 농가명, 관광지명, 지역명을 정확히 사용하세요
- 임의로 다른 장소나 농가를 추가하지 마세요
- 제공된 시간대를 준수하세요

각 일차별로 상세한 일정과 함께 이동 경로, 일반적인 식사 시간을 포함한 자연어 일정을 작성해주세요.
"""

    try:
        response = client.chat.completions.create(
            model=settings.itinerary_model,  # GPT-4o
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        itinerary = response.choices[0].message.content
        print(f"✅ GPT-4o 일정 생성 완료 ({len(itinerary)}자)")
        return itinerary
        
    except Exception as e:
        print(f"⚠️ GPT-4o 일정 생성 실패: {e}")
        # 폴백: 기본 템플릿 사용
        return _generate_fallback_itinerary(optimized_schedule, date_range)


def _generate_fallback_itinerary(
    schedule: Dict[str, List[ActivityInfo]], 
    date_range: List[str]
) -> str:
    """GPT 실패 시 사용할 기본 일정 템플릿 (SMART_SCHEDULE_GUIDE.md 형식)"""
    
    itinerary = ""
    
    # 날짜별 활동 그룹화 (연속된 같은 활동은 묶기)
    day_count = 1
    i = 0
    while i < len(date_range):
        date = date_range[i]
        activities = schedule.get(date, [])
        
        if not activities:
            # 빈 날은 휴식일로 처리
            date_formatted = date[5:].replace('-', '/')  # 09/01 형식
            itinerary += f"🗓️ Day {day_count} ({date_formatted}) 휴식 및 자유시간\n"
            itinerary += "지역 탐방 및 개인 활동\n\n"
            day_count += 1
            i += 1
            continue
        
        # 같은 타입의 연속 활동 찾기 (특히 농장 일)
        same_activity_dates = [date]
        current_activity = activities[0] if activities else None
        
        if current_activity and current_activity.type == "job":
            # 농장 일의 경우 연속일로 그룹화
            j = i + 1
            while j < len(date_range):
                next_date = date_range[j]
                next_activities = schedule.get(next_date, [])
                
                if (next_activities and 
                    len(next_activities) == 1 and 
                    next_activities[0].type == "job" and
                    next_activities[0].name == current_activity.name):
                    same_activity_dates.append(next_date)
                    j += 1
                else:
                    break
        else:
            j = i + 1
        
        # 날짜 형식 변환 (2025-09-01 -> 09/01)
        start_date = same_activity_dates[0]
        end_date = same_activity_dates[-1] if len(same_activity_dates) > 1 else start_date
        
        start_formatted = start_date[5:].replace('-', '/')
        end_formatted = end_date[5:].replace('-', '/')
        
        # 헤더 생성
        if len(same_activity_dates) == 1:
            header = f"🗓️ Day {day_count} ({start_formatted})"
        else:
            end_day = day_count + len(same_activity_dates) - 1
            header = f"🗓️ Day {day_count} ~ {end_day} ({start_formatted} ~ {end_formatted})"
        
        # 주요 활동명 추가
        if activities:
            main_activity = activities[0].name
            if activities[0].type == "job":
                header += f" {main_activity}"
            else:
                header += f" {main_activity} 관광"
        
        itinerary += f"{header}\n"
        
        # 활동 상세 내용
        for activity in activities:
            if activity.type == "job":
                itinerary += f"{activity.start_time} ~ {activity.end_time} 농장 출근\n"
                itinerary += f"위치: {activity.address if activity.type == 'job' else activity.region}\n"
                if hasattr(activity, 'tags') and activity.tags:
                    tags_list = activity.tags.split(',') if isinstance(activity.tags, str) else activity.tags
                    if tags_list:
                        itinerary += f"작업 내용: {', '.join(tags_list[:2])}\n"
                itinerary += "중식 제공\n"
            elif activity.type == "tour":
                itinerary += f"{activity.name}\n"
                itinerary += f"위치: {activity.address if activity.type == 'job' else activity.region}\n"
                itinerary += "지역 명소 탐방\n"
        
        itinerary += "\n"
        day_count += len(same_activity_dates)
        i = j
    
    return itinerary


def _calculate_total_cost(activities: List[ActivityInfo]) -> int:
    """전체 예상 비용 계산 (비용 고려하지 않음)"""
    return 0  # 비용/예산은 고려하지 않음