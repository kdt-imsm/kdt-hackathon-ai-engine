"""
app/schemas.py
==============

Pydantic 데이터 모델(Pydantic Schemas) 정의 모듈
FastAPI 엔드포인트 Request/Response 바디 검증 및 문서화를 담당합니다.

섹션별 역할
------------
1. 슬롯 추출 관련 모델
   * `SlotQuery`      : 자연어 입력 파싱 요청 바디
   * `JobPreview`     : 일거리 카드 미리보기(단건)
   * `TourPreview`    : 관광지 카드 미리보기(단건)
   * `SlotsResponse`  : 슬롯 + 카드 10개 미리보기 응답

2. 추천(일정 생성) 관련 모델
   * `RecommendationRequest` : 공통 필드(query, user_id, budget)
   * `RecommendRequest`      : 선택한 카드 ID 리스트를 추가한 최종 요청

3. 일정(Itinerary) 모델
   * `ScheduleItem` : 하루 단위 일정 항목
   * `Itinerary`    : 향후 확장 가능성을 위해 ScheduleItem 을 그대로 상속

주의사항
~~~~~~~~
• 이 모듈은 비즈니스 로직이 없는 순수 데이터 클래스만 포함해야 합니다.
• 필드 순서나 타입을 변경하면 FastAPI 스펙 및 클라이언트와의 계약이 깨질 수 있으므로, 기존 필드는 그대로 유지해야 합니다.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, validator

# ─────────────────────────────────────────────────────────────────
# 1) 슬롯 추출용 스키마
# ─────────────────────────────────────────────────────────────────

class SlotQuery(BaseModel):
    """사용자 자연어 쿼리 하나를 감싸는 Request Body 모델."""
    query: str = Field(
        ...,  # 필수값
        example="9월 첫째 주 고창에서 조개잡이 + 해변 관광하고 싶어요",
        description="일·여행 조건이 포함된 자연어 문장",
    )


# ─────────────────────────────────────────────────────────────────
# 2) 카드 미리보기 응답 모델
# ─────────────────────────────────────────────────────────────────

class JobPreview(BaseModel):
    """벡터 유사도 상위 Job(일거리) 카드 메타데이터."""
    job_id: int
    farm_name: str
    region: str
    tags: List[str]


class TourPreview(BaseModel):
    """벡터 유사도 상위 Tour(관광지) 카드 메타데이터."""
    content_id: int
    title: str
    region: str
    overview: str
    image_url: Optional[str] = None  # 이미지 URL 필드 추가
    matched_keywords: Optional[List[str]] = Field(default_factory=list, description="키워드 검색으로 매칭된 키워드들")  # 매칭된 키워드 필드


class SlotsResponse(BaseModel):
    """/slots 엔드포인트 응답 모델."""
    success: bool = True  # 성공 여부
    slots: dict  # GPT Slot Extraction 결과(JSON)
    jobs_preview: List[JobPreview]
    tours_preview: List[TourPreview]
    error: Optional[str] = None  # 에러 메시지


# ─────────────────────────────────────────────────────────────────
# 3) 추천 요청 스키마
# ─────────────────────────────────────────────────────────────────

class RecommendationRequest(BaseModel):
    """추천(일정 생성) 요청 공통 필드."""
    query: str
    user_id: Optional[UUID] = None  # 로그인 사용자 식별자(옵션)


class RecommendRequest(RecommendationRequest):
    """/recommend 엔드포인트 최종 Request Body."""
    selected_jobs: List[int] = Field(default_factory=list)
    selected_tours: List[int] = Field(default_factory=list)
    budget: Optional[int] = Field(default=None, description="예산 (선택적, 스마트 스케줄링에서는 사용하지 않음)")

    @validator('selected_jobs', pre=True)
    def validate_selected_jobs(cls, v):
        """selected_jobs 필드를 안전하게 정수 배열로 변환"""
        if v is None:
            return []
        if not isinstance(v, list):
            # 문자열이나 다른 타입이면 빈 배열 반환
            return []
        
        result = []
        for item in v:
            try:
                # 각 아이템을 정수로 변환 시도
                if isinstance(item, (int, float)):
                    result.append(int(item))
                elif isinstance(item, str) and item.isdigit():
                    result.append(int(item))
                # 변환할 수 없는 값은 건너뜀
            except (ValueError, TypeError):
                continue
        return result

    @validator('selected_tours', pre=True)
    def validate_selected_tours(cls, v):
        """selected_tours 필드를 안전하게 정수 배열로 변환"""
        if v is None:
            return []
        if not isinstance(v, list):
            # 문자열이나 다른 타입이면 빈 배열 반환
            return []
        
        result = []
        for item in v:
            try:
                # 각 아이템을 정수로 변환 시도
                if isinstance(item, (int, float)):
                    result.append(int(item))
                elif isinstance(item, str) and item.isdigit():
                    result.append(int(item))
                # 변환할 수 없는 값은 건너뜀
            except (ValueError, TypeError):
                continue
        return result


# ─────────────────────────────────────────────────────────────────
# 4) 일정(Itinerary) 모델
# ─────────────────────────────────────────────────────────────────

class ScheduleItem(BaseModel):
    """하루 단위 여행·일거리 Schedule."""
    day: int
    date: str
    plan_items: List[str]
    total_distance_km: Optional[float]


class Itinerary(ScheduleItem):
    """현재는 ScheduleItem과 동일하지만 향후 다중 일정을 위한 래퍼."""

    pass  # 확장을 위해 비워둠


# ─────────────────────────────────────────────────────────────────
# 6) 자연어 일정 생성 관련 모델
# ─────────────────────────────────────────────────────────────────

class DetailedItineraryResponse(BaseModel):
    """GPT-4o 기반 자연어 일정 생성 응답 모델."""
    
    # 기존 JSON 일정 (하위 호환성)
    legacy_itineraries: List[Itinerary] = Field(
        description="기존 JSON 형태 일정 (하위 호환성 유지)"
    )
    
    # 자연어 일정
    natural_language_itinerary: str = Field(
        description="GPT-4o가 생성한 자연어 형태의 상세 일정"
    )
    
    # 일정 메타데이터
    total_days: int = Field(description="총 여행 기간 (일)")
    date_range: List[str] = Field(description="여행 날짜 범위 (YYYY-MM-DD)")
    estimated_total_cost: int = Field(default=0, description="예상 총 비용 (원)")
    
    # 요약 정보
    summary: Dict[str, Any] = Field(
        description="일정 요약 정보 (선택한 일거리/관광지 수, 지역 등)"
    )
    
    # 성공 여부
    success: bool = Field(default=True, description="일정 생성 성공 여부")
    error_message: Optional[str] = Field(default=None, description="오류 메시지 (실패 시)")


class ActivitySummary(BaseModel):
    """활동 요약 정보 모델."""
    id: int
    name: str
    type: str  # 'job' or 'tour'
    region: str
    estimated_duration_minutes: int
    scheduled_date: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None


# ─────────────────────────────────────────────────────────────────
# 5) Multi-Agent 스케줄링 시스템 스키마
# ─────────────────────────────────────────────────────────────────

class FarmApplicationRequest(BaseModel):
    """농장주의 일정 신청 요청."""
    start_date: str = Field(
        ...,
        example="2025-09-10",
        description="작업 시작 날짜 (YYYY-MM-DD)"
    )
    end_date: str = Field(
        ...,
        example="2025-09-17",
        description="작업 종료 날짜 (YYYY-MM-DD)"
    )
    start_time: str = Field(
        ...,
        example="09:00",
        description="작업 시작 시간 (HH:MM)"
    )
    end_time: str = Field(
        ...,
        example="15:00",
        description="작업 종료 시간 (HH:MM)"
    )
    max_workers: int = Field(
        ...,
        example=3,
        description="모집 인원 수",
        ge=1,
        le=30
    )
    farmer_contact: str = Field(
        ...,
        example="010-1234-5678",
        description="농장주 연락처"
    )
    job_id: int = Field(
        ...,
        description="일자리 ID"
    )
    description: Optional[str] = Field(
        None,
        example="벼 수확 작업입니다. 초보자도 환영합니다.",
        description="추가 설명"
    )


class YouthApplicationRequest(BaseModel):
    """청년의 농장 일자리 신청 요청."""
    user_id: int = Field(
        ...,
        description="신청하는 청년의 사용자 ID"
    )
    farm_application_id: int = Field(
        ...,
        description="농장주 신청 ID"
    )
    selected_jobs: List[int] = Field(
        default_factory=list,
        description="선택한 일자리 ID 목록"
    )
    selected_tours: List[int] = Field(
        default_factory=list,
        description="선택한 관광지 ID 목록"
    )
    preferences: Optional[str] = Field(
        None,
        description="추가 선호사항"
    )


class WorkScheduleItem(BaseModel):
    """개별 작업 스케줄 항목."""
    youth_id: int
    user_name: str
    work_date: str
    start_time: str
    end_time: str
    assigned_tasks: str
    transport_info: Optional[str] = None
    notes: Optional[str] = None


class WaitingListItem(BaseModel):
    """대기열 항목."""
    youth_id: int
    user_name: str
    queue_position: int
    preferences: Optional[str] = None


class MultiAgentScheduleResponse(BaseModel):
    """Multi-Agent 스케줄링 결과 응답."""
    success: bool
    session_id: str
    execution_time: float
    farm_application: Optional[Dict[str, Any]] = None
    final_schedule: Optional[Dict[str, Any]] = None
    negotiation_history: Optional[List[Dict[str, Any]]] = None
    warnings: Optional[List[str]] = None
    suggestions: Optional[List[str]] = None
    error: Optional[str] = None


class FarmApplicationResponse(BaseModel):
    """농장주 신청 처리 결과."""
    success: bool
    farm_application_id: int
    message: str
    error: Optional[str] = None


class YouthApplicationResponse(BaseModel):
    """청년 신청 처리 결과."""
    success: bool
    youth_application_id: int
    status: str  # confirmed, waiting, rejected
    queue_position: Optional[int] = None
    message: str
    error: Optional[str] = None


class ScheduleStatusResponse(BaseModel):
    """스케줄 상태 조회 결과."""
    farm_application_id: int
    status: str
    confirmed_workers: int
    waiting_workers: int
    schedules: List[WorkScheduleItem]
    waiting_list: List[WaitingListItem]


class AgentLogItem(BaseModel):
    """Agent 실행 로그 항목."""
    session_id: str
    agent_type: str
    execution_time: float
    success: bool
    created_at: datetime
    error_message: Optional[str] = None


class SystemStatusResponse(BaseModel):
    """시스템 상태 응답."""
    total_farm_applications: int
    total_youth_applications: int
    total_confirmed_schedules: int
    recent_agent_logs: List[AgentLogItem]
    system_health: str


# ─────────────────────────────────────────────────────────────────
# 6) 스마트 스케줄링 피드백 시스템 스키마
# ─────────────────────────────────────────────────────────────────

class ActivityModification(BaseModel):
    """개별 활동 수정사항."""
    type: str = Field(
        ...,
        description="수정 타입: remove_activity, change_time, replace_activity, add_activity, reorder_activities"
    )
    date: Optional[str] = Field(None, description="대상 날짜 (YYYY-MM-DD)")
    activity_id: Optional[str] = Field(None, description="활동 ID")
    old_activity_id: Optional[str] = Field(None, description="교체할 기존 활동 ID")
    new_activity: Optional[dict] = Field(None, description="새로운 활동 정보")
    activity: Optional[dict] = Field(None, description="추가할 활동 정보")
    insert_index: Optional[int] = Field(None, description="삽입 위치")
    new_start_time: Optional[str] = Field(None, description="새로운 시작 시간")
    new_end_time: Optional[str] = Field(None, description="새로운 종료 시간")
    new_order: Optional[List[str]] = Field(None, description="새로운 활동 순서")


class ItineraryFeedbackRequest(BaseModel):
    """일정 피드백 요청."""
    session_id: str = Field(..., description="세션 ID")
    modifications: List[ActivityModification] = Field(
        default=[],
        description="활동 수정사항 리스트"
    )
    user_preferences: Optional[Dict[str, Any]] = Field(
        default={},
        description="업데이트된 사용자 선호도"
    )


class ItineraryFeedbackResponse(BaseModel):
    """일정 피드백 응답."""
    success: bool
    updated_itinerary: Optional[str] = None
    changes_summary: Optional[List[str]] = None
    execution_time: Optional[float] = None
    error: Optional[str] = None
    traceback: Optional[str] = None


