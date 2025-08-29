"""
Smart Scheduling Orchestrator - 지능형 농촌 일여행 스케줄링 시스템

선택된 농가/관광지 카드를 기반으로 개인 맞춤 일정을 생성하는 AI Agent 오케스트레이터입니다.
GPT-4o를 활용한 지리적/시간적/개인화 최적화를 통해 최적의 일정을 제공합니다.

주요 기능:
- 선택된 카드 기반 일정 생성
- GPT-4o 기반 지능형 일정 배치
- 일정 피드백 및 수정 시스템
- 실시간 재최적화
"""

import time
import uuid
import copy
from typing import Dict, List, Any
from app.services.accommodation_restaurant_service import get_itinerary_recommendations
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.config import get_settings
from app.schemas import DetailedItineraryResponse, Itinerary
from app.db.models import JobPost, TourSpot
from app.services.accommodation_restaurant_service import get_itinerary_recommendations

settings = get_settings()


class SmartSchedulingOrchestrator:
    """스마트 스케줄링 전용 오케스트레이터."""
    
    def __init__(self, db_session: Session = None):
        if db_session is None:
            from app.db.database import SessionLocal
            self.db_session = SessionLocal()
            self._should_close_session = True
        else:
            self.db_session = db_session
            self._should_close_session = False
        self.session_cache = {}  # 세션별 일정 데이터 캐시
        
    def create_optimized_itinerary(
        self,
        slots: dict,
        selected_jobs: List[JobPost],
        selected_tours: List[TourSpot],
        user_query: str,
        user_preferences: dict = None
    ) -> DetailedItineraryResponse:
        """
        IntelligentPlannerAgent를 활용한 선택된 카드 기반 최적화된 일정 생성.
        
        Args:
            slots: 슬롯 추출 결과
            selected_jobs: 선택된 농가 카드
            selected_tours: 선택된 관광지 카드
            user_query: 원본 쿼리
            user_preferences: 사용자 선호도
            
        Returns:
            DetailedItineraryResponse: 생성된 일정
        """
        
        session_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            print(f"스마트 스케줄링 시작 (Session: {session_id[:8]})")
            
            # IntelligentPlannerAgent 초기화 (db_session 전달)
            from app.agents.intelligent_planner_agent import IntelligentPlannerAgent
            planner_agent = IntelligentPlannerAgent(db_session=self.db_session)
            
            # 지역 내 추가 관광지 추천
            print(f"🔄 0단계: 지역 내 추가 관광지 추천 중...")
            additional_tours = planner_agent.recommend_additional_regional_tours(
                selected_jobs, selected_tours, user_preferences or {}, slots
            )
            
            # 선택된 관광지에 추가 관광지 통합
            all_tours = selected_tours + additional_tours
            print(f"✅ 총 관광지 수: {len(all_tours)}개 (선택: {len(selected_tours)}개, 추가: {len(additional_tours)}개)")
            
            # Agent 기반 최적화 시도 (실패 시 즉시 fallback으로 이동)
            try:
                # 1단계: 지리적 최적화 분석 (GPT-4o Agent)
                print(f"🔄 1단계: 지리적 최적화 분석 실행 중...")
                geo_optimization = planner_agent.analyze_geographical_optimization(
                    selected_jobs, all_tours, user_preferences or {}
                )
                print(f"✅ 지리적 최적화 완료: {type(geo_optimization)} {len(str(geo_optimization)[:100])}...")
                
                # 2단계: 시간적 최적화 분석 (GPT-4o Agent) 
                print(f"🔄 2단계: 시간적 최적화 분석 실행 중...")
                time_optimization = planner_agent.analyze_temporal_optimization(
                    selected_jobs, all_tours, slots, geo_optimization
                )
                print(f"✅ 시간적 최적화 완료: {type(time_optimization)} {len(str(time_optimization)[:100])}...")
                
                # 3단계: 개인화 맞춤 배치 (GPT-4o Agent)
                print(f"🔄 3단계: 개인화 맞춤 배치 실행 중...")
                personalization_result = planner_agent.create_personalized_arrangement(
                    geo_optimization, time_optimization, user_preferences or {}, slots
                )
                print(f"✅ 개인화 맞춤 배치 완료: {type(personalization_result)} {len(str(personalization_result)[:100])}...")
                
                # Agent 실행 로그 확인
                logs = planner_agent.get_execution_logs()
                agent_failures = [log for log in logs if not log.get("success", True)]
                
                if agent_failures:
                    print(f"💡 GPT-4o Agent 일부 실패, fallback 사용")
                    print(f"   실패한 Agent 단계: {[log['function'] for log in agent_failures]}")
                    raise Exception("Agent 실패로 인한 fallback 사용")
                
                print(f"GPT-4o Agent 최적화 완료")
                    
            except Exception as e:
                print(f"🚨 AI Agent 실행 실패 상세 진단:")
                print(f"   예외 타입: {type(e).__name__}")
                print(f"   예외 메시지: {str(e)}")
                print(f"   발생 위치: {e.__traceback__.tb_frame.f_code.co_name if e.__traceback__ else 'Unknown'}")
                
                # 추가 컨텍스트 정보
                print(f"   선택된 일자리 수: {len(selected_jobs)}")
                print(f"   선택된 관광지 수: {len(selected_tours)}")
                print(f"   사용자 슬롯: {slots}")
                
                import traceback
                print(f"   전체 스택 트레이스:")
                traceback.print_exc()
                
                print(f"💡 선택된 카드를 활용한 맞춤형 일정 생성 중... (Agent 실패로 fallback 사용)")
                # fallback으로 이동 (추가 관광지 포함)
                return self._create_fallback_itinerary(
                    selected_jobs, all_tours, slots, user_query
                )
            
            # 4단계: GPT-4o 기반 자연어 일정 생성
            natural_language_itinerary = self._generate_natural_language_itinerary_v2(
                geo_optimization,
                time_optimization,
                personalization_result,
                user_query,
                slots,
                selected_jobs,
                all_tours
            )
            
            # 5단계: 결과 구조화 및 캐싱
            execution_time = time.time() - start_time
            
            # 최종 일정 데이터 구조화
            final_schedule = self._structure_final_schedule(
                geo_optimization,
                time_optimization,
                personalization_result
            )
            
            # 6단계: 숙박 및 음식점 추천
            accommodation_restaurant_recommendations = {}
            if self.db_session:
                try:
                    # 선택된 일자리와 관광지의 위치 정보 수집 (nan 값 필터링)
                    import math
                    job_locations = [
                        (job.lat, job.lon) 
                        for job in selected_jobs 
                        if job.lat is not None and job.lon is not None 
                        and not math.isnan(job.lat) and not math.isnan(job.lon)
                    ]
                    tour_locations = [
                        (tour.lat, tour.lon) 
                        for tour in selected_tours 
                        if tour.lat is not None and tour.lon is not None 
                        and not math.isnan(tour.lat) and not math.isnan(tour.lon)
                    ]
                    
                    print(f"🔍 위치 정보 디버깅:")
                    print(f"   선택된 농가 수: {len(selected_jobs)}개")
                    print(f"   농가 위치 정보: {len(job_locations)}개")
                    for i, job in enumerate(selected_jobs):
                        print(f"     농가{i+1}: ID={job.id} | {job.title} | lat={job.lat} | lon={job.lon} | 타입={type(job.lat)} {type(job.lon)}")
                    
                    print(f"   선택된 관광지 수: {len(selected_tours)}개") 
                    print(f"   관광지 위치 정보: {len(tour_locations)}개")
                    for i, tour in enumerate(selected_tours):
                        print(f"     관광지{i+1}: ID={tour.id} | {tour.name} | lat={tour.lat} | lon={tour.lon} | 타입={type(tour.lat)} {type(tour.lon)}")
                    
                    print(f"🌍 실제 수집된 위치 좌표:")
                    print(f"   job_locations: {job_locations}")
                    print(f"   tour_locations: {tour_locations}")
                    print(f"   전체 위치 수: {len(job_locations) + len(tour_locations)}개")
                    
                    if not job_locations and not tour_locations:
                        print(f"⚠️ 위치 정보가 없어 기본 좌표 사용 (김제 중심)")
                        # 김제 중심 좌표를 기본값으로 사용
                        job_locations = [(35.8020, 126.8814)]  # 김제시 중심부
                    
                    accommodation_restaurant_recommendations = get_itinerary_recommendations(
                        db=self.db_session,
                        job_locations=job_locations,
                        tour_locations=tour_locations
                    )
                    
                    print(f"✅ 숙박/음식점 추천 완료: 숙박 {len(accommodation_restaurant_recommendations.get('accommodations', []))}개, 음식점 {len(accommodation_restaurant_recommendations.get('restaurants', []))}개")
                    
                except Exception as e:
                    print(f"⚠️ 숙박/음식점 추천 실패: {e}")
                    import traceback
                    print(f"상세 에러: {traceback.format_exc()}")
                    accommodation_restaurant_recommendations = {
                        "accommodations": [],
                        "restaurants": []
                    }
            
            result = DetailedItineraryResponse(
                legacy_itineraries=self._create_legacy_itineraries_v2(final_schedule),
                natural_language_itinerary=natural_language_itinerary,
                total_days=len(final_schedule.get("daily_schedule", {})),
                date_range=list(final_schedule.get("daily_schedule", {}).keys()),
                estimated_total_cost=0,  # 비용 계산 생략 (WORKFLOW.md 방침)
                summary={
                    "total_jobs": len(selected_jobs),
                    "total_tours": len(selected_tours),
                    "regions_covered": geo_optimization.get("optimal_route", []),
                    "activity_types": ["job", "tour"],
                    "optimization_applied": True,
                    "session_id": session_id,
                    "geographical_efficiency": geo_optimization.get("travel_efficiency", "medium"),
                    "temporal_efficiency": time_optimization.get("time_efficiency", "good"),
                    "personalization_level": personalization_result.get("activity_density", "medium"),
                    "agent_execution_logs": planner_agent.get_execution_logs()
                },
                accommodations=accommodation_restaurant_recommendations.get("accommodations", []),
                restaurants=accommodation_restaurant_recommendations.get("restaurants", []),
                success=True
            )
            
            # 세션 캐싱 (피드백 시스템용)
            self.session_cache[session_id] = {
                "final_schedule": final_schedule,
                "geo_optimization": geo_optimization,
                "time_optimization": time_optimization,
                "personalization_result": personalization_result,
                "selected_jobs": selected_jobs,
                "selected_tours": selected_tours,
                "user_preferences": user_preferences,
                "slots": slots,
                "user_query": user_query,
                "natural_language_itinerary": natural_language_itinerary,  # 자연어 일정 추가
                "created_at": datetime.now(),
                "planner_agent_logs": planner_agent.get_execution_logs()
            }
            
            print(f"스마트 스케줄링 완료 (실행시간: {execution_time:.2f}초)")
            print(f"   지리적 효율성: {geo_optimization.get('travel_efficiency', 'medium')}")
            print(f"   시간적 효율성: {time_optimization.get('time_efficiency', 'good')}")
            print(f"   개인화 수준: {personalization_result.get('activity_density', 'medium')}")
            
            return result
            
        except Exception as e:
            print(f"❌ 스마트 스케줄링 실패: {str(e)}")
            
            # 폴백: 기존 방식 사용 (원본 선택된 카드만 사용)
            return self._create_fallback_itinerary(
                selected_jobs, selected_tours, slots, user_query
            )
        finally:
            # 세션 정리
            if hasattr(self, '_should_close_session') and self._should_close_session:
                if self.db_session:
                    self.db_session.close()
    
    def reoptimize_itinerary(
        self,
        session_id: str,
        modifications: List[Dict[str, Any]],
        user_preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        일정 피드백을 반영한 실시간 재최적화.
        
        Args:
            session_id: 세션 ID
            modifications: 사용자 수정사항
            user_preferences: 업데이트된 사용자 선호도
            
        Returns:
            Dict: 재최적화된 일정 결과
        """
        
        start_time = time.time()
        
        try:
            print(f"일정 재최적화 시작 (Session: {session_id[:8]})")
            
            # 1) 세션 데이터 조회
            if session_id not in self.session_cache:
                raise ValueError(f"세션 데이터를 찾을 수 없습니다: {session_id}")
            
            cached_data = self.session_cache[session_id]
            
            # 2) 수정사항 적용
            updated_schedule = self._apply_feedback_modifications(
                cached_data["final_schedule"],
                modifications
            )
            
            # 3) 사용자 선호도 업데이트
            merged_preferences = {**cached_data.get("user_preferences", {}), **user_preferences}
            
            # 4) IntelligentPlannerAgent를 활용한 재최적화
            from app.agents.intelligent_planner_agent import IntelligentPlannerAgent
            planner_agent = IntelligentPlannerAgent()
            
            # 기존 최적화 결과를 바탕으로 개인화 재배치
            reoptimization_result = planner_agent.create_personalized_arrangement(
                cached_data["geo_optimization"],
                cached_data["time_optimization"],
                merged_preferences,
                cached_data["slots"]
            )
            
            # 5) 자연어 일정 재생성
            updated_natural_language = self._generate_natural_language_itinerary_v2(
                cached_data["geo_optimization"],
                cached_data["time_optimization"],
                reoptimization_result,
                cached_data["user_query"],
                cached_data["slots"]
            )
            
            # 6) 변경사항 요약
            changes_summary = self._summarize_optimization_changes(
                cached_data["final_schedule"],
                reoptimization_result
            )
            
            # 7) 캐시 업데이트
            self.session_cache[session_id]["final_schedule"] = updated_schedule
            self.session_cache[session_id]["user_preferences"] = merged_preferences
            self.session_cache[session_id]["last_reoptimization"] = reoptimization_result
            
            execution_time = time.time() - start_time
            
            print(f"일정 재최적화 완료 (실행시간: {execution_time:.2f}초)")
            
            return {
                "success": True,
                "natural_language_itinerary": updated_natural_language,
                "changes_summary": changes_summary,
                "execution_time": execution_time,
                "optimization_details": {
                    "geographical_efficiency": cached_data["geo_optimization"].get("travel_efficiency", "medium"),
                    "temporal_efficiency": cached_data["time_optimization"].get("time_efficiency", "good"),
                    "personalization_level": reoptimization_result.get("activity_density", "medium")
                }
            }
            
        except Exception as e:
            print(f"❌ 일정 재최적화 실패: {str(e)}")
            
            return {
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    
    def _create_fallback_itinerary(
        self,
        selected_jobs: List[JobPost],
        selected_tours: List[TourSpot],
        slots: dict,
        user_query: str
    ) -> DetailedItineraryResponse:
        """폴백: 선택된 카드를 기반으로 간단한 일정 생성."""
        
        print("선택된 카드 기반 폴백 일정 생성 중...")
        print(f"   일거리: {len(selected_jobs)}개, 관광지: {len(selected_tours)}개")
        
        # 날짜 범위 계산
        start_date = slots.get("start_date", "2025-10-01")
        total_activities = len(selected_jobs) + len(selected_tours)
        total_days = max(1, total_activities)
        
        # 날짜 목록 생성
        from datetime import datetime, timedelta
        try:
            start_dt = datetime.fromisoformat(start_date).date()
        except:
            start_dt = datetime(2025, 10, 1).date()
            
        date_range = [(start_dt + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(total_days)]
        
        # Legacy 일정 생성 (선택된 카드들을 일차별로 배치)
        legacy_itineraries = []
        day_count = 1
        
        # 각 일거리를 개별 일차로 배치
        for job in selected_jobs:
            job_title = getattr(job, 'title', '농촌 일거리')
            start_time = getattr(job, 'start_time', '08:00')
            end_time = getattr(job, 'end_time', '17:00')
            
            legacy_itineraries.append(Itinerary(
                day=day_count,
                date=date_range[day_count-1] if day_count-1 < len(date_range) else start_date,
                plan_items=[f"[JOB] {job_title} ({start_time}~{end_time})"],
                total_distance_km=0.0
            ))
            day_count += 1
        
        # 각 관광지를 개별 일차로 배치  
        for tour in selected_tours:
            tour_title = getattr(tour, 'title', getattr(tour, 'name', '관광지'))
            
            legacy_itineraries.append(Itinerary(
                day=day_count,
                date=date_range[day_count-1] if day_count-1 < len(date_range) else start_date,
                plan_items=[f"[TOUR] {tour_title} (09:00~17:00)"],
                total_distance_km=0.0
            ))
            day_count += 1
        
        # 자연어 일정 생성
        natural_itinerary = self._create_natural_language_itinerary_from_cards(
            selected_jobs, selected_tours, date_range, user_query
        )
        
        # 지역 정보 수집
        regions_covered = list(set([
            getattr(job, 'region', '지역미상') for job in selected_jobs
        ] + [
            getattr(tour, 'region', '지역미상') for tour in selected_tours
        ]))
        
        # 폴백에서도 숙박/음식점 추천
        accommodation_restaurant_recommendations = {}
        if self.db_session:
            try:
                import math
                job_locations = [
                    (job.lat, job.lon) 
                    for job in selected_jobs 
                    if job.lat is not None and job.lon is not None 
                    and not math.isnan(job.lat) and not math.isnan(job.lon)
                ]
                tour_locations = [
                    (tour.lat, tour.lon) 
                    for tour in selected_tours 
                    if tour.lat is not None and tour.lon is not None 
                    and not math.isnan(tour.lat) and not math.isnan(tour.lon)
                ]
                
                accommodation_restaurant_recommendations = get_itinerary_recommendations(
                    db=self.db_session,
                    job_locations=job_locations,
                    tour_locations=tour_locations
                )
                
                print(f"✅ 폴백 숙박/음식점 추천: 숙박 {len(accommodation_restaurant_recommendations.get('accommodations', []))}개, 음식점 {len(accommodation_restaurant_recommendations.get('restaurants', []))}개")
                
            except Exception as e:
                print(f"⚠️ 폴백 숙박/음식점 추천 실패: {e}")
                accommodation_restaurant_recommendations = {
                    "accommodations": [],
                    "restaurants": []
                }
        
        return DetailedItineraryResponse(
            legacy_itineraries=legacy_itineraries,
            natural_language_itinerary=natural_itinerary,
            total_days=total_days,
            date_range=date_range,
            estimated_total_cost=0,
            summary={
                "total_jobs": len(selected_jobs),
                "total_tours": len(selected_tours),
                "regions_covered": regions_covered,
                "activity_types": ["job", "tour"],
                "optimization_applied": False,
                "fallback_method": "selected_cards_based"
            },
            accommodations=accommodation_restaurant_recommendations.get("accommodations", []),
            restaurants=accommodation_restaurant_recommendations.get("restaurants", []),
            success=True
        )
    
    def _create_natural_language_itinerary_from_cards(
        self,
        selected_jobs: List[JobPost],
        selected_tours: List[TourSpot],
        date_range: List[str],
        user_query: str
    ) -> str:
        """AI_AGENT_GUIDE.md 요구사항에 맞는 정확한 형식의 일정 생성."""
        
        # 지역 추출
        main_region = "농촌"
        if selected_jobs:
            job_region = getattr(selected_jobs[0], 'region', '')
            if "김제" in job_region:
                main_region = "전북 김제"
            elif "전북" in job_region:
                main_region = "전북"
        
        total_days = len(date_range)
        
        itinerary_parts = [f"🚘 {main_region} {total_days}일 여행 계획\n"]
        
        day_count = 1
        
        # Day 1: 도착
        if day_count <= total_days:
            date_str = date_range[day_count-1].split('-')[1:] if day_count-1 < len(date_range) else ['09', '05']
            itinerary_parts.append(f"🗓️ Day {day_count} ({date_str[0]}/{date_str[1]}) 도착")
            itinerary_parts.append("![IMAGE_URL]")
            itinerary_parts.append("- 서울 출발")
            itinerary_parts.append("- 숙소 체크인")
            if selected_jobs:
                job_address = getattr(selected_jobs[0], 'address', f"{main_region} 농가")
                itinerary_parts.append(f"   - 주소: {job_address}")
            itinerary_parts.append("")
            day_count += 1
        
        # 농가 일정 배치 (실제 work_date, work_hours 사용)
        for job in selected_jobs:
            if day_count > total_days:
                break
                
            job_title = getattr(job, 'title', '농가 체험')
            work_hours = getattr(job, 'work_hours', '08:00-17:00')
            job_address = getattr(job, 'address', f"{main_region} 농가")
            work_date = getattr(job, 'work_date', '')
            
            # work_date가 연속 기간인지 확인
            if '~' in work_date and day_count + 2 <= total_days:
                # 연속 기간 처리 (예: Day 2~4)
                start_day = day_count
                end_day = min(day_count + 2, total_days - 1)
                
                start_date_str = date_range[start_day-1].split('-')[1:] if start_day-1 < len(date_range) else ['09', '06']
                end_date_str = date_range[end_day-1].split('-')[1:] if end_day-1 < len(date_range) else ['09', '08']
                
                itinerary_parts.append(f"🗓️ Day {start_day}~{end_day} ({start_date_str[0]}/{start_date_str[1]}~{end_date_str[0]}/{end_date_str[1]}) {job_title}")
                itinerary_parts.append("![IMAGE_URL]")
                itinerary_parts.append(f"- {work_hours} {job_title}")
                itinerary_parts.append("- 중식 제공")
                itinerary_parts.append(f"   - 주소: {job_address}")
                itinerary_parts.append("")
                
                day_count = end_day + 1
            else:
                # 단일 날짜 처리
                date_str = date_range[day_count-1].split('-')[1:] if day_count-1 < len(date_range) else ['09', f'{day_count+4:02d}']
                
                itinerary_parts.append(f"🗓️ Day {day_count} ({date_str[0]}/{date_str[1]}) {job_title}")
                itinerary_parts.append("![IMAGE_URL]")
                itinerary_parts.append(f"- {work_hours} {job_title}")
                itinerary_parts.append("- 중식 제공")
                itinerary_parts.append(f"   - 주소: {job_address}")
                itinerary_parts.append("")
                
                day_count += 1
        
        # 관광지 배치 (시간 표기 없이)
        tour_index = 0
        while day_count <= total_days:
            if day_count == total_days:
                # 마지막 날: 귀가
                date_str = date_range[day_count-1].split('-')[1:] if day_count-1 < len(date_range) else ['09', f'{day_count+4:02d}']
                itinerary_parts.append(f"🗓️ Day {day_count} ({date_str[0]}/{date_str[1]}) 귀가")
                itinerary_parts.append("![IMAGE_URL]")
                itinerary_parts.append("- 마무리 및 정리")
                itinerary_parts.append("- 서울 복귀")
                break
            else:
                # 관광 일정 (시간 없이 장소명만)
                date_str = date_range[day_count-1].split('-')[1:] if day_count-1 < len(date_range) else ['09', f'{day_count+4:02d}']
                itinerary_parts.append(f"🗓️ Day {day_count} ({date_str[0]}/{date_str[1]}) 지역 관광")
                itinerary_parts.append("![IMAGE_URL]")
                
                if tour_index < len(selected_tours):
                    tour_name = getattr(selected_tours[tour_index], 'title', getattr(selected_tours[tour_index], 'name', '관광지'))
                    itinerary_parts.append(f"- {tour_name}")
                    tour_index += 1
                    
                    if tour_index < len(selected_tours):
                        tour_name2 = getattr(selected_tours[tour_index], 'title', getattr(selected_tours[tour_index], 'name', '관광지'))
                        itinerary_parts.append(f"- {tour_name2}")
                        tour_index += 1
                else:
                    itinerary_parts.append("- 자유 시간")
                    itinerary_parts.append("- 지역 맛집 탐방")
                
                itinerary_parts.append("")
                
            day_count += 1
        
        return "\n".join(itinerary_parts)
    
    # ====== 유틸리티 메서드들 ======
    
    def _calculate_days_from_slots(self, slots: dict) -> int:
        """슬롯 추출 결과의 start_date와 end_date로부터 정확한 여행 기간 계산."""
        from datetime import datetime
        
        try:
            start_date_str = slots.get("start_date", "")
            end_date_str = slots.get("end_date", "")
            
            if not start_date_str or not end_date_str:
                print(f"⚠️ 슬롯에서 날짜 정보 없음: start_date={start_date_str}, end_date={end_date_str}")
                return 0
            
            # 날짜 파싱
            start_date = datetime.fromisoformat(start_date_str).date()
            end_date = datetime.fromisoformat(end_date_str).date()
            
            # 기간 계산 (종료일 포함)
            duration_days = (end_date - start_date).days + 1
            
            # 유효성 검증 (1-30일 범위)
            if duration_days < 1:
                print(f"⚠️ 잘못된 기간: {duration_days}일 (start: {start_date}, end: {end_date})")
                return 0
            elif duration_days > 30:
                print(f"⚠️ 너무 긴 기간: {duration_days}일 -> 7일로 제한")
                return 7
            
            print(f"✅ 슬롯 기반 기간: {start_date} ~ {end_date} = {duration_days}일")
            return duration_days
            
        except Exception as e:
            print(f"⚠️ 슬롯 기간 계산 실패: {e}")
            return 0
    
    def _calculate_date_range(self, slots: dict) -> List[str]:
        """날짜 범위 계산."""
        start_date_str = slots.get("start_date", "")
        end_date_str = slots.get("end_date", "")
        
        if not start_date_str:
            start_date = datetime(2025, 9, 1).date()
        else:
            try:
                parsed_date = datetime.fromisoformat(start_date_str).date()
                start_date = parsed_date.replace(year=2025)
            except:
                start_date = datetime(2025, 9, 1).date()
        
        if not end_date_str:
            end_date = start_date + timedelta(days=2)
        else:
            try:
                parsed_date = datetime.fromisoformat(end_date_str).date()
                end_date = parsed_date.replace(year=2025)
            except:
                end_date = start_date + timedelta(days=2)
        
        # 최소 1일, 최대 7일로 제한
        if end_date <= start_date:
            end_date = start_date + timedelta(days=1)
        
        days_diff = (end_date - start_date).days + 1
        if days_diff > 7:
            end_date = start_date + timedelta(days=6)
        
        date_range = []
        current_date = start_date
        while current_date <= end_date:
            date_range.append(current_date.isoformat())
            current_date += timedelta(days=1)
        
        return date_range
    
    def _calculate_optimal_route(self, regions: List[str]) -> List[str]:
        """최적 이동 경로 계산 (단순 정렬)."""
        return sorted(regions)
    
    def _calculate_duration_hours(self, start_time: str, end_time: str) -> int:
        """시작/종료 시간으로부터 지속 시간(시간) 계산."""
        try:
            start = datetime.strptime(start_time, "%H:%M")
            end = datetime.strptime(end_time, "%H:%M")
            duration = (end - start).total_seconds() / 3600
            return max(1, int(duration))
        except:
            return 8  # 기본 8시간
    
    
    def _generate_natural_language_itinerary_v2(
        self,
        geo_optimization: Dict[str, Any],
        time_optimization: Dict[str, Any],
        personalization_result: Dict[str, Any],
        user_query: str,
        slots: dict,
        selected_jobs: List = None,
        selected_tours: List = None
    ) -> str:
        """AI_AGENT_GUIDE.md 요구사항에 따른 표준화된 일정 생성."""
        
        try:
            from openai import OpenAI
            from app.config import get_settings
            import re
            from datetime import datetime, timedelta
            
            settings = get_settings()
            client = OpenAI(api_key=settings.openai_api_key)
            
            # 실제 선택된 농가와 관광지 데이터 가져오기 (DB에서 직접)
            farm_activities = []
            tour_activities = []
            
            # 선택된 농가들의 상세 정보 수집
            if selected_jobs:
                for job in selected_jobs:
                    farm_data = {
                        "id": f"job_{job.id}",
                        "title": job.title,
                        "work_date": getattr(job, 'work_date', ''),
                        "work_hours": getattr(job, 'work_hours', ''),
                        "region": job.region,
                        "address": getattr(job, 'address', ''),
                        "crop_type": getattr(job, 'crop_type', ''),
                        "image_url": getattr(job, 'image_url', ''),
                        "type": "job"
                    }
                    farm_activities.append(farm_data)
            
            # 선택된 관광지들의 상세 정보 수집  
            if selected_tours:
                for tour in selected_tours:
                    tour_data = {
                        "id": f"tour_{tour.id}",
                        "name": tour.name,
                        "region": tour.region,
                        "address": getattr(tour, 'addr1', ''),
                        "first_image": getattr(tour, 'first_image', ''),
                        "image_url": getattr(tour, 'first_image', ''),
                        "type": "tour"
                    }
                    tour_activities.append(tour_data)
            
            # 데이터가 없을 경우 fallback 메커니즘
            if not farm_activities and not tour_activities:
                # 기존 geo_optimization 데이터 사용 (backward compatibility)
                locations_data = geo_optimization.get("locations_data", {})
                locations = locations_data.get("locations", [])
                farm_activities = [loc for loc in locations if loc.get("type") == "job"]
                tour_activities = [loc for loc in locations if loc.get("type") == "tour"]
            
            # 지역 정보 추출 및 정규화
            try:
                main_region = self._extract_main_region(farm_activities, tour_activities)
            except Exception as e:
                print(f"⚠️ 지역 정보 추출 실패: {e}, 기본값 사용")
                main_region = "농촌"
            
            # 슬롯 추출 결과에서 정확한 기간 계산 (우선순위 1)
            duration_days = self._calculate_days_from_slots(slots)
            
            # 농가 데이터 기반 필요 기간 계산 (참고용)
            farm_required_days = self._calculate_total_duration_from_farms(farm_activities)
            
            # 사용자 요청 기간 확인 (백업용)
            user_requested_days = self._extract_duration_from_query(user_query, slots)
            
            # 슬롯 기간이 유효하지 않은 경우만 다른 방법 사용
            if duration_days <= 0:
                duration_days = max(user_requested_days, farm_required_days)
            
            print(f"🔍 기간 계산 결과:")
            print(f"   - 슬롯 기반 기간: {duration_days}일")
            print(f"   - 사용자 요청 기간: {user_requested_days}일") 
            print(f"   - 농가 필요 기간: {farm_required_days}일")
            
            # 농가 데이터에서 실제 work_date와 work_hours 정보 추출
            farm_schedule_info = self._extract_farm_schedule_info(farm_activities)
            
            print(f"🔧 표준화 일정 생성: {main_region}, {duration_days}일 여행")
            print(f"   농가 활동: {len(farm_activities)}개, 관광지: {len(tour_activities)}개")
            print(f"   농가 일정 정보: {farm_schedule_info}")

            system_prompt = f"""농촌 일정을 정확한 형식으로 생성하세요.

**절대 준수할 출력 형식:**

🚘 {main_region} {duration_days}일 여행 계획

🗓️ Day 1 (09/05) 도착
![IMAGE_URL]
- 서울 출발
- 숙소 체크인
   - 주소: [실제 농가 주소]

🗓️ Day 2 (09/06) [농가 작업명]
![IMAGE_URL]
- [실제 work_hours] [농가 작업명]
   - 주소: [실제 농가 주소]

🗓️ Day 3 (09/07) [농가 작업명] 
![IMAGE_URL]
- [실제 work_hours] [농가 작업명]
   - 주소: [실제 농가 주소]

🗓️ Day 4 (09/08) [농가 작업명]
![IMAGE_URL]
- [실제 work_hours] [농가 작업명]
   - 주소: [실제 농가 주소]

🗓️ Day 5 (09/09) 지역 관광
![IMAGE_URL]
- [관광지명1]
- [관광지명2]

**절대 금지사항:**
- 불필요한 설명 추가 금지
- 관광일정에 시간 표기 금지
- 농가 일정만 정확한 work_hours 표기
- 추가 텍스트나 해설 금지
- 형식 변경 금지
- 연속된 일정(Day 2~4) 표기 금지
- "중식 제공" 등 식사 관련 내용 추가 금지

**필수사항:**
- 정확히 {duration_days}일 일정만 생성 (Day 1부터 Day {duration_days}까지만)
- 각 날짜마다 개별적으로 Day 1, Day 2, Day 3... 형식으로 표기
- 농가 work_date, work_hours 정확히 사용
- 관광지는 시간 없이 장소명만
- 각 Day마다 ![IMAGE_URL] 포함
- 일정 총 기간은 반드시 {duration_days}일과 일치"""

            user_prompt = f"""사용자의 실제 여행 요청을 바탕으로 맞춤형 일정을 생성하세요:

**🗣️ 사용자 요청:**
"{user_query}"

**📊 선택된 농가 정보:**
{self._format_farm_data_for_prompt(farm_activities)}

**🏛️ 선택된 관광지 정보:**
{self._format_tour_data_for_prompt(tour_activities)}

**📋 기본 정보:**
- 주요 지역: {main_region}
- 여행 기간: {duration_days}일
- 농가 일정 상세: {farm_schedule_info}

**🎯 생성 지침:**
1. 반드시 {duration_days}일 일정으로 생성 (Day 1~Day {duration_days})
2. 사용자 요청을 최우선으로 고려 (교통수단, 선호사항, 특별요청 등)
3. 농가 work_date와 work_hours를 정확히 일정에 반영
4. 농가 일정 → 관광 일정 순서로 자연스럽게 배치
5. 지역 특성과 현실적 이동시간 고려
6. 구조적 형식은 유지하되 내용은 완전히 맞춤형으로

**⚠️ 중요:** 일정의 총 기간은 정확히 {duration_days}일이어야 하며, 이보다 많거나 적게 생성하지 마세요."""

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # 일관성을 위해 낮은 온도
                max_tokens=2500
            )
            
            result = response.choices[0].message.content.strip()
            
            # 이미지 URL을 실제 농가/관광지 이미지로 교체
            result = self._inject_actual_images(result, farm_activities, tour_activities)
            
            return result
            
        except Exception as e:
            print(f"표준화 일정 생성 실패: {e}")
            return self._create_fallback_structured_itinerary(farm_activities, tour_activities, main_region, duration_days)
    
    def _structure_final_schedule(
        self,
        geo_optimization: Dict[str, Any],
        time_optimization: Dict[str, Any],
        personalization_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Agent 결과를 통합하여 최종 일정 구조 생성."""
        
        # 개인화 결과에서 일별 일정 추출
        personalized_schedule = personalization_result.get("personalized_schedule", {})
        
        return {
            "daily_schedule": personalized_schedule,
            "geo_optimization": geo_optimization,
            "time_optimization": time_optimization,
            "personalization": personalization_result,
            "metadata": {
                "geographical_efficiency": geo_optimization.get("travel_efficiency", "medium"),
                "temporal_efficiency": time_optimization.get("time_efficiency", "good"),
                "personalization_level": personalization_result.get("activity_density", "medium")
            }
        }
    
    def _create_legacy_itineraries_v2(self, final_schedule: Dict[str, Any]) -> List[Itinerary]:
        """Agent 결과 기반 레거시 JSON 일정 생성."""
        
        itineraries = []
        daily_schedule = final_schedule.get("daily_schedule", {})
        
        for i, (date, activities) in enumerate(daily_schedule.items(), 1):
            plan_items = []
            
            if isinstance(activities, list):
                for activity in activities:
                    if isinstance(activity, dict):
                        activity_type = activity.get("type", "unknown").upper()
                        name = activity.get("activity_name", activity.get("name", "활동"))
                        start_time = activity.get("start_time", "미정")
                        end_time = activity.get("end_time", "미정")
                        
                        plan_items.append(f"[{activity_type}] {name} ({start_time}~{end_time})")
            
            itinerary = Itinerary(
                day=i,
                date=date,
                plan_items=plan_items,
                total_distance_km=0.0,
                total_cost_krw=0
            )
            
            itineraries.append(itinerary)
        
        return itineraries
    
    def _extract_activities_from_agent_results(
        self,
        geo_optimization: Dict[str, Any],
        time_optimization: Dict[str, Any],
        personalization_result: Dict[str, Any]
    ) -> tuple:
        """Agent 결과에서 활동 목록 추출."""
        
        # Agent 결과 구조 분석 (실제 구현에서는 복잡한 로직이 필요할 수 있음)
        locations_data = geo_optimization.get("locations_data", {})
        locations = locations_data.get("locations", [])
        
        selected_jobs = []
        selected_tours = []
        
        # 위치 데이터에서 원본 활동 정보 재구성 (제한적 구현)
        for location in locations:
            location_type = location.get("type", "")
            if location_type == "job":
                # JobPost 유사 객체 생성 (실제로는 DB에서 조회해야 함)
                job_data = type('JobPost', (), {
                    'id': location.get("id", "").replace("job_", ""),
                    'title': location.get("name", ""),
                    'region': location.get("region", ""),
                    'start_time': location.get("working_hours", {}).get("start", "09:00"),
                    'end_time': location.get("working_hours", {}).get("end", "17:00"),
                    'tags': ",".join(location.get("tags", []))
                })()
                selected_jobs.append(job_data)
            elif location_type == "tour":
                # TourSpot 유사 객체 생성
                tour_data = type('TourSpot', (), {
                    'id': location.get("id", "").replace("tour_", ""),
                    'name': location.get("name", ""),
                    'region': location.get("region", ""),
                    'tags': ",".join(location.get("tags", []))
                })()
                selected_tours.append(tour_data)
        
        return selected_jobs, selected_tours
    
    def _create_simple_itinerary_text_v2(
        self,
        geo_optimization: Dict[str, Any],
        time_optimization: Dict[str, Any],
        personalization_result: Dict[str, Any]
    ) -> str:
        """Agent 결과 기반 간단한 일정 텍스트 생성."""
        
        itinerary = "# 농촌 일여행 일정\n\n"
        
        # 개인화 결과에서 일정 추출
        personalized_schedule = personalization_result.get("personalized_schedule", {})
        activity_style = personalization_result.get("activity_profile", {}).get("activity_style", "balanced")
        
        itinerary += f"**개인화 스타일**: {activity_style} 타입\n"
        itinerary += f"**지리적 효율성**: {geo_optimization.get('travel_efficiency', 'medium')}\n"
        itinerary += f"**시간적 효율성**: {time_optimization.get('time_efficiency', 'good')}\n\n"
        
        for i, (date, activities) in enumerate(personalized_schedule.items(), 1):
            itinerary += f"## {i}일차 ({date})\n\n"
            
            if not activities:
                itinerary += "- 휴식 및 자유 시간\n\n"
                continue
            
            for activity in activities:
                if isinstance(activity, dict):
                    activity_type = "농가 체험" if activity.get("type") == "job" else "관광지 탐방"
                    name = activity.get("activity_name", activity.get("name", "활동"))
                    start_time = activity.get("start_time", "미정")
                    end_time = activity.get("end_time", "미정")
                    notes = activity.get("personalization_notes", "")
                    
                    itinerary += f"- **{start_time} - {end_time}**: {activity_type} - {name}\n"
                    if notes:
                        itinerary += f"  - 💡 {notes}\n"
            
            itinerary += "\n"
        
        itinerary += "## 💡 여행 팁\n\n"
        itinerary += "- 농촌 일거리는 날씨에 영향을 받을 수 있으니 준비하세요\n"
        itinerary += "- 편안한 복장과 작업용 장갑을 준비하시면 좋습니다\n"
        itinerary += f"- {activity_style} 성향에 맞춘 일정으로 구성되었습니다\n\n"
        
        return itinerary
    
    def _create_simple_itinerary_text(self, personalized_schedule: Dict[str, Any]) -> str:
        """간단한 일정 텍스트 생성 (GPT 폴백용)."""
        
        itinerary = "# 농촌 일여행 일정\n\n"
        
        daily_schedule = personalized_schedule.get("daily_schedule", {})
        
        for i, (date, activities) in enumerate(daily_schedule.items(), 1):
            itinerary += f"## {i}일차 ({date})\n\n"
            
            if not activities:
                itinerary += "- 휴식 및 자유 시간\n\n"
                continue
            
            for activity in activities:
                activity_type = "농가 체험" if activity["type"] == "job" else "관광지 탐방"
                name = activity.get("name", "활동")
                start_time = activity.get("start_time", "미정")
                end_time = activity.get("end_time", "미정")
                
                itinerary += f"- **{start_time} - {end_time}**: {activity_type} - {name}\n"
            
            itinerary += "\n"
        
        itinerary += "## 💡 여행 팁\n\n"
        itinerary += "- 농촌 일거리는 날씨에 영향을 받을 수 있으니 준비하세요\n"
        itinerary += "- 편안한 복장과 작업용 장갑을 준비하시면 좋습니다\n\n"
        
        return itinerary
    
    # ====== 피드백 시스템 헬퍼 메서드들 ======
    
    def _apply_feedback_modifications(
        self,
        original_schedule: Dict[str, Any],
        modifications: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        사용자 수정사항을 기존 일정에 적용합니다.
        
        Args:
            original_schedule: 원본 일정
            modifications: 수정사항 리스트
            
        Returns:
            수정된 일정
        """
        
        print(f"🔧 일정 수정사항 적용: {len(modifications)}개")
        
        modified_schedule = copy.deepcopy(original_schedule)
        
        for modification in modifications:
            mod_type = modification.get("type")
            
            if mod_type == "remove_activity":
                self._remove_activity(modified_schedule, modification)
            elif mod_type == "change_time":
                self._change_activity_time(modified_schedule, modification)
            elif mod_type == "replace_activity":
                self._replace_activity(modified_schedule, modification)
            elif mod_type == "add_activity":
                self._add_activity(modified_schedule, modification)
            elif mod_type == "reorder_activities":
                self._reorder_activities(modified_schedule, modification)
        
        print(f"✅ 일정 수정 적용 완료")
        return modified_schedule
    
    def _remove_activity(self, schedule: Dict[str, Any], modification: Dict[str, Any]):
        """특정 활동을 일정에서 제거합니다."""
        target_date = modification.get("date")
        activity_id = modification.get("activity_id")
        
        daily_schedule = schedule.get("daily_schedule", {})
        
        if target_date in daily_schedule:
            daily_schedule[target_date] = [
                activity for activity in daily_schedule[target_date]
                if activity.get("id") != activity_id
            ]
    
    def _change_activity_time(self, schedule: Dict[str, Any], modification: Dict[str, Any]):
        """활동 시간을 변경합니다."""
        target_date = modification.get("date")
        activity_id = modification.get("activity_id")
        new_start_time = modification.get("new_start_time")
        new_end_time = modification.get("new_end_time")
        
        daily_schedule = schedule.get("daily_schedule", {})
        
        if target_date in daily_schedule:
            for activity in daily_schedule[target_date]:
                if activity.get("id") == activity_id:
                    if new_start_time:
                        activity["start_time"] = new_start_time
                    if new_end_time:
                        activity["end_time"] = new_end_time
    
    def _replace_activity(self, schedule: Dict[str, Any], modification: Dict[str, Any]):
        """활동을 다른 활동으로 교체합니다."""
        target_date = modification.get("date")
        old_activity_id = modification.get("old_activity_id")
        new_activity = modification.get("new_activity")
        
        daily_schedule = schedule.get("daily_schedule", {})
        
        if target_date in daily_schedule:
            for i, activity in enumerate(daily_schedule[target_date]):
                if activity.get("id") == old_activity_id:
                    daily_schedule[target_date][i] = new_activity
                    break
    
    def _add_activity(self, schedule: Dict[str, Any], modification: Dict[str, Any]):
        """새로운 활동을 일정에 추가합니다."""
        target_date = modification.get("date")
        new_activity = modification.get("activity")
        insert_index = modification.get("insert_index", -1)
        
        daily_schedule = schedule.get("daily_schedule", {})
        
        if target_date not in daily_schedule:
            daily_schedule[target_date] = []
        
        if insert_index == -1:
            daily_schedule[target_date].append(new_activity)
        else:
            daily_schedule[target_date].insert(insert_index, new_activity)
    
    def _reorder_activities(self, schedule: Dict[str, Any], modification: Dict[str, Any]):
        """활동 순서를 변경합니다."""
        target_date = modification.get("date")
        new_order = modification.get("new_order")
        
        daily_schedule = schedule.get("daily_schedule", {})
        
        if target_date in daily_schedule and new_order:
            activities = daily_schedule[target_date]
            reordered_activities = []
            
            for activity_id in new_order:
                for activity in activities:
                    if activity.get("id") == activity_id:
                        reordered_activities.append(activity)
                        break
            
            daily_schedule[target_date] = reordered_activities
    
    def _summarize_optimization_changes(
        self,
        original_schedule: Dict[str, Any],
        optimization_result: Dict[str, Any]
    ) -> List[str]:
        """
        원본 일정과 최적화 결과를 비교하여 변경사항을 요약합니다.
        
        Args:
            original_schedule: 원본 일정
            optimization_result: 최적화 결과
            
        Returns:
            변경사항 요약 리스트
        """
        
        changes = []
        
        # 최적화 수준 변화
        original_efficiency = original_schedule.get("metadata", {}).get("geographical_efficiency", "medium")
        new_efficiency = optimization_result.get("activity_profile", {}).get("activity_style", "balanced")
        
        if original_efficiency != new_efficiency:
            changes.append(f"개인화 스타일이 {new_efficiency}로 조정되었습니다")
        
        # 활동 밀도 변화
        activity_density = optimization_result.get("activity_density", "medium")
        changes.append(f"활동 밀도: {activity_density} 레벨로 최적화")
        
        # 개인화 요소들
        personalization_factors = optimization_result.get("personalization_factors", [])
        if personalization_factors:
            changes.append(f"적용된 개인화 요소: {', '.join(personalization_factors[:3])}")
        
        # 기본 메시지
        if not changes:
            changes.append("사용자 피드백을 반영하여 일정이 재최적화되었습니다")
        
        return changes
    
    def _extract_main_region(self, farm_activities: List[dict], tour_activities: List[dict]) -> str:
        """농가와 관광지 데이터에서 주요 지역 추출 및 정규화."""
        regions = []
        
        # 농가 데이터에서 지역 추출 (우선순위)
        for farm in farm_activities:
            region = farm.get("region", "")
            if region:
                regions.append(region)
        
        # 관광지 데이터에서 지역 추출
        for tour in tour_activities:
            region = tour.get("region", "")
            if region:
                regions.append(region)
        
        if not regions:
            return "농촌"
        
        # 가장 빈번한 지역 찾기
        region_counts = {}
        for region in regions:
            region_counts[region] = region_counts.get(region, 0) + 1
        
        main_region = max(region_counts, key=region_counts.get)
        
        # 지역명 정규화
        if "김제" in main_region:
            return "전북 김제"
        elif "청양" in main_region:
            return "충남 청양"
        elif "괴산" in main_region:
            return "충북 괴산"
        elif "전북" in main_region or "전라북도" in main_region:
            return "전북"
        elif "충남" in main_region or "충청남도" in main_region:
            return "충남"
        elif "충북" in main_region or "충청북도" in main_region:
            return "충북"
        else:
            return main_region
    
    def _extract_duration_from_query(self, user_query: str, slots: dict) -> int:
        """사용자 쿼리와 슬롯에서 여행 기간 추출."""
        import re
        
        # 슬롯에서 기간 정보 확인
        duration = slots.get("duration")
        if duration and isinstance(duration, (int, str)):
            if isinstance(duration, str):
                duration_match = re.search(r'(\d+)', duration)
                if duration_match:
                    return int(duration_match.group(1))
            else:
                return int(duration)
        
        # 자연어에서 기간 추출
        query_lower = user_query.lower()
        
        # 패턴들 확인
        patterns = [
            r'(\d+)일',
            r'(\d+)박\s*(\d+)일',
            r'(\d+)주',
            r'(\d+)\s*days?',
            r'(\d+)\s*week'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                if '주' in pattern or 'week' in pattern:
                    return int(match.group(1)) * 7
                elif '박' in pattern:
                    return int(match.group(2))  # 박수가 아닌 일수
                else:
                    return int(match.group(1))
        
        # 기본값: 7일
        return 7
    
    def _calculate_total_duration_from_farms(self, farm_activities: List[dict]) -> int:
        """농가 데이터의 work_date를 분석하여 전체 필요 기간 계산."""
        if not farm_activities:
            return 7  # 기본값
        
        from datetime import datetime, timedelta
        import re
        
        total_days = set()
        
        for farm in farm_activities:
            work_date = farm.get('work_date', '')
            if '~' in work_date:
                # "2024-09-06~2024-09-10" 형태 처리
                try:
                    start_str, end_str = work_date.split('~')
                    start_date = datetime.strptime(start_str.strip(), '%Y-%m-%d')
                    end_date = datetime.strptime(end_str.strip(), '%Y-%m-%d')
                    
                    # 해당 기간의 모든 날짜 추가
                    current_date = start_date
                    while current_date <= end_date:
                        total_days.add(current_date.date())
                        current_date += timedelta(days=1)
                except:
                    continue
            elif work_date:
                # 단일 날짜 처리
                try:
                    date_obj = datetime.strptime(work_date.strip(), '%Y-%m-%d')
                    total_days.add(date_obj.date())
                except:
                    continue
        
        if total_days:
            # 농가 작업일 + 도착일/관광일 등 추가 고려
            farm_work_days = len(total_days)
            return max(farm_work_days + 2, 7)  # 최소 7일
        
        return 7  # 기본값
    
    def _extract_farm_schedule_info(self, farm_activities: List[dict]) -> dict:
        """농가 데이터에서 work_date와 work_hours 정보 추출."""
        schedule_info = {}
        
        for i, farm in enumerate(farm_activities):
            farm_id = farm.get("id", f"farm_{i}")
            
            # work_date 추출 (CSV에서 읽은 원본 데이터)
            work_date = farm.get("work_date", "")
            work_hours = farm.get("work_hours", "")
            
            if work_date and work_hours:
                schedule_info[farm_id] = {
                    "work_date": work_date,
                    "work_hours": work_hours,
                    "title": farm.get("title", farm.get("name", "")),
                    "address": farm.get("address", "")
                }
        
        return schedule_info
    
    def _format_farm_data_for_prompt(self, farm_activities: List[dict]) -> str:
        """농가 데이터를 AI 프롬프트용으로 포매팅."""
        if not farm_activities:
            return "농가 데이터 없음"
        
        formatted_data = []
        for i, farm in enumerate(farm_activities):
            farm_info = f"""농가 {i+1}:
- 제목: {farm.get('title', farm.get('name', 'Unknown'))}
- 작업기간: {farm.get('work_date', 'N/A')}
- 근무시간: {farm.get('work_hours', 'N/A')}
- 주소: {farm.get('address', 'N/A')}
- 작물: {farm.get('crop_type', 'N/A')}
- 이미지: {farm.get('image_url', 'N/A')}"""
            formatted_data.append(farm_info)
        
        return "\n\n".join(formatted_data)
    
    def _format_tour_data_for_prompt(self, tour_activities: List[dict]) -> str:
        """관광지 데이터를 AI 프롬프트용으로 포매팅."""
        if not tour_activities:
            return "관광지 데이터 없음"
        
        formatted_data = []
        for i, tour in enumerate(tour_activities):
            tour_info = f"""관광지 {i+1}:
- 이름: {tour.get('name', tour.get('title', 'Unknown'))}
- 지역: {tour.get('region', 'N/A')}
- 주소: {tour.get('address', tour.get('addr1', 'N/A'))}
- 태그: {tour.get('tags', 'N/A')}
- 이미지: {tour.get('first_image', tour.get('image_url', 'N/A'))}"""
            formatted_data.append(tour_info)
        
        return "\n\n".join(formatted_data)
    
    def _inject_actual_images(self, itinerary_text: str, farm_activities: List[dict], tour_activities: List[dict]) -> str:
        """일정 텍스트의 ![IMAGE_URL] 플레이스홀더를 실제 이미지로 교체."""
        import re
        
        # 모든 이미지 URL 수집
        image_urls = []
        
        # 농가 이미지 추가
        for farm in farm_activities:
            image_url = farm.get('image_url', '')
            if image_url:
                image_urls.append(image_url)
        
        # 관광지 이미지 추가
        for tour in tour_activities:
            image_url = tour.get('first_image', tour.get('image_url', ''))
            if image_url:
                image_urls.append(image_url)
        
        # 기본 이미지 (부족할 경우)
        default_images = [
            "https://images.unsplash.com/photo-1560807707-8cc77767d783?w=400",
            "https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400",
            "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=400"
        ]
        
        # 이미지가 부족하면 기본 이미지 추가
        while len(image_urls) < 10:  # 최대 10일 여행 가정
            image_urls.extend(default_images)
        
        # ![IMAGE_URL] 패턴을 실제 이미지로 교체
        image_pattern = r'!\[IMAGE_URL\]'
        image_index = 0
        
        def replace_image(match):
            nonlocal image_index
            if image_index < len(image_urls):
                url = image_urls[image_index]
                image_index += 1
                return f"![travel_image]({url})"
            return "![travel_image](https://images.unsplash.com/photo-1560807707-8cc77767d783?w=400)"
        
        return re.sub(image_pattern, replace_image, itinerary_text)
    
    def _create_fallback_structured_itinerary(self, farm_activities: List[dict], tour_activities: List[dict], 
                                            main_region: str, duration_days: int) -> str:
        """AI 생성 실패시 사용할 백업 일정 생성."""
        
        # 기본 구조화 일정 생성
        itinerary_parts = [f"🚘 {main_region} {duration_days}일 여행 계획\n"]
        
        # Day 1: 도착
        itinerary_parts.append("🗓️ Day 1 (09/05) 도착")
        if farm_activities:
            first_farm = farm_activities[0]
            itinerary_parts.append(f"![travel_image](https://images.unsplash.com/photo-1560807707-8cc77767d783?w=400)")
            itinerary_parts.append("- 서울역 출발")
            itinerary_parts.append("- 현지 도착 및 이동") 
            itinerary_parts.append("- 숙소 체크인")
            if first_farm.get('address'):
                itinerary_parts.append(f"   - 주소: {first_farm['address']}")
            itinerary_parts.append("")
        
        # 농가 일정 배치 (Day 2부터)
        day_counter = 2
        for farm in farm_activities[:2]:  # 최대 2개 농가
            work_date = farm.get('work_date', '')
            work_hours = farm.get('work_hours', '09:00-17:00')
            title = farm.get('title', farm.get('name', '농가 체험'))
            
            if '~' in work_date:
                # 연속 기간 처리
                start_day = day_counter
                end_day = min(day_counter + 2, duration_days - 1)  # 최대 3일
                itinerary_parts.append(f"🗓️ Day {start_day}~{end_day} (09/0{start_day+3}~09/0{end_day+3}) {title}")
                day_counter = end_day + 1
            else:
                itinerary_parts.append(f"🗓️ Day {day_counter} (09/0{day_counter+3}) {title}")
                day_counter += 1
            
            image_url = farm.get('image_url', 'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=400')
            itinerary_parts.append(f"![travel_image]({image_url})")
            itinerary_parts.append(f"- {work_hours} 농장 작업")
            itinerary_parts.append("- 중식 제공")
            if farm.get('address'):
                itinerary_parts.append(f"   - 주소: {farm['address']}")
            itinerary_parts.append("")
        
        # 관광 일정 배치 (남은 날짜들)
        tour_index = 0
        while day_counter <= duration_days:
            if day_counter == duration_days:
                # 마지막 날: 귀환
                itinerary_parts.append(f"🗓️ Day {duration_days} (09/0{duration_days+3}) 귀환")
                itinerary_parts.append("![travel_image](https://images.unsplash.com/photo-1544197150-b99a580bb7a8?w=400)")
                itinerary_parts.append("- 마무리 및 정리")
                itinerary_parts.append("- 서울 복귀")
                break
            else:
                # 관광 일정
                itinerary_parts.append(f"🗓️ Day {day_counter} (09/0{day_counter+3}) 지역 관광")
                
                if tour_index < len(tour_activities):
                    tour = tour_activities[tour_index]
                    image_url = tour.get('first_image', tour.get('image_url', 'https://images.unsplash.com/photo-1560807707-8cc77767d783?w=400'))
                    itinerary_parts.append(f"![travel_image]({image_url})")
                    itinerary_parts.append(f"- {tour.get('name', '관광지 방문')}")
                    
                    if tour_index + 1 < len(tour_activities):
                        next_tour = tour_activities[tour_index + 1]
                        itinerary_parts.append(f"- {next_tour.get('name', '추가 관광지')}")
                    
                    tour_index += 2
                else:
                    itinerary_parts.append("![travel_image](https://images.unsplash.com/photo-1560807707-8cc77767d783?w=400)")
                    itinerary_parts.append("- 자유 시간")
                    itinerary_parts.append("- 지역 맛집 탐방")
                
                itinerary_parts.append("")
                
            day_counter += 1
        
        return "\n".join(itinerary_parts)
    
    def reoptimize_itinerary(
        self,
        session_id: str,
        modifications: List[Dict[str, Any]],
        user_preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """일정 피드백을 반영한 실시간 재최적화."""
        
        start_time = time.time()
        
        try:
            print(f"일정 재최적화 시작 (Session: {session_id[:8]})")
            
            # 1) 세션 데이터 조회 확인
            if session_id not in self.session_cache:
                print(f"⚠️ 세션 데이터를 찾을 수 없습니다: {session_id}")
                # 기본 응답 반환
                return {
                    "natural_language_itinerary": "세션 데이터가 없어 재최적화를 수행할 수 없습니다.",
                    "changes_summary": ["세션 만료 또는 데이터 없음"],
                    "execution_time": time.time() - start_time
                }
            
            cached_data = self.session_cache[session_id]
            
            # 2) 자연어 피드백 처리
            feedback_text = ""
            for modification in modifications:
                if modification.get("type") == "natural_language_feedback":
                    feedback_text = modification.get("feedback", "")
                    break
            
            if not feedback_text:
                return {
                    "natural_language_itinerary": "피드백 내용이 없습니다.",
                    "changes_summary": [],
                    "execution_time": time.time() - start_time
                }
            
            # 3) GPT를 활용한 피드백 기반 일정 재생성
            from openai import OpenAI
            from app.config import get_settings
            settings = get_settings()
            client = OpenAI(api_key=settings.openai_api_key)
            
            original_itinerary = cached_data.get("natural_language_itinerary", "")
            
            system_prompt = """당신은 여행 일정 수정 전문가입니다.
            
사용자의 피드백을 반영하여 기존 일정을 개선해 주세요.

**수정 원칙:**
1. 기존 일정의 기본 구조와 형식은 유지
2. 사용자 피드백 내용을 정확히 반영
3. 실현 가능한 범위에서 수정
4. 각 Day마다 ![IMAGE_URL] 포함
5. "중식 제공" 등 식사 관련 내용 제외

**기존 일정을 참고하여 사용자 요청에 맞게 수정해주세요.**"""
            
            user_prompt = f"""**기존 일정:**
{original_itinerary}

**사용자 피드백:**
{feedback_text}

위 피드백을 반영하여 일정을 수정해 주세요."""
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            updated_itinerary = response.choices[0].message.content.strip()
            
            # 4) 세션 캐시 업데이트
            self.session_cache[session_id]["natural_language_itinerary"] = updated_itinerary
            
            execution_time = time.time() - start_time
            
            return {
                "natural_language_itinerary": updated_itinerary,
                "changes_summary": [f"사용자 피드백 반영: {feedback_text}"],
                "execution_time": execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            print(f"⚠️ 일정 재최적화 실패: {e}")
            
            return {
                "natural_language_itinerary": f"재최적화 중 오류가 발생했습니다: {str(e)}",
                "changes_summary": [],
                "execution_time": execution_time,
                "error": str(e)
            }