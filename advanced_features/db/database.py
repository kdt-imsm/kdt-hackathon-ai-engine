"""
app/db/database.py
==================
PostgreSQL + pgvector 데이터베이스 초기화 및 SQLAlchemy 세션 팩토리

주요 기능
---------
1. **create_engine**
   * `settings.postgres_uri` 를 기반으로 SQLAlchemy 2.x Engine 생성.
   * `pool_pre_ping=True` 로 연결 상태를 주기적으로 확인해 *stale connection*
     오류를 방지합니다.

2. **SessionLocal**
   * `sessionmaker` 로 정의된 DB 세션 팩토리.
   * FastAPI 의존성(`Depends`)에서 `SessionLocal()` 사용.

3. **DeclarativeBase 서브클래스(Base)**
   * 모든 ORM 모델이 상속할 공통 베이스.

4. **pgvector EXTENSION 보증**
   * 애플리케이션 시작 시 `CREATE EXTENSION IF NOT EXISTS vector` 쿼리를 실행해
     pgvector가 없을 경우 자동으로 설치합니다.

사용 예시
~~~~~~~~~
```python
from sqlalchemy.orm import Session
from app.db.database import SessionLocal

with SessionLocal() as db:  # context 관리도 가능
    users = db.query(User).all()
```
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import get_settings

# ─────────────────────────────────────────────────────────────
# 환경 설정 로드 (.env)
# ─────────────────────────────────────────────────────────────
settings = get_settings()

# ─────────────────────────────────────────────────────────────
# SQLAlchemy Engine & Sessionmaker
# ─────────────────────────────────────────────────────────────
engine = create_engine(
    settings.postgres_uri,  # 예: postgresql+psycopg2://user:pwd@host/db
    echo=False,            # SQL 디버깅 로그 비활성화
    pool_pre_ping=True,    # 커넥션 풀에서 사전 ping → dead connection 방지
)

# autoflush=False → 명시적 db.commit() 호출 전에는 플러시하지 않음
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """모든 ORM 모델이 상속해야 할 Declarative Base 클래스."""

    pass


# ─────────────────────────────────────────────────────────────
# pgvector 확장 설치(최초 1회) --------------------------------
# ─────────────────────────────────────────────────────────────
try:
    with engine.connect() as conn:
        # `IF NOT EXISTS` 로 idempotent 하게 실행
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
except Exception as e:
    print(f"⚠️ pgvector 확장 설치 실패 (데모에서는 무시): {e}")

# ─────────────────────────────────────────────────────────────
# DB 세션 의존성 함수 (FastAPI Depends용)
# ─────────────────────────────────────────────────────────────
def get_db_session():
    """요청마다 독립적인 SQLAlchemy 세션을 제공하고 종료합니다."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
