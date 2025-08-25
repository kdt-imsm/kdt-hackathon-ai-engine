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
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.config import get_settings
from app.schemas import DetailedItineraryResponse, Itinerary
from app.db.models import JobPost, TourSpot

settings = get_settings()


class SmartSchedulingOrchestrator:
    """스마트 스케줄링 전용 오케스트레이터."""
    
    def __init__(self, db_session: Session = None):
        self.db_session = db_session
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
            
            # IntelligentPlannerAgent 초기화
            from app.agents.intelligent_planner_agent import IntelligentPlannerAgent
            planner_agent = IntelligentPlannerAgent()
            
            # Agent 기반 최적화 시도 (실패 시 즉시 fallback으로 이동)
            try:
                # 1단계: 지리적 최적화 분석 (GPT-4o Agent)
                geo_optimization = planner_agent.analyze_geographical_optimization(
                    selected_jobs, selected_tours, user_preferences or {}
                )
                
                # 2단계: 시간적 최적화 분석 (GPT-4o Agent) 
                time_optimization = planner_agent.analyze_temporal_optimization(
                    selected_jobs, selected_tours, slots, geo_optimization
                )
                
                # 3단계: 개인화 맞춤 배치 (GPT-4o Agent)
                personalization_result = planner_agent.create_personalized_arrangement(
                    geo_optimization, time_optimization, user_preferences or {}, slots
                )
                
                # Agent 실행 로그 확인
                logs = planner_agent.get_execution_logs()
                agent_failures = [log for log in logs if not log.get("success", True)]
                
                if agent_failures:
                    print(f"💡 GPT-4o Agent 일부 실패, fallback 사용")
                    print(f"   실패한 Agent 단계: {[log['function'] for log in agent_failures]}")
                    raise Exception("Agent 실패로 인한 fallback 사용")
                
                print(f"GPT-4o Agent 최적화 완료")
                    
            except Exception as e:
                print(f"💡 선택된 카드를 활용한 맞춤형 일정 생성 중... (사유: {str(e)[:50]})")
                # fallback으로 이동
                return self._create_fallback_itinerary(
                    selected_jobs, selected_tours, slots, user_query
                )
            
            # 4단계: GPT-4o 기반 자연어 일정 생성
            natural_language_itinerary = self._generate_natural_language_itinerary_v2(
                geo_optimization,
                time_optimization,
                personalization_result,
                user_query,
                slots
            )
            
            # 5단계: 결과 구조화 및 캐싱
            execution_time = time.time() - start_time
            
            # 최종 일정 데이터 구조화
            final_schedule = self._structure_final_schedule(
                geo_optimization,
                time_optimization,
                personalization_result
            )
            
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
            
            # 폴백: 기존 방식 사용
            return self._create_fallback_itinerary(
                selected_jobs, selected_tours, slots, user_query
            )
    
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
            success=True
        )
    
    def _create_natural_language_itinerary_from_cards(
        self,
        selected_jobs: List[JobPost],
        selected_tours: List[TourSpot],
        date_range: List[str],
        user_query: str
    ) -> str:
        """선택된 카드들을 기반으로 자연어 일정 생성."""
        
        itinerary = f"# 선택하신 카드 기반 농촌 일여행 일정\n\n"
        itinerary += f"**사용자 요청**: {user_query}\n"
        itinerary += f"**여행 기간**: {len(date_range)}일\n"
        itinerary += f"**선택된 농촌 일거리**: {len(selected_jobs)}개\n"
        itinerary += f"**선택된 관광지**: {len(selected_tours)}개\n\n"
        
        day_count = 1
        
        # 각 선택된 일거리를 개별 일차로 배치
        for job in selected_jobs:
            date = date_range[day_count-1] if day_count-1 < len(date_range) else date_range[0]
            job_title = getattr(job, 'title', '농촌 일거리')
            job_region = getattr(job, 'region', '지역미상')
            job_start_time = getattr(job, 'start_time', '08:00')
            job_end_time = getattr(job, 'end_time', '17:00')
            
            itinerary += f"## 📅 Day {day_count} ({date}) - 농촌 일거리 체험\n\n"
            itinerary += f"### 🌾 {job_title}\n"
            itinerary += f"**⏰ 시간**: {job_start_time} ~ {job_end_time}\n"
            itinerary += f"**📍 위치**: {job_region}\n"
            itinerary += f"**활동 내용**:\n"
            itinerary += f"- 농촌 일거리 체험을 통한 농업 현장 경험\n"
            itinerary += f"- 지역 농민과의 소통 및 농업 기술 학습\n"
            itinerary += f"- 계절에 맞는 농작업 참여\n\n"
            
            # 점심 시간 추가
            itinerary += f"### 🍽️ 점심 식사 (12:00 ~ 13:00)\n"
            itinerary += f"**📍 위치**: {job_region} 인근 로컬 식당\n"
            itinerary += f"**🍲 추천 메뉴**: 지역 특색 음식 및 농가 정식\n\n"
            
            day_count += 1
        
        # 각 선택된 관광지를 개별 일차로 배치  
        for tour in selected_tours:
            date = date_range[day_count-1] if day_count-1 < len(date_range) else date_range[0]
            tour_title = getattr(tour, 'title', getattr(tour, 'name', '관광지'))
            tour_region = getattr(tour, 'region', '지역미상')
            
            itinerary += f"## 📅 Day {day_count} ({date}) - 관광지 체험\n\n"
            itinerary += f"### 🏞️ {tour_title}\n"
            itinerary += f"**⏰ 시간**: 09:00 ~ 17:00\n"
            itinerary += f"**📍 위치**: {tour_region}\n"
            itinerary += f"**활동 내용**:\n"
            itinerary += f"- 지역 문화유산 및 자연경관 탐방\n"
            itinerary += f"- 역사적 의미와 문화적 가치 학습\n"
            itinerary += f"- 사진 촬영 및 기념품 구매\n\n"
            
            # 점심 시간 추가
            itinerary += f"### 🍽️ 점심 식사 (12:00 ~ 13:00)\n"
            itinerary += f"**📍 위치**: {tour_region} 인근 관광지 맛집\n"
            itinerary += f"**🍲 추천 메뉴**: 지역 특산물 요리\n\n"
            
            day_count += 1
        
        # 선택된 카드가 없는 경우
        if not selected_jobs and not selected_tours:
            itinerary += "## 안내사항\n\n"
            itinerary += "선택된 농촌 일거리나 관광지가 없습니다.\n"
            itinerary += "카드를 선택한 후 다시 일정 생성을 요청해 주세요.\n\n"
        
        # 여행 팁 추가
        itinerary += "---\n\n"
        itinerary += "## 💡 여행 팁\n\n"
        itinerary += "- **복장**: 편안한 작업복과 운동화, 작업용 장갑 준비\n"
        itinerary += "- **날씨**: 농촌 일거리는 날씨의 영향을 받을 수 있으니 사전 확인\n"
        itinerary += "- **교통**: 대중교통보다는 자차 이용을 권장\n"
        itinerary += "- **예산**: 지역 특산물 구매 예산을 별도 준비\n"
        itinerary += "- **연락처**: 각 농장/관광지의 운영시간 및 예약 여부 사전 확인 필요\n\n"
        itinerary += "**📞 문의사항이 있으시면 각 농장 및 관광지에 직접 연락 부탁드립니다.**\n\n"
        
        return itinerary
    
    # ====== 유틸리티 메서드들 ======
    
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
        slots: dict
    ) -> str:
        """Agent 결과를 활용한 자연어 일정 생성."""
        
        try:
            # 기존 itinerary_generator 사용하되, Agent 결과 반영
            from app.nlp.itinerary_generator import generate_detailed_itinerary
            
            # Agent 결과를 바탕으로 활동 목록 재구성
            selected_jobs, selected_tours = self._extract_activities_from_agent_results(
                geo_optimization, time_optimization, personalization_result
            )
            
            result = generate_detailed_itinerary(
                slots=slots,
                selected_jobs=selected_jobs,
                selected_tours=selected_tours,
                user_query=user_query
            )
            
            return result.get("natural_language_itinerary", "일정 생성 실패")
            
        except Exception as e:
            print(f"자연어 일정 생성 실패: {e}")
            return self._create_simple_itinerary_text_v2(geo_optimization, time_optimization, personalization_result)
    
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