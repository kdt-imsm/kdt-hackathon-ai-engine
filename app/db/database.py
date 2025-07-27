"""
database.py
~~~~~~~~~~~
PostgreSQL 연결 및 pgvector 확장 확인/생성.
SQLAlchemy 2.x Engine + Sessionmaker 제공.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.postgres_uri, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)

class Base(DeclarativeBase):
    """모든 ORM 모델의 베이스 클래스."""
    pass


# pgvector 확장 설치 (최초 1회)
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()
