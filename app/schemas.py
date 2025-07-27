"""
app/schemas.py
~~~~~~~~~~~~~~
API 입‧출력용 Pydantic 모델 정의
"""

from typing import List, Optional
from datetime import date
from pydantic import BaseModel, Field

# ──────────────────────────────────
# 요청 모델
class RecommendationRequest(BaseModel):
    """
    자연어 질의 + (선택) 사용자 ID, 예산
    """
    query: str = Field(..., example="9월 초 강원 평창에서 허브농장 체험하고 사찰도 둘러보고 싶어요")
    user_id: Optional[int] = Field(None, example=42)
    budget: Optional[int] = Field(None, description="예산(만원)", example=50)


# ──────────────────────────────────
# 응답 모델
class ScheduleItem(BaseModel):
    """
    일정의 한 블록(농장 일거리 or 관광지 방문)
    """
    type: str = Field(..., example="job" )          # job / tour
    ref_id: int = Field(..., example=7)              # job_posts.id or tour_spots.id
    name: str = Field(..., example="허브 농장 체험")
    start_time: str = Field(..., example="09:00")
    end_time: str = Field(..., example="12:00")
    cost: int = Field(0, description="예상 비용(원)")

class Itinerary(BaseModel):
    """
    하루 단위(또는 전체 여정) 일정
    """
    date: date
    items: List[ScheduleItem]
    total_cost: int

    class Config:
        orm_mode = True     # SQLAlchemy 객체도 직렬화 가능


class UserSlots(BaseModel):
    """
    자연어에서 추출된 구조화 정보
    """
    region: Optional[str] = Field(None, example="강원")
    month:  Optional[date] = Field(None, example="2025-09-01")
    # 필요 시 tag·duration 등 계속 추가