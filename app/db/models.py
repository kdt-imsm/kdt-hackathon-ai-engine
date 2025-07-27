"""
models.py
~~~~~~~~~
ORM 테이블 정의.
* User(선호 벡터)
* Tag(사전 정의 태그)
* JobPost(농가 일거리)
* TourSpot(관광지)
* Feedback(사용자 피드백)
"""

from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.db.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    # 768-dim 벡터 → text-embedding-3-small default
    pref_vector = Column(Vector(1536))

    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="user")


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


class JobPost(Base):
    __tablename__ = "job_posts"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    region = Column(String, nullable=False)
    tags = Column(String, nullable=False)
    lat = Column(Float)
    lon = Column(Float)
    wage = Column(Integer)

    # ★ 임베딩 벡터 (1536 차원 예시) -------------
    pref_vector = Column(Vector(1536), nullable=True)


class TourSpot(Base):
    __tablename__ = "tour_spots"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    region: Mapped[str]
    tags: Mapped[str]
    lat: Mapped[float]
    lon: Mapped[float]

    pref_vector = Column(Vector(1536), nullable=True)


class Feedback(Base):
    __tablename__ = "feedbacks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content_id: Mapped[int]  # JobPost or TourSpot id
    content_type: Mapped[str]  # "job" or "tour"
    score: Mapped[float]       # +1 like, -1 dislike

    user: Mapped["User"] = relationship(back_populates="feedbacks")
