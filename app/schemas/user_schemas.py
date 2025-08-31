"""
Bubble User2 데이터 구조에 맞는 사용자 스키마
"""

from pydantic import BaseModel, Field
from typing import List, Optional

class BubbleUser2(BaseModel):
    """Bubble User2 테이블에 맞는 사용자 데이터 모델"""
    
    address: str = Field(..., description="거주지 (시/도 + 시/군/구 결합)")
    age: str = Field(..., description="나이 (직접 입력, 예: '24')")
    gender: str = Field(..., description="성별 '남/여' 선택")
    name: str = Field(..., description="닉네임")
    
    # 선호도 데이터 (List of texts)
    pref_etc: List[str] = Field(default=[], description="5_onboarding5 '서술형' 텍스트")
    pref_jobs: List[str] = Field(default=[], description="4_onboarding4 사용자 선택 '체험' 유형")
    pref_style: List[str] = Field(default=[], description="3_onboarding3 사용자 선택 '여행 스타일' 유형")
    pref_view: List[str] = Field(default=[], description="2_onboarding2 사용자 선택 '풍경' 유형")
    
    real_name: str = Field(default="지현", description="사용자의 실제 이름")
    with_whom: str = Field(..., description="index '누구와 떠날까요?' 선택 값")

class OnboardingRequest(BaseModel):
    """온보딩 요청 데이터"""
    
    # 기본 정보
    real_name: str = Field(default="지현")
    name: str = Field(..., description="닉네임")
    age: str = Field(..., description="나이 (직접 입력, 예: '24')")
    gender: str = Field(..., description="성별")
    sido: str = Field(..., description="시/도")
    sigungu: str = Field(..., description="시/군/구")
    
    # 누구와 함께
    with_whom: str = Field(..., description="누구와 떠날까요")
    
    # 선호도 (온보딩 단계별)
    selected_views: List[str] = Field(default=[], description="2단계: 풍경 선호도")
    selected_styles: List[str] = Field(default=[], description="3단계: 여행 스타일 선호도") 
    selected_jobs: List[str] = Field(default=[], description="4단계: 체험 유형 선호도")
    additional_requests: List[str] = Field(default=[], description="6단계: 서술형 추가 요청 (5개 칸)")

class OnboardingResponse(BaseModel):
    """온보딩 응답 데이터"""
    
    status: str
    message: str
    user_id: Optional[str] = None
    user_data: Optional[BubbleUser2] = None