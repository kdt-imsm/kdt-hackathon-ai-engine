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

from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.db.database import Base


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
    title: Mapped[str] = mapped_column(String, nullable=False)
    region: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "조개잡이,갯벌체험"
    lat: Mapped[float] = mapped_column(Float, nullable=True)
    lon: Mapped[float] = mapped_column(Float, nullable=True)
    wage: Mapped[int] = mapped_column(Integer, nullable=True)

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
    
    # 🔥 NEW: TourAPI contentid 및 이미지 URL 필드 추가
    contentid: Mapped[str] = mapped_column(String, nullable=True)  # TourAPI contentid
    image_url: Mapped[str] = mapped_column(String, nullable=True)  # 대표 이미지 URL

    # 1536차원 콘텐츠 벡터
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
