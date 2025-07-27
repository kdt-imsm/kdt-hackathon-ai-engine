"""
app/main.py
~~~~~~~~~~~
FastAPI 애플리케이션 엔트리포인트.

* /public/*        ―  React·HTML 등 프론트 정적 파일
* /docs, /redoc    ―  자동 생성 API 문서
* /healthz         ―  헬스 체크
* /recommend       ―  자연어 조건 → 맞춤 일정 JSON
"""

from pathlib import Path
from typing import List

from fastapi import FastAPI, Depends, HTTPException, Body
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, engine, Base
from app.db import models
from app.recommendation.ranking import rank_personalized
from app.recommendation.scheduler import build_itineraries
from app.nlp.slot_extraction import extract_slots
from app.schemas import RecommendationRequest, Itinerary

# ─────────────────────────────────────────────────────────────
# DB 테이블이 아직 없다면 생성
Base.metadata.create_all(bind=engine)

# FastAPI 앱 생성
app = FastAPI(
    title="Rural Planner API",
    description="농촌 일자리 + 관광 맞춤 일정 추천 서비스",
    version="0.1.0",
)

# public/ 정적 파일 서빙
BASE_DIR = Path(__file__).resolve().parent.parent
app.mount(
    "/public",
    StaticFiles(directory=BASE_DIR / "public", html=True),
    name="public",
)

# ─────────────────────────────────────────────────────────────
# 공통 DB 세션 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 헬스 체크
@app.get("/healthz")
def healthz():
    return {"status": "ok"}

# 추천 API: 자연어 조건 → 일정 JSON
@app.post("/recommend", response_model=List[Itinerary])
def recommend(req: RecommendationRequest = Body(...), db: Session = Depends(get_db)):
    """
    1. GPT-4o-mini → 슬롯(JSON) 추출
    2. JobPost / TourSpot 개인화 랭킹
    3. 이동 거리·예산 균형으로 다중 일정 생성
    """
    try:
        slots = extract_slots(req.query)
        ranked_jobs, ranked_spots = rank_personalized(slots, req.user_id, db)
        itineraries = build_itineraries(slots, ranked_jobs, ranked_spots, req.budget)
        return itineraries
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
