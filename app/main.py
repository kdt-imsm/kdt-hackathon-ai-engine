"""
app/main.py
===========

FastAPI 진입점(애플리케이션 팩토리)

* 역할
  - DB 스키마를 초기화(없을 때만)하고 `FastAPI` 앱 객체를 생성합니다.
  - `/healthz` 헬스 체크, `/slots`(슬롯 추출 & 미리보기), `/smart-schedule`(GPT-4o Agent 기반 일정 생성)
    세 개의 핵심 엔드포인트를 제공합니다.
  - 사용자 자연어 질의 → **슬롯 추출** → **벡터 기반 추천** → **일정 생성** 으로
    이어지는 전체 파이프라인의 HTTP 인터페이스를 담당합니다.

* 주요 구성 요소
  - **DB 의존성 주입**: `get_db` 의존성으로 요청마다 세션을 열고 자동 close.
  - **StaticFiles**: `/public` 경로에 정적 HTML 파일을 서빙하여 간단한 테스트 UI 지원.
  - **Slot Extraction**: `app.nlp.slot_extraction.extract_slots`
  - **Vector Search**: `app.recommendation.vector_store.search_jobs / search_tours`
  - **Smart Scheduling**: `app.agents.smart_scheduling_orchestrator` (GPT-4o Agent 기반)

* 실행
  ```bash
  uvicorn app.main:app --reload
  ```
"""

from pathlib import Path
from typing import List
from fastapi import FastAPI, Depends, HTTPException, Body, Request
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, engine, Base
from app.db import crud
from app.nlp.slot_extraction import extract_slots
from app.schemas import (
    SlotsResponse,
    SlotQuery,
    RecommendRequest,
    Itinerary,
    DetailedItineraryResponse,  # 자연어 일정 응답 모델
    ItineraryFeedbackRequest,   # 일정 피드백 요청 스키마
    ItineraryFeedbackResponse,  # 일정 피드백 응답 스키마
)

# ─────────────────────────────────────────────────────────────
#  DB 테이블이 없는 경우(create_all) → 로컬 개발·시연 환경 편의
# ─────────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# FastAPI 앱 인스턴스 생성 --------------------------------------------------
app = FastAPI(
    title="Rural Planner API",
    description="농촌 일자리 + 관광 맞춤 일정 추천 서비스",
    version="0.1.0",
)

# 422 오류 상세 디버깅을 위한 예외 처리기
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = await request.body()
    print(f"❌ 요청 검증 실패: {request.method} {request.url}")
    print(f"   오류 상세: {exc.errors()}")
    print(f"   요청 본문: {body.decode('utf-8') if body else 'empty'}")
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "message": "요청 데이터 검증 실패",
            "url": str(request.url)
        }
    )

# public/ 폴더의 정적 파일(html, css 등) 서빙 -------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
app.mount(
    "/public",
    StaticFiles(directory=BASE_DIR / "public", html=True),
    name="public",
)

# ─────────────────────────────────────────────────────────────
# DB 세션 의존성 (요청 스코프)
# ─────────────────────────────────────────────────────────────

def get_db():
    """요청마다 독립적인 SQLAlchemy 세션을 제공하고 종료합니다."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 헬스 체크 --------------------------------------------------
@app.get("/healthz")
def healthz():
    """Kubernetes 등 상태 확인용 엔드포인트."""
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────
# 1) 슬롯 추출 + 카드 10개 미리보기 ----------------------------------------
# ─────────────────────────────────────────────────────────────

@app.post("/slots", response_model=SlotsResponse)
def get_slots_preview(
    query: SlotQuery = Body(...),
    db: Session = Depends(get_db),
):
    """사용자 자연어 → 슬롯 추출 + Job/Tour 카드 10개씩 미리보기 반환."""
    try:
        # 1) 자연어에서 슬롯(JSON) 추출 (GPT 기반)
        slots = extract_slots(query.query)

        # 2) 검색용 벡터 생성 (순수 슬롯 기반)
        from app.embeddings.embedding_service import embed_texts
        
        search_tags = []
        if slots.get("activity_tags"):
            search_tags.extend(slots["activity_tags"])
        if slots.get("region_pref"):
            search_tags.extend(slots["region_pref"])
        if slots.get("terrain_pref"):
            search_tags.extend(slots["terrain_pref"])
            
        # 기본 검색 벡터 생성
        search_text = " ".join(search_tags) if search_tags else query.query
        search_vector = embed_texts([search_text])[0]
        
        print(f"검색 태그: {search_tags}")
        print(f"검색 텍스트: {search_text}")
    
        # 3) 지역 좌표 추출
        from app.utils.location import get_location_coords, is_region_specified
        
        user_coords = None
        if slots.get("region_pref") and slots["region_pref"]:
            region_name = slots["region_pref"][0]
            user_coords = get_location_coords(region_name)
            print(f"지역 '{region_name}'의 좌표: {user_coords}")
        
        # 4) 지역 명시 여부 판단
        region_specified = is_region_specified(slots.get("region_pref", []))
        print(f"지역 명시 여부: {region_specified}, 추출된 지역: {slots.get('region_pref', [])}")
        
        # 5) 검색용 키워드 준비 (순수 슬롯 기반)
        extracted_keywords = []
        if slots.get("activity_tags"):
            extracted_keywords.extend(slots["activity_tags"])
        if slots.get("terrain_pref"):
            extracted_keywords.extend(slots["terrain_pref"])
        if slots.get("region_pref"):
            extracted_keywords.extend(slots["region_pref"])
            
        print(f"검색 키워드: {extracted_keywords}")
        
        # 6) 지능적 추천 시스템 적용
        from app.recommendation.intelligent_recommender import get_intelligent_recommendations
        
        print(f"지능적 추천 시스템 시작")
        print(f"   지역 명시 여부: {region_specified}")
        print(f"   대상 지역: {slots.get('region_pref', [])}")
        print(f"   키워드: {extracted_keywords}")
        
        # 통합 지능적 추천 호출
        intelligent_results = get_intelligent_recommendations(
            user_vector=search_vector,
            region_filter=slots.get("region_pref", []) if region_specified else None,
            activity_keywords=extracted_keywords,
            job_count=5,
            tour_count=5
        )
        
        # 결과 분리
        jobs = intelligent_results["jobs"]  # [(JobPost, score, reason), ...]
        tours = intelligent_results["tours"]  # [(TourSpot, score, reason), ...]
        
        # 시스템 진단 정보 출력
        diagnosis = intelligent_results.get("system_diagnosis", {})
        print(f"시스템 진단:")
        print(f"   총 일거리: {diagnosis.get('총_일거리', 0)}개")
        print(f"   총 관광지: {diagnosis.get('총_관광지', 0)}개")
        
        # 추천 이유 설명
        explanation = intelligent_results.get("explanation", {})
        print(f"추천 방식:")
        print(f"   일거리: {explanation.get('job_scoring', '정보없음')}")
        print(f"   관광지: {explanation.get('tour_scoring', '정보없음')}")
        print(f"   지역확장: {explanation.get('region_expansion', '정보없음')}")
        
        print(f"검색 결과: 일거리 {len(jobs)}개, 관광지 {len(tours)}개")
        
        # 지역 분포 분석 로그
        job_regions = {}
        for job, _, _ in jobs:
            region = job.region if job.region else "지역정보없음"
            job_regions[region] = job_regions.get(region, 0) + 1
        
        tour_regions = {}
        for tour_result in tours:
            if len(tour_result) >= 2:
                tour = tour_result[0]
                region = tour.region if hasattr(tour, 'region') and tour.region else "지역정보없음"
                tour_regions[region] = tour_regions.get(region, 0) + 1
        
        print("일거리 지역 분포:", dict(sorted(job_regions.items(), key=lambda x: x[1], reverse=True)))
        print("관광지 지역 분포:", dict(sorted(tour_regions.items(), key=lambda x: x[1], reverse=True)))

        # 5) 지능적 추천 결과 처리
        # jobs = [(JobPost, score, reason), ...]
        jobs_preview = []
        for job, score, reason in jobs:
            jobs_preview.append({
                "job_id": job.id,
                "farm_name": job.title,
                "region": job.region if hasattr(job, 'region') and job.region else "지역정보없음",
                "tags": job.tags.split(",") if isinstance(job.tags, str) else job.tags,
                "score": score,
                "recommendation_reason": reason
            })
        
        print(f"✅ 일거리 추천 완료: {len(jobs_preview)}개")
    
        # 온디맨드 이미지 수집
        from app.utils.image_service import get_image_service
        image_service = get_image_service()
    
        # 지능적 추천 관광지 결과 처리
        # tours = [(TourSpot, score, reason), ...]
        tour_data = []
        print(f"지능적 관광지 결과 처리 시작: {len(tours)}개")
        
        for tour, score, reason in tours:
            tour_info = {
                "content_id": tour.id,
                "title": tour.name,
                "region": tour.region if hasattr(tour, 'region') and tour.region else "지역정보없음",
                "overview": (", ".join(tour.tags.split(","))
                             if isinstance(tour.tags, str)
                             else " ".join(tour.tags)),
                "contentid": getattr(tour, 'contentid', ''),
                "score": score,
                "recommendation_reason": reason,
            }
            tour_data.append(tour_info)
        
        # 배치로 이미지 수집
        contentids = [t['contentid'] for t in tour_data if t['contentid']]
        tour_names = [t['title'] for t in tour_data if t['contentid']]
        
        if contentids:
            image_urls = image_service.get_images_batch(contentids, tour_names)
        else:
            image_urls = {}
        
        # 최종 tours_preview 생성
        tours_preview = []
        for tour_info in tour_data:
            contentid = tour_info['contentid']
            image_url = image_urls.get(contentid) if contentid else None
            
            tours_preview.append({
                "content_id": tour_info['content_id'],
                "title": tour_info['title'],
                "region": tour_info['region'],
                "overview": tour_info['overview'],
                "image_url": image_url,
                "score": tour_info['score'],
                "recommendation_reason": tour_info['recommendation_reason'],
            })
        
        print(f"✅ 관광지 추천 완료: {len(tours_preview)}개")

        return SlotsResponse(
            success=True,
            slots=slots,
            jobs_preview=jobs_preview,
            tours_preview=tours_preview,
        )
        
    except Exception as e:
        import traceback
        error_msg = f"슬롯 추출 중 오류 발생: {str(e)}"
        print(f"❌ {error_msg}")
        print(traceback.format_exc())
        
        return SlotsResponse(
            success=False,
            slots={},
            jobs_preview=[],
            tours_preview=[],
            error=error_msg
        )




# ─────────────────────────────────────────────────────────────
# 3) 키워드 검색 API (한국관광공사 searchKeyword2 프록시)
# ─────────────────────────────────────────────────────────────

@app.get("/searchKeyword2")
def search_keyword(
    keyword: str,
    pageNo: int = 1,
    numOfRows: int = 10,
):
    """한국관광공사 searchKeyword2 API를 프록시하여 키워드 기반 관광지 검색 제공."""
    from app.utils.keyword_search import get_keyword_service
    
    try:
        keyword_service = get_keyword_service()
        results = keyword_service.search_by_keyword(keyword, max_results=numOfRows)
        
        # TourAPI 응답 형식과 유사하게 변환
        items = []
        for result in results:
            items.append({
                "contentid": result.contentid,
                "title": result.title,
                "keywords": result.keywords,
                "relevance_score": result.relevance_score
            })
        
        return {
            "response": {
                "header": {
                    "resultCode": "0000",
                    "resultMsg": "OK"
                },
                "body": {
                    "items": {
                        "item": items
                    },
                    "numOfRows": numOfRows,
                    "pageNo": pageNo,
                    "totalCount": len(items)
                }
            }
        }
        
    except Exception as e:
        print(f"searchKeyword2 API 오류: {e}")
        return {
            "response": {
                "header": {
                    "resultCode": "9999",
                    "resultMsg": f"API 호출 실패: {str(e)}"
                },
                "body": {
                    "items": {"item": []},
                    "numOfRows": numOfRows,
                    "pageNo": pageNo,
                    "totalCount": 0
                }
            }
        }


# ─────────────────────────────────────────────────────────────
# 4) 스마트 스케줄링 시스템 (일정 생성 전용)
# ─────────────────────────────────────────────────────────────

@app.post("/smart-schedule", response_model=DetailedItineraryResponse)
def create_smart_schedule(
    req: RecommendRequest = Body(...),
    db: Session = Depends(get_db),
):
    """선택된 카드 기반 지능형 일정 생성 시스템 (GPT-4o Agent 활용)."""
    try:
        print(f"스마트 스케줄링 요청 시작")
        print(f"   요청 데이터: {req.dict()}")
        print(f"   쿼리: {req.query}")
        print(f"   선택 일거리: {len(req.selected_jobs)}개")
        print(f"   선택 관광지: {len(req.selected_tours)}개")
        
        # 1) 자연어에서 슬롯 재추출
        slots = extract_slots(req.query)
        
        # 2) 사용자 선호도 매칭 (기존 로직 재사용)
        from app.recommendation.user_matching import get_best_matching_user, enhance_user_vector_with_preferences
        from app.embeddings.embedding_service import embed_texts
        
        matched_user_id, similarity_score, user_info = get_best_matching_user(
            req.query,
            slots["activity_tags"], 
            slots["region_pref"]
        )
        
        print(f"매칭된 사용자: ID={matched_user_id}, 유사도={similarity_score:.3f}")
        
        # 3) 선택된 카드 정보 조회
        selected_jobs = []
        if req.selected_jobs:
            selected_jobs = crud.get_jobs_by_ids(db, req.selected_jobs)
            print(f"✅ 일거리 카드 조회 완료: {len(selected_jobs)}개")
        
        selected_tours = []
        if req.selected_tours:
            selected_tours = crud.get_tours_by_ids(db, req.selected_tours)
            print(f"✅ 관광지 카드 조회 완료: {len(selected_tours)}개")
        
        # 4) Multi-Agent 시스템을 활용한 지능형 일정 생성
        from app.agents.smart_scheduling_orchestrator import SmartSchedulingOrchestrator
        
        orchestrator = SmartSchedulingOrchestrator(db)
        scheduling_result = orchestrator.create_optimized_itinerary(
            slots=slots,
            selected_jobs=selected_jobs,
            selected_tours=selected_tours,
            user_query=req.query,
            user_preferences=user_info
        )
        
        print(f"🎉 스마트 스케줄링 완료!")
        print(f"   📅 총 {scheduling_result.total_days}일 일정")
        
        return scheduling_result
        
    except Exception as e:
        import traceback, sys
        
        tb = traceback.format_exc()
        print("스마트 스케줄링 예외 발생:\n", tb, file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"스마트 스케줄링 실패: {str(e)}")


@app.post("/itinerary/feedback", response_model=ItineraryFeedbackResponse)
def update_itinerary_feedback(
    req: ItineraryFeedbackRequest = Body(...),
    db: Session = Depends(get_db),
):
    """일정 피드백 및 실시간 재최적화 시스템."""
    try:
        print(f"일정 피드백 처리 시작")
        
        # 1) 피드백 데이터 파싱
        session_id = req.session_id
        modifications = [mod.dict() for mod in req.modifications]
        user_preferences = req.user_preferences or {}
        
        print(f"   세션 ID: {session_id}")
        print(f"   수정사항: {len(modifications)}개")
        
        # 2) Multi-Agent 시스템을 활용한 일정 재최적화
        from app.agents.smart_scheduling_orchestrator import SmartSchedulingOrchestrator
        
        orchestrator = SmartSchedulingOrchestrator(db)
        updated_result = orchestrator.reoptimize_itinerary(
            session_id=session_id,
            modifications=modifications,
            user_preferences=user_preferences
        )
        
        print(f"✅ 일정 재최적화 완료")
        
        return ItineraryFeedbackResponse(
            success=True,
            updated_itinerary=updated_result.get("natural_language_itinerary", ""),
            changes_summary=updated_result.get("changes_summary", []),
            execution_time=updated_result.get("execution_time", 0)
        )
        
    except Exception as e:
        import traceback
        
        tb = traceback.format_exc()
        print("일정 피드백 처리 예외:", tb)
        return ItineraryFeedbackResponse(
            success=False,
            error=str(e),
            traceback=tb
        )
