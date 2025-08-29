"""
Intelligent Planner Agent - 지능형 일정 배치 전문 AI Agent

선택된 농가/관광지 카드를 기반으로 최적 일정 배치를 수행하는 GPT-4o 기반 AI Agent입니다.
지리적, 시간적, 개인화 최적화를 통해 사용자 맞춤형 일정을 생성합니다.

주요 기능:
- 지리적 최적화: 선택된 장소들의 위치 관계 분석 및 최단거리 동선 생성
- 시간적 최적화: 운영시간, 체험 소요시간, 이동시간을 고려한 시간표 생성
- 개인화 맞춤: 사용자 성향에 따른 일정 스타일 조정
- 논리적 흐름: 자연스러운 활동 순서 구성
"""

import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from openai import OpenAI

from app.config import get_settings
from app.db.models import JobPost, TourSpot

settings = get_settings()


class IntelligentPlannerAgent:
    """지능형 일정 배치 전문 AI Agent."""
    
    def __init__(self, db_session=None):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o"  # 복합적 조건 분석을 위한 최상위 모델
        self.execution_logs = []
        
        # 데이터베이스 세션 초기화
        if db_session is None:
            from app.db.database import SessionLocal
            self.db_session = SessionLocal()
            self._should_close_session = True
        else:
            self.db_session = db_session
            self._should_close_session = False
    
    def analyze_geographical_optimization(
        self,
        selected_jobs: List[JobPost],
        selected_tours: List[TourSpot],
        user_preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        지리적 최적화 분석.
        선택된 장소들의 위치 관계를 분석하여 최단거리 동선으로 일정 배치.
        
        Args:
            selected_jobs: 선택된 농가 카드
            selected_tours: 선택된 관광지 카드
            user_preferences: 사용자 선호도
            
        Returns:
            지리적 최적화 결과
        """
        
        start_time = time.time()
        
        try:
            print(f"지리적 최적화 분석 시작")
            
            # 장소 정보 수집
            locations_data = self._collect_location_data(selected_jobs, selected_tours)
            
            # GPT-4o를 활용한 지리적 최적화
            optimization_result = self._generate_geographical_optimization(
                locations_data, user_preferences
            )
            
            execution_time = time.time() - start_time
            
            result = {
                "success": True,
                "locations_data": locations_data,
                "optimal_route": optimization_result.get("optimal_route", []),
                "region_clusters": optimization_result.get("region_clusters", {}),
                "travel_efficiency": optimization_result.get("travel_efficiency", "high"),
                "execution_time": execution_time,
                "agent_notes": optimization_result.get("notes", "")
            }
            
            self.execution_logs.append({
                "agent": "IntelligentPlannerAgent",
                "function": "analyze_geographical_optimization",
                "execution_time": execution_time,
                "success": True,
                "input_size": len(selected_jobs) + len(selected_tours)
            })
            
            print(f"   지리적 최적화 완료 (실행시간: {execution_time:.2f}초)")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            self.execution_logs.append({
                "agent": "IntelligentPlannerAgent",
                "function": "analyze_geographical_optimization",
                "execution_time": execution_time,
                "success": False,
                "error": str(e)
            })
            
            print(f"   → 지리적 최적화: 기본 방식 사용")
            
            # 폴백: 기본 지역 그룹화
            return self._create_basic_geographical_optimization(selected_jobs, selected_tours)
    
    def analyze_temporal_optimization(
        self,
        selected_jobs: List[JobPost],
        selected_tours: List[TourSpot],
        slots: Dict[str, Any],
        geographical_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        시간적 최적화 분석.
        각 장소의 운영시간, 체험 소요시간, 이동시간을 고려한 시간표 생성.
        
        Args:
            selected_jobs: 선택된 농가 카드
            selected_tours: 선택된 관광지 카드
            slots: 슬롯 추출 결과
            geographical_result: 지리적 최적화 결과
            
        Returns:
            시간적 최적화 결과
        """
        
        start_time = time.time()
        
        try:
            print(f"시간적 최적화 분석 시작")
            
            # 시간 제약 조건 수집
            time_constraints = self._collect_time_constraints(selected_jobs, selected_tours, slots)
            
            # GPT-4o를 활용한 시간적 최적화
            optimization_result = self._generate_temporal_optimization(
                time_constraints, geographical_result, slots
            )
            
            execution_time = time.time() - start_time
            
            result = {
                "success": True,
                "time_constraints": time_constraints,
                "daily_schedules": optimization_result.get("daily_schedules", {}),
                "time_efficiency": optimization_result.get("time_efficiency", "optimal"),
                "conflict_resolutions": optimization_result.get("conflict_resolutions", []),
                "execution_time": execution_time,
                "agent_notes": optimization_result.get("notes", "")
            }
            
            self.execution_logs.append({
                "agent": "IntelligentPlannerAgent",
                "function": "analyze_temporal_optimization",
                "execution_time": execution_time,
                "success": True
            })
            
            print(f"   시간적 최적화 완료 (실행시간: {execution_time:.2f}초)")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            self.execution_logs.append({
                "agent": "IntelligentPlannerAgent",
                "function": "analyze_temporal_optimization",
                "execution_time": execution_time,
                "success": False,
                "error": str(e)
            })
            
            print(f"   → 시간적 최적화: 기본 방식 사용")
            
            # 폴백: 기본 시간 배치
            return self._create_basic_temporal_optimization(selected_jobs, selected_tours, slots)
    
    def create_personalized_arrangement(
        self,
        geographical_result: Dict[str, Any],
        temporal_result: Dict[str, Any],
        user_preferences: Dict[str, Any],
        slots: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        개인화 맞춤 배치.
        사용자 성향("활동적" vs "여유로운")에 따른 일정 밀도 및 스타일 조정.
        
        Args:
            geographical_result: 지리적 최적화 결과
            temporal_result: 시간적 최적화 결과
            user_preferences: 사용자 선호도
            slots: 슬롯 추출 결과
            
        Returns:
            개인화 맞춤 배치 결과
        """
        
        start_time = time.time()
        
        try:
            print(f"개인화 맞춤 배치 시작")
            
            # 사용자 성향 분석
            activity_profile = self._analyze_user_activity_profile(user_preferences, slots)
            
            # GPT-4o를 활용한 개인화 배치
            arrangement_result = self._generate_personalized_arrangement(
                geographical_result,
                temporal_result,
                activity_profile,
                user_preferences
            )
            
            execution_time = time.time() - start_time
            
            result = {
                "success": True,
                "activity_profile": activity_profile,
                "personalized_schedule": arrangement_result.get("personalized_schedule", {}),
                "activity_density": arrangement_result.get("activity_density", "balanced"),
                "personalization_factors": arrangement_result.get("personalization_factors", []),
                "execution_time": execution_time,
                "agent_notes": arrangement_result.get("notes", "")
            }
            
            self.execution_logs.append({
                "agent": "IntelligentPlannerAgent",
                "function": "create_personalized_arrangement",
                "execution_time": execution_time,
                "success": True
            })
            
            print(f"   개인화 맞춤 배치 완료 (실행시간: {execution_time:.2f}초)")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            self.execution_logs.append({
                "agent": "IntelligentPlannerAgent",
                "function": "create_personalized_arrangement",
                "execution_time": execution_time,
                "success": False,
                "error": str(e)
            })
            
            print(f"   → 개인화 맞춤 배치: 기본 방식 사용")
            
            # 폴백: 균형잡힌 기본 배치
            return self._create_basic_personalized_arrangement(geographical_result, temporal_result)
    
    def _collect_location_data(
        self, 
        selected_jobs: List[JobPost], 
        selected_tours: List[TourSpot]
    ) -> Dict[str, Any]:
        """장소 정보 수집."""
        
        locations = []
        
        # 농가 정보 수집 (새로운 구조 반영)
        for job in selected_jobs:
            locations.append({
                "id": f"job_{job.id}",
                "name": job.title,
                "type": "job",
                "region": getattr(job, 'region', '지역미상'),
                "lat": getattr(job, 'lat', None),
                "lon": getattr(job, 'lon', None),
                "work_date": getattr(job, 'work_date', None),  # 실제 작업 날짜
                "work_hours": getattr(job, 'work_hours', None),  # 실제 근무시간
                "working_hours": {
                    "start": getattr(job, 'start_time', '09:00'),
                    "end": getattr(job, 'end_time', '17:00')
                },
                "address": getattr(job, 'address', ''),  # 농가 주소
                "crop_type": getattr(job, 'crop_type', ''),  # 작물
                "image_url": getattr(job, 'image_url', ''),  # 이미지 URL
                "tags": getattr(job, 'tags', '').split(',') if hasattr(job, 'tags') else []
            })
        
        # 관광지 정보 수집
        for tour in selected_tours:
            locations.append({
                "id": f"tour_{tour.id}",
                "name": tour.name,
                "type": "tour",
                "region": getattr(tour, 'region', '지역미상'),
                "lat": getattr(tour, 'lat', None),
                "lon": getattr(tour, 'lon', None),
                "operating_hours": {
                    "start": "09:00",
                    "end": "18:00"
                },
                "estimated_visit_duration": 120,  # 기본 2시간
                "tags": getattr(tour, 'tags', '').split(',') if hasattr(tour, 'tags') else []
            })
        
        return {
            "total_locations": len(locations),
            "locations": locations,
            "regions": list(set([loc["region"] for loc in locations])),
            "job_count": len(selected_jobs),
            "tour_count": len(selected_tours)
        }
    
    def _generate_geographical_optimization(
        self,
        locations_data: Dict[str, Any],
        user_preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """GPT-4o를 활용한 지리적 최적화."""
        
        system_prompt = """당신은 여행 일정의 지리적 최적화를 전문으로 하는 AI입니다.

주어진 농가와 관광지 정보를 분석하여 다음을 수행하세요:

1. **지리적 클러스터링**: 같은 지역 또는 인접 지역의 장소들을 그룹화
2. **최적 이동 경로**: 이동 거리를 최소화하는 방문 순서 생성
3. **지역별 체류 시간**: 각 지역에서의 적정 체류 시간 산정

**중요한 원칙:**
- 같은 지역 내 장소들은 연속으로 방문
- 지역 간 이동은 최소화
- 농가 체험과 관광지 방문의 자연스러운 조합

응답은 반드시 다음 JSON 형식으로 제공하세요:
{
    "optimal_route": ["지역1", "지역2", "지역3"],
    "region_clusters": {
        "지역1": {
            "locations": [장소 ID 목록],
            "estimated_stay_duration": "시간",
            "travel_notes": "이동 관련 특이사항"
        }
    },
    "travel_efficiency": "high|medium|low",
    "notes": "최적화 과정에서 고려된 주요 사항들"
}"""

        user_prompt = f"""다음 농가 및 관광지 정보를 바탕으로 지리적 최적화를 수행해 주세요:

장소 정보:
{json.dumps(locations_data, ensure_ascii=False, indent=2)}

사용자 선호도:
{json.dumps(user_preferences, ensure_ascii=False, indent=2)}

지리적으로 효율적이고 이동 부담이 적은 최적 경로를 생성해 주세요."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        
        result = response.choices[0].message.content.strip()
        
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            # 마크다운 코드 블록에서 JSON 추출 시도
            import re
            json_match = re.search(r'```json\s*\n(.*?)\n```', result, re.DOTALL)
            if json_match:
                json_content = json_match.group(1).strip()
                try:
                    return json.loads(json_content)
                except json.JSONDecodeError:
                    pass
            
            # 마크다운 없는 코드 블록에서 JSON 추출 시도
            json_match = re.search(r'```\s*\n(.*?)\n```', result, re.DOTALL)
            if json_match:
                json_content = json_match.group(1).strip()
                try:
                    return json.loads(json_content)
                except json.JSONDecodeError:
                    pass
                    
            raise Exception("JSON 파싱 실패 - fallback 사용")
    
    def _collect_time_constraints(
        self,
        selected_jobs: List[JobPost],
        selected_tours: List[TourSpot],
        slots: Dict[str, Any]
    ) -> Dict[str, Any]:
        """시간 제약 조건 수집."""
        
        constraints = {
            "date_range": {
                "start_date": slots.get("start_date", "2025-09-01"),
                "end_date": slots.get("end_date", "2025-09-03")
            },
            "daily_constraints": {},
            "activity_constraints": []
        }
        
        # 농가 작업 시간 제약 (실제 날짜와 시간 반영)
        for job in selected_jobs:
            # work_hours에서 시작/종료 시간 파싱 (예: "08:00-15:00")
            start_time, end_time = self._parse_work_hours(getattr(job, 'work_hours', ''))
            if not start_time:
                start_time = getattr(job, 'start_time', '09:00')
                end_time = getattr(job, 'end_time', '17:00')
                
            constraints["activity_constraints"].append({
                "id": f"job_{job.id}",
                "name": job.title,
                "type": "job",
                "work_date": getattr(job, 'work_date', None),  # 실제 작업 날짜
                "mandatory_hours": {
                    "start": start_time,
                    "end": end_time
                },
                "duration_hours": self._calculate_duration_hours(start_time, end_time),
                "flexibility": "low",  # 농가 시간은 유연성 낮음
                "address": getattr(job, 'address', ''),
                "crop_type": getattr(job, 'crop_type', ''),
                "image_url": getattr(job, 'image_url', '')
            })
        
        # 관광지 운영 시간 제약
        for tour in selected_tours:
            constraints["activity_constraints"].append({
                "id": f"tour_{tour.id}",
                "name": tour.name,
                "type": "tour",
                "operating_hours": {
                    "start": "09:00",
                    "end": "18:00"
                },
                "estimated_duration_minutes": 120,
                "flexibility": "high"  # 관광지는 유연성 높음
            })
        
        return constraints
    
    def _generate_temporal_optimization(
        self,
        time_constraints: Dict[str, Any],
        geographical_result: Dict[str, Any],
        slots: Dict[str, Any]
    ) -> Dict[str, Any]:
        """GPT-4o를 활용한 시간적 최적화."""
        
        system_prompt = """당신은 개인 맞춤형 일여행 추천 서비스의 시간적 최적화를 전문으로 하는 AI입니다.

주어진 시간 제약 조건과 지리적 배치를 고려하여 다음을 수행하세요:

1. **일별 시간표 생성**: 각 날짜별로 활동의 시작/종료 시간 배정
2. **시간 충돌 해결**: 겹치는 시간이나 불가능한 이동 시간 조정
3. **휴식 시간 확보**: 적절한 식사 시간과 휴식 시간 배치
4. **농가-관광 연계**: 농가 일거리 종료 후 관광 활동을 자연스럽게 연결

**핵심 원칙 - 개인 맞춤형 일여행:**
- 농가 작업 시간은 농장주가 지정한 시간 엄격히 준수 (예: 08:00-15:30)
- 농가 일거리가 15:30에 끝나면, 16:00부터는 관광지 방문 가능
- 관광지는 농가 일거리 종료 시간 이후 오후/저녁 시간대에 배치
- 같은 지역 내에서 농가 일거리 → 관광지 순서로 자연스럽게 연결
- 이동 시간을 충분히 고려 (지역 간 이동 1-2시간, 지역 내 이동 15-30분)
- 점심 시간(12:00-13:00)은 반드시 확보

응답은 반드시 다음 JSON 형식으로 제공하세요:
{
    "daily_schedules": {
        "2025-09-01": [
            {
                "activity_id": "job_1",
                "activity_name": "농가 체험",
                "start_time": "09:00",
                "end_time": "12:00",
                "type": "job",
                "notes": "특별 고려사항"
            }
        ]
    },
    "time_efficiency": "optimal|good|acceptable",
    "conflict_resolutions": ["해결된 충돌 사항들"],
    "notes": "시간 배치 시 고려된 주요 사항들"
}"""

        user_prompt = f"""다음 정보를 바탕으로 시간적 최적화를 수행해 주세요:

시간 제약 조건:
{json.dumps(time_constraints, ensure_ascii=False, indent=2)}

지리적 최적화 결과:
{json.dumps(geographical_result, ensure_ascii=False, indent=2)}

각 활동의 시간 제약을 준수하면서 효율적이고 현실적인 일정을 생성해 주세요."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        result = response.choices[0].message.content.strip()
        
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            # 마크다운 코드 블록에서 JSON 추출 시도
            import re
            json_match = re.search(r'```json\s*\n(.*?)\n```', result, re.DOTALL)
            if json_match:
                json_content = json_match.group(1).strip()
                try:
                    return json.loads(json_content)
                except json.JSONDecodeError:
                    pass
            
            # 마크다운 없는 코드 블록에서 JSON 추출 시도
            json_match = re.search(r'```\s*\n(.*?)\n```', result, re.DOTALL)
            if json_match:
                json_content = json_match.group(1).strip()
                try:
                    return json.loads(json_content)
                except json.JSONDecodeError:
                    pass
                    
            raise Exception("Agent JSON 파싱 실패 - fallback 사용")
    
    def _analyze_user_activity_profile(
        self,
        user_preferences: Dict[str, Any],
        slots: Dict[str, Any]
    ) -> Dict[str, Any]:
        """사용자 활동 프로필 분석."""
        
        # 활동 성향 분석
        activity_tags = user_preferences.get("activity_style_tags", [])
        terrain_tags = user_preferences.get("terrain_tags", [])
        
        # 키워드 기반 성향 분석
        active_keywords = ["활동적", "체험", "모험", "적극적", "빠른"]
        relaxed_keywords = ["여유", "휴식", "느긋", "편안", "천천히"]
        
        active_score = sum(1 for tag in activity_tags + terrain_tags 
                          if any(keyword in str(tag) for keyword in active_keywords))
        relaxed_score = sum(1 for tag in activity_tags + terrain_tags 
                           if any(keyword in str(tag) for keyword in relaxed_keywords))
        
        # 성향 결정
        if active_score > relaxed_score:
            activity_style = "active"
            activity_density = "high"
        elif relaxed_score > active_score:
            activity_style = "relaxed"
            activity_density = "low"
        else:
            activity_style = "balanced"
            activity_density = "medium"
        
        return {
            "activity_style": activity_style,  # "active", "relaxed", "balanced"
            "activity_density": activity_density,  # "high", "medium", "low"
            "active_score": active_score,
            "relaxed_score": relaxed_score,
            "preferences_summary": {
                "activity_tags": activity_tags,
                "terrain_tags": terrain_tags
            }
        }
    
    def _generate_personalized_arrangement(
        self,
        geographical_result: Dict[str, Any],
        temporal_result: Dict[str, Any],
        activity_profile: Dict[str, Any],
        user_preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """GPT-4o를 활용한 개인화 배치."""
        
        system_prompt = """당신은 개인 맞춤형 농촌 일정을 전문으로 하는 AI입니다.

사용자의 활동 성향과 선호도를 분석하여 다음을 수행하세요:

1. **활동 밀도 조정**: 사용자 성향에 따른 일정 빈도 조정
   - "활동적": 빡빡한 일정, 다양한 체험 배치
   - "여유로운": 충분한 휴식시간, 느긋한 일정 배치
   - "균형": 적당한 활동과 휴식의 조화

2. **개인화 요소 반영**: 사용자 선호도에 맞는 활동 우선순위
3. **스타일 맞춤**: 개인의 여행 스타일에 맞는 전체적인 흐름

**중요한 원칙:**
- 사용자 성향을 일정 전반에 반영
- 무리하지 않는 선에서 최대한의 만족도 추구
- 개인의 체력과 관심사 고려

응답은 반드시 다음 JSON 형식으로 제공하세요:
{
    "personalized_schedule": {
        "2025-09-01": [
            {
                "activity_id": "job_1",
                "activity_name": "농가 체험",
                "start_time": "09:00",
                "end_time": "12:00",
                "type": "job",
                "personalization_notes": "활동적 성향에 맞춘 적극적 체험",
                "rest_time_after": 30
            }
        ]
    },
    "activity_density": "high|medium|low",
    "personalization_factors": ["적용된 개인화 요소들"],
    "notes": "개인화 과정에서 고려된 주요 사항들"
}"""

        user_prompt = f"""다음 정보를 바탕으로 개인화 맞춤 배치를 수행해 주세요:

지리적 최적화 결과:
{json.dumps(geographical_result, ensure_ascii=False, indent=2)}

시간적 최적화 결과:
{json.dumps(temporal_result, ensure_ascii=False, indent=2)}

사용자 활동 프로필:
{json.dumps(activity_profile, ensure_ascii=False, indent=2)}

사용자의 성향과 선호도에 완벽히 맞춤화된 일정을 생성해 주세요."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        result = response.choices[0].message.content.strip()
        
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            # 마크다운 코드 블록에서 JSON 추출 시도
            import re
            json_match = re.search(r'```json\s*\n(.*?)\n```', result, re.DOTALL)
            if json_match:
                json_content = json_match.group(1).strip()
                try:
                    return json.loads(json_content)
                except json.JSONDecodeError:
                    pass
            
            # 마크다운 없는 코드 블록에서 JSON 추출 시도
            json_match = re.search(r'```\s*\n(.*?)\n```', result, re.DOTALL)
            if json_match:
                json_content = json_match.group(1).strip()
                try:
                    return json.loads(json_content)
                except json.JSONDecodeError:
                    pass
                    
            raise Exception("Agent JSON 파싱 실패 - fallback 사용")
    
    # ====== 폴백 메서드들 ======
    
    def _create_basic_geographical_optimization(
        self,
        selected_jobs: List[JobPost],
        selected_tours: List[TourSpot]
    ) -> Dict[str, Any]:
        """기본 지리적 최적화 (GPT 폴백용)."""
        
        regions = set()
        location_groups = {}
        
        # 지역별 그룹화
        for job in selected_jobs:
            region = getattr(job, 'region', '지역미상')
            regions.add(region)
            if region not in location_groups:
                location_groups[region] = []
            location_groups[region].append(f"job_{job.id}")
        
        for tour in selected_tours:
            region = getattr(tour, 'region', '지역미상')
            regions.add(region)
            if region not in location_groups:
                location_groups[region] = []
            location_groups[region].append(f"tour_{tour.id}")
        
        return {
            "success": True,
            "optimal_route": sorted(list(regions)),
            "region_clusters": {
                region: {
                    "locations": locations,
                    "estimated_stay_duration": f"{len(locations) * 2}시간",
                    "travel_notes": "기본 배치"
                }
                for region, locations in location_groups.items()
            },
            "travel_efficiency": "medium",
            "agent_notes": "기본 지리적 최적화 적용됨"
        }
    
    def _create_basic_temporal_optimization(
        self,
        selected_jobs: List[JobPost],
        selected_tours: List[TourSpot],
        slots: Dict[str, Any]
    ) -> Dict[str, Any]:
        """기본 시간적 최적화 (GPT 폴백용)."""
        
        start_date = slots.get("start_date", "2025-09-01")
        date_range = self._calculate_date_range(slots)
        
        daily_schedules = {}
        all_activities = []
        
        # 활동 목록 생성
        for job in selected_jobs:
            all_activities.append({
                "id": f"job_{job.id}",
                "name": job.title,
                "type": "job",
                "start_time": getattr(job, 'start_time', '09:00'),
                "end_time": getattr(job, 'end_time', '17:00')
            })
        
        for tour in selected_tours:
            all_activities.append({
                "id": f"tour_{tour.id}",
                "name": tour.name,
                "type": "tour",
                "start_time": "13:00",
                "end_time": "15:00"
            })
        
        # 일별 배분
        activities_per_day = max(1, len(all_activities) // len(date_range))
        
        for i, date in enumerate(date_range):
            start_idx = i * activities_per_day
            end_idx = min(start_idx + activities_per_day, len(all_activities))
            
            if i == len(date_range) - 1:  # 마지막 날
                end_idx = len(all_activities)
            
            daily_schedules[date] = all_activities[start_idx:end_idx]
        
        return {
            "success": True,
            "daily_schedules": daily_schedules,
            "time_efficiency": "acceptable",
            "conflict_resolutions": [],
            "agent_notes": "기본 시간적 최적화 적용됨"
        }
    
    def _create_basic_personalized_arrangement(
        self,
        geographical_result: Dict[str, Any],
        temporal_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """기본 개인화 배치 (GPT 폴백용)."""
        
        # 시간적 최적화 결과를 기반으로 기본 개인화 적용
        personalized_schedule = temporal_result.get("daily_schedules", {})
        
        return {
            "success": True,
            "activity_profile": {"activity_style": "balanced", "activity_density": "medium"},
            "personalized_schedule": personalized_schedule,
            "activity_density": "medium",
            "personalization_factors": ["기본 균형 배치"],
            "agent_notes": "기본 개인화 배치 적용됨"
        }
    
    def _calculate_duration_hours(self, start_time: str, end_time: str) -> int:
        """시간 차이 계산."""
        try:
            start = datetime.strptime(start_time, "%H:%M")
            end = datetime.strptime(end_time, "%H:%M")
            duration = (end - start).total_seconds() / 3600
            return max(1, int(duration))
        except:
            return 8
    
    def _parse_work_hours(self, work_hours: str) -> tuple:
        """근무시간 문자열을 시작/종료 시간으로 파싱 (예: "08:00-15:00")."""
        if not work_hours or work_hours == '':
            return None, None
        try:
            if '-' in work_hours:
                start, end = work_hours.split('-', 1)
                return start.strip(), end.strip()
        except:
            pass
        return None, None
    
    def _calculate_date_range(self, slots: Dict[str, Any]) -> List[str]:
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
    
    def recommend_additional_regional_tours(
        self,
        selected_jobs: List[JobPost],
        selected_tours: List[TourSpot],
        user_preferences: Dict[str, Any],
        slots: Dict[str, Any]
    ) -> List[TourSpot]:
        """
        선택된 카드들의 지역 내에서 추가 관광지를 추천합니다.
        사용자 선호도와 벡터 유사도를 기반으로 추천합니다.
        
        Args:
            selected_jobs: 선택된 농가 카드들
            selected_tours: 선택된 관광지 카드들  
            user_preferences: 사용자 선호도
            slots: 추출된 슬롯 정보
            
        Returns:
            추천된 추가 관광지 리스트
        """
        try:
            print("🔍 지역 내 추가 관광지 추천 시작")
            
            # 선택된 카드들에서 지역 정보 추출
            regions = set()
            for job in selected_jobs:
                if hasattr(job, 'region') and job.region:
                    regions.add(job.region)
            for tour in selected_tours:
                if hasattr(tour, 'region') and tour.region:
                    regions.add(tour.region)
                    
            if not regions:
                print("❌ 지역 정보가 없어 추가 관광지 추천을 생략합니다.")
                return []
                
            print(f"📍 대상 지역: {list(regions)}")
            
            # 이미 선택된 관광지 ID들
            selected_tour_ids = {tour.id for tour in selected_tours}
            
            # 지역 내 모든 관광지 조회 (이미 선택된 것 제외)
            from sqlalchemy import or_
            regional_tours_query = self.db_session.query(TourSpot).filter(
                or_(*[TourSpot.region.like(f"%{region}%") for region in regions]),
                ~TourSpot.id.in_(selected_tour_ids)
            )
            
            regional_tours = regional_tours_query.all()
            print(f"🏞️ 지역 내 후보 관광지: {len(regional_tours)}개")
            
            if not regional_tours:
                return []
            
            # 사용자 선호도 키워드 추출
            preference_keywords = []
            if user_preferences and 'keywords' in user_preferences:
                preference_keywords.extend(user_preferences['keywords'])
            if slots:
                if slots.get('activity_tags'):
                    preference_keywords.extend(slots['activity_tags'])
                if slots.get('terrain_pref'):
                    preference_keywords.extend(slots['terrain_pref'])
                    
            print(f"🏷️ 선호도 키워드: {preference_keywords}")
            
            # 키워드 매칭으로 후보 필터링
            recommended_tours = []
            for tour in regional_tours:
                if hasattr(tour, 'tags') and tour.tags:
                    # 태그 문자열을 리스트로 변환
                    tour_tags = []
                    if isinstance(tour.tags, str):
                        tour_tags = [tag.strip() for tag in tour.tags.split(',')]
                    elif isinstance(tour.tags, list):
                        tour_tags = tour.tags
                    
                    # 키워드 매칭 점수 계산
                    match_score = 0
                    for keyword in preference_keywords:
                        for tag in tour_tags:
                            if keyword.lower() in tag.lower() or tag.lower() in keyword.lower():
                                match_score += 1
                                break
                                
                    if match_score > 0:
                        recommended_tours.append((tour, match_score))
            
            # 점수 기준으로 정렬하고 상위 5개 선택
            recommended_tours.sort(key=lambda x: x[1], reverse=True)
            final_recommendations = [tour for tour, score in recommended_tours[:5]]
            
            print(f"✅ 추가 관광지 추천 완료: {len(final_recommendations)}개")
            for tour in final_recommendations:
                print(f"   - {tour.name} ({getattr(tour, 'region', '지역정보없음')})")
                
            return final_recommendations
            
        except Exception as e:
            print(f"❌ 추가 관광지 추천 중 오류: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_execution_logs(self) -> List[Dict[str, Any]]:
        """실행 로그 반환."""
        return self.execution_logs.copy()
    
    def clear_execution_logs(self):
        """실행 로그 초기화."""
        self.execution_logs.clear()