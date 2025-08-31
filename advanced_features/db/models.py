"""
app/db/models.py
================
SQLAlchemy ORM 모델 정의 모듈

* **User**      : 회원 정보 + 선호도 벡터 + 피드백 관계
* **Tag**       : 태그 마스터 테이블 (예비)
* **JobPost**   : 농가 일거리 포스트
* **TourSpot**  : 관광지 정보(TourAPI 기반)
* **Feedback**  : 사용자 행동 피드백(+1/-1)

공통 사항
---------
• 모든 모델은 `Base`(DeclarativeBase) 를 상속합니다.
• pgvector 확장을 이용해 1536차원 임베딩(Vector) 컬럼을 저장합니다.
• 관계형 필드(`relationship`)는 역참조(back_populates)를 명시하여 쿼리 시
  편리한 네비게이션이 가능합니다.

주의
~~~~
이 파일은 **스키마 변경이 빈번할 수 있으므로** 실제 운영 전에는 Alembic 등을
사용한 마이그레이션 관리가 필요합니다.
"""

from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.db.database import Base
from datetime import datetime, timezone


class User(Base):
    """회원 테이블.

    Columns
    --------
    id            : PK (자동 증가)
    email         : 로그인 이메일(유니크)
    pref_vector   : 1536차원 사용자 선호 벡터(pgvector)
    terrain_tags  : 지형 선호 태그 배열
    activity_style_tags : 활동 스타일 태그 배열
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    # 1536차원 선호 벡터 (text-embedding-3-small 등)
    pref_vector: Mapped[list[float]] = Column(Vector(1536), nullable=True)

    terrain_tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=True)
    activity_style_tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=True)

    # 사용자의 피드백 기록 (1:N)
    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="user")


class Tag(Base):
    """태그 마스터(미사용 시 향후 확장용)."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)


class JobPost(Base):
    """농가 일거리 정보."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)  # 작업명
    work_date: Mapped[str] = mapped_column(String, nullable=True)  # 작업 날짜 YYYY-MM-DD
    work_hours: Mapped[str] = mapped_column(String, nullable=True)  # 근무시간 HH:MM-HH:MM
    required_people: Mapped[str] = mapped_column(String, nullable=True)  # 필요 인원
    region: Mapped[str] = mapped_column(String, nullable=False)  # 위치(지역)
    address: Mapped[str] = mapped_column(String, nullable=True)  # 주소
    crop_type: Mapped[str] = mapped_column(String, nullable=True)  # 작물
    preference_condition: Mapped[str] = mapped_column(String, nullable=True)  # 선호조건
    image_url: Mapped[str] = mapped_column(String, nullable=True)  # 이미지 URL
    
    # 기존 호환성 유지 필드들
    tags: Mapped[str] = mapped_column(String, nullable=False)  # crop_type + preference_condition 조합
    lat: Mapped[float] = mapped_column(Float, nullable=True)
    lon: Mapped[float] = mapped_column(Float, nullable=True)
    start_time: Mapped[str] = mapped_column(String, nullable=True)  # work_hours에서 추출
    end_time: Mapped[str] = mapped_column(String, nullable=True)    # work_hours에서 추출

    # 1536차원 콘텐츠 벡터
    pref_vector: Mapped[list[float]] = Column(Vector(1536), nullable=True)


class TourSpot(Base):
    """TourAPI 기반 관광지 정보."""

    __tablename__ = "tour_spots"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    region: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[str] = mapped_column(String, nullable=False)  # 카테고리 코드 또는 태그
    lat: Mapped[float] = mapped_column(Float, nullable=True)
    lon: Mapped[float] = mapped_column(Float, nullable=True)
    
    # TourAPI contentid 및 이미지 URL 필드 추가
    contentid: Mapped[str] = mapped_column(String, nullable=True)  # TourAPI contentid
    image_url: Mapped[str] = mapped_column(String, nullable=True)  # 대표 이미지 URL

    # 키워드 검색으로 수집한 상세 키워드 정보 (JSON 문자열)
    detailed_keywords: Mapped[str] = mapped_column(Text, nullable=True)  # JSON 형태의 키워드 배열
    
    # 수집된 관광지 키워드 (CSV 기반)
    keywords: Mapped[str] = mapped_column(Text, nullable=True)  # 수집된 키워드 문자열

    # 1536차원 콘텐츠 벡터
    pref_vector: Mapped[list[float]] = Column(Vector(1536), nullable=True)


class DemoFarm(Base):
    """Demo 데이터용 농가 정보 모델 (data2/demo_data_jobs.csv)."""

    __tablename__ = "demo_farms"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_name: Mapped[str] = mapped_column(String, nullable=False)
    required_workers: Mapped[int] = mapped_column(Integer, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
    detail_address: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[str] = mapped_column(String, nullable=False)
    end_time: Mapped[str] = mapped_column(String, nullable=False)
    tag: Mapped[str] = mapped_column(String, nullable=False)
    image_name: Mapped[str] = mapped_column(String, nullable=False)

    # 지역 정보 추가 (전북 지역만)
    region: Mapped[str] = mapped_column(String, nullable=True)  # 정규화된 지역명
    
    # 위치 정보 (향후 확장용)
    lat: Mapped[float] = mapped_column(Float, nullable=True)
    lon: Mapped[float] = mapped_column(Float, nullable=True)

    # 1536차원 콘텐츠 벡터 (벡터 유사도 추천용)
    pref_vector: Mapped[list[float]] = Column(Vector(1536), nullable=True)


class Feedback(Base):
    """사용자 ↔ 콘텐츠 피드백(+1/-1)."""

    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    content_id: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)  # "job" or "tour"
    score: Mapped[float] = mapped_column(Float, nullable=False)       # +1: 좋아요, -1: 싫어요

    # 역참조: 사용자 ↔ 피드백 (N:1)
    user: Mapped["User"] = relationship(back_populates="feedbacks")


class FarmApplication(Base):
    """농장주 일정 신청 테이블 - 농장주가 일자리 모집을 위해 등록하는 정보."""
    
    __tablename__ = "farm_applications"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    farmer_contact: Mapped[str] = mapped_column(String, nullable=False)  # 농장주 연락처
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    start_time: Mapped[str] = mapped_column(String, nullable=False, default="09:00")  # 작업 시작 시간
    end_time: Mapped[str] = mapped_column(String, nullable=False, default="17:00")   # 작업 종료 시간
    max_workers: Mapped[int] = mapped_column(Integer, nullable=False)  # 최대 모집 인원
    description: Mapped[str] = mapped_column(Text, nullable=True)  # 추가 설명
    status: Mapped[str] = mapped_column(String, default="active")  # active, closed, cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # 관계
    job: Mapped["JobPost"] = relationship()
    youth_applications: Mapped[list["YouthApplication"]] = relationship(back_populates="farm_application")
    schedules: Mapped[list["WorkSchedule"]] = relationship(back_populates="farm_application")


class YouthApplication(Base):
    """청년 신청 테이블 - 청년이 특정 농장 일자리에 신청하는 정보."""
    
    __tablename__ = "youth_applications"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    farm_application_id: Mapped[int] = mapped_column(ForeignKey("farm_applications.id"), nullable=False)
    selected_jobs: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)  # 선택한 일자리 ID들
    selected_tours: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)  # 선택한 관광지 ID들
    preferences: Mapped[str] = mapped_column(Text, nullable=True)  # 추가 선호사항
    status: Mapped[str] = mapped_column(String, default="pending")  # pending, confirmed, waiting, rejected
    queue_position: Mapped[int] = mapped_column(Integer, nullable=True)  # 대기열 순서 (1-3)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # 관계
    user: Mapped["User"] = relationship()
    farm_application: Mapped["FarmApplication"] = relationship(back_populates="youth_applications")


class WorkSchedule(Base):
    """최종 확정된 작업 스케줄 - Multi-Agent가 생성한 최종 일정."""
    
    __tablename__ = "work_schedules"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_application_id: Mapped[int] = mapped_column(ForeignKey("farm_applications.id"), nullable=False)
    youth_application_id: Mapped[int] = mapped_column(ForeignKey("youth_applications.id"), nullable=False)
    work_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    start_time: Mapped[str] = mapped_column(String, nullable=False)  # e.g., "09:00"
    end_time: Mapped[str] = mapped_column(String, nullable=False)    # e.g., "17:00"
    assigned_tasks: Mapped[str] = mapped_column(Text, nullable=False)  # 할당된 작업 내용
    transport_info: Mapped[str] = mapped_column(Text, nullable=True)    # 교통 정보
    status: Mapped[str] = mapped_column(String, default="scheduled")  # scheduled, in_progress, completed, cancelled
    agent_notes: Mapped[str] = mapped_column(Text, nullable=True)     # Agent가 생성한 스케줄링 노트
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # 관계
    farm_application: Mapped["FarmApplication"] = relationship(back_populates="schedules")
    youth_application: Mapped["YouthApplication"] = relationship()


class AgentLog(Base):
    """Multi-Agent 시스템 실행 로그 - 디버깅 및 모니터링용."""
    
    __tablename__ = "agent_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)  # 세션 식별자
    farm_application_id: Mapped[int] = mapped_column(ForeignKey("farm_applications.id"), nullable=True)
    agent_type: Mapped[str] = mapped_column(String, nullable=False)  # farmer, planner, checker
    input_data: Mapped[str] = mapped_column(Text, nullable=True)     # Agent 입력 데이터
    output_data: Mapped[str] = mapped_column(Text, nullable=True)    # Agent 출력 데이터
    execution_time: Mapped[float] = mapped_column(Float, nullable=True)  # 실행 시간 (초)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Accommodation(Base):
    """숙박 정보 테이블 - TourAPI contentTypeId=32 데이터."""
    
    __tablename__ = "accommodations"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    region: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[str] = mapped_column(String, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=True)
    lon: Mapped[float] = mapped_column(Float, nullable=True)
    
    # TourAPI 관련 필드
    contentid: Mapped[str] = mapped_column(String, nullable=True)
    image_url: Mapped[str] = mapped_column(String, nullable=True)
    
    # 숙박 특화 정보
    checkin_time: Mapped[str] = mapped_column(String, nullable=True)  # 체크인 시간
    checkout_time: Mapped[str] = mapped_column(String, nullable=True)  # 체크아웃 시간
    room_count: Mapped[str] = mapped_column(String, nullable=True)    # 객실 수
    parking: Mapped[str] = mapped_column(String, nullable=True)       # 주차 정보
    facilities: Mapped[str] = mapped_column(Text, nullable=True)      # 부대시설
    
    # 검색 키워드
    detailed_keywords: Mapped[str] = mapped_column(Text, nullable=True)
    keywords: Mapped[str] = mapped_column(Text, nullable=True)
    
    # 1536차원 콘텐츠 벡터
    pref_vector: Mapped[list[float]] = Column(Vector(1536), nullable=True)


class Restaurant(Base):
    """음식점 정보 테이블 - TourAPI contentTypeId=39 데이터."""
    
    __tablename__ = "restaurants"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    region: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[str] = mapped_column(String, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=True)
    lon: Mapped[float] = mapped_column(Float, nullable=True)
    
    # TourAPI 관련 필드
    contentid: Mapped[str] = mapped_column(String, nullable=True)
    image_url: Mapped[str] = mapped_column(String, nullable=True)
    
    # 음식점 특화 정보
    menu: Mapped[str] = mapped_column(Text, nullable=True)            # 대표메뉴
    open_time: Mapped[str] = mapped_column(String, nullable=True)     # 영업시간
    rest_date: Mapped[str] = mapped_column(String, nullable=True)     # 휴무일
    parking: Mapped[str] = mapped_column(String, nullable=True)       # 주차 정보
    reservation: Mapped[str] = mapped_column(String, nullable=True)   # 예약 정보
    packaging: Mapped[str] = mapped_column(String, nullable=True)     # 포장 가능 여부
    
    # 검색 키워드
    detailed_keywords: Mapped[str] = mapped_column(Text, nullable=True)
    keywords: Mapped[str] = mapped_column(Text, nullable=True)
    
    # 1536차원 콘텐츠 벡터
    pref_vector: Mapped[list[float]] = Column(Vector(1536), nullable=True)


class Notification(Base):
    """알림 테이블 - 푸시 알림, 이메일, SMS 등 알림 내역."""
    
    __tablename__ = "notifications"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    recipient_contact: Mapped[str] = mapped_column(String, nullable=False)  # 이메일 또는 전화번호
    notification_type: Mapped[str] = mapped_column(String, nullable=False)  # push, email, sms, calendar
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    related_id: Mapped[int] = mapped_column(Integer, nullable=True)  # 관련 레코드 ID
    related_type: Mapped[str] = mapped_column(String, nullable=True)  # 관련 레코드 타입
    status: Mapped[str] = mapped_column(String, default="pending")  # pending, sent, failed
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # 관계
    user: Mapped["User"] = relationship()
