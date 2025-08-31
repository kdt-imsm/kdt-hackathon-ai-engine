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
from fastapi.middleware.cors import CORSMiddleware
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

# CORS 설정 (프론트엔드에서 API 접근 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인 허용 (개발용)
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메소드 허용
    allow_headers=["*"],  # 모든 헤더 허용
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
# System_Improvements.md: 벡터 유사도 기반 추천 시스템 -------------
# ─────────────────────────────────────────────────────────────

@app.post("/recommendations")
def get_demo_recommendations(
    request: dict = Body(...),
    db: Session = Depends(get_db),
):
    """
    System_Improvements.md 요구사항에 따른 추천 시스템
    
    요청 형식:
    {
        "natural_request": "9월 초에 2주 정도 전북 김제에서 과수원 체험하면서 힐링하고 싶어. 축제도 있으면 가보고 싶어.",
        "preferences": {
            "landscape_keywords": ["자연", "산"],
            "travel_style_keywords": ["체험", "힐링"],
            "job_type_keywords": ["과수", "채소"]
        }
    }
    
    응답: 전북 지역 필터링 + 농가 5개(JSON 기반) + 관광지 5개(벡터 기반) 추천
    """
    try:
        from app.services.demo_recommendation_service import get_demo_recommendation_service
        
        natural_request = request.get('natural_request', '')
        preferences = request.get('preferences', {})
        
        if not natural_request:
            raise HTTPException(status_code=400, detail="natural_request는 필수입니다.")
        
        print(f"📋 추천 요청: {natural_request[:50]}...")
        print(f"🎯 선호도: {preferences}")
        
        # System_Improvements.md: 농가는 간단한 JSON 기반, 관광지는 벡터 기반
        service = get_demo_recommendation_service()
        result = service.get_recommendations(natural_request, preferences)
        
        if result['status'] == 'error':
            raise HTTPException(status_code=400, detail=result['message'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 추천 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"추천 처리 중 오류가 발생했습니다: {str(e)}")


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
        # 1) 사용자 선호도 기반 검색 벡터 생성 (실제 서비스 로직)
        from app.embeddings.embedding_service import embed_texts
        from app.recommendation.user_matching import create_user_profile_from_preferences
        
        print(f"사용자 선호도: 지형={query.user_preferences.terrain_tags}, 활동={query.user_preferences.activity_style_tags}, 일자리={query.user_preferences.job_tags}")
        
        # 사용자 프로필 생성
        user_profile = create_user_profile_from_preferences(
            query.query,
            query.user_preferences.terrain_tags,
            query.user_preferences.activity_style_tags,
            query.user_preferences.job_tags
        )
        search_vector = user_profile['user_vector']
        
        # 검색 태그에 사용자 선호도 추가
        search_tags = []
        search_tags.extend(query.user_preferences.terrain_tags)
        search_tags.extend(query.user_preferences.activity_style_tags)
        search_tags.extend(query.user_preferences.job_tags)
        
        # 2) 슬롯 추출으로 자연어에서 구체적 정보 추출
        slots = extract_slots(query.query)
        print(f"추출된 슬롯: {slots}")
        
        # 3) 슬롯 정보와 사용자 선호도를 자연스럽게 결합한 검색 텍스트 생성
        search_components = [query.query]  # 원본 자연어 요청을 기본으로
        
        # 슬롯에서 추출된 활동 태그 추가 (자연어에서 나온 구체적 의도)
        if slots.get("activity_tags"):
            search_components.append(" ".join(slots["activity_tags"]))
            
        # 사용자 선호도 추가 (회원가입시 선택한 관심사)
        preference_text = " ".join(search_tags)
        if preference_text.strip():
            search_components.append(preference_text)
            
        # 추가 자연어 선호도 (Step 3에서 입력한 세부 취향)
        if query.user_preferences.preference_details:
            search_components.append(query.user_preferences.preference_details)
        
        # 자연스러운 문장으로 결합
        search_text = " ".join(search_components)
        
        print(f"검색 태그: {search_tags}")
        print(f"슬롯 활동태그: {slots.get('activity_tags', [])}")
        print(f"최종 검색 텍스트: {search_text}")
    
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
        print(f"🔍 API 추천 호출 디버깅:")
        print(f"   region_specified: {region_specified}")
        print(f"   region_filter: {slots.get('region_pref', []) if region_specified else None}")
        print(f"   activity_keywords: {extracted_keywords}")
        print(f"   search_vector 길이: {len(search_vector)}")
        
        try:
            intelligent_results = get_intelligent_recommendations(
                user_vector=search_vector,
                region_filter=slots.get("region_pref", []) if region_specified else None,
                activity_keywords=extracted_keywords,
                job_count=5,
                tour_count=20  # 이미지 필터링을 위해 더 많은 관광지 요청
            )
            print(f"✅ 지능적 추천 성공")
        except Exception as e:
            print(f"❌ 지능적 추천 실패: {e}")
            import traceback
            traceback.print_exc()
            intelligent_results = {"jobs": [], "tours": [], "system_diagnosis": {}}
        
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
        
        # 최종 tours_preview 생성 - 이미지가 있는 것만 선별
        tours_preview = []
        for tour_info in tour_data:
            contentid = tour_info['contentid']
            image_url = image_urls.get(contentid) if contentid else None
            
            # 이미지가 있는 경우만 추가
            if image_url:
                tours_preview.append({
                    "content_id": tour_info['content_id'],
                    "title": tour_info['title'],
                    "region": tour_info['region'],
                    "overview": tour_info['overview'],
                    "image_url": image_url,
                    "score": tour_info['score'],
                    "recommendation_reason": tour_info['recommendation_reason'],
                })
                
                # 최대 5개까지만 반환
                if len(tours_preview) >= 5:
                    break
        
        print(f"✅ 관광지 추천 완료: {len(tours_preview)}개 (이미지 필터링 적용)")

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
# System_Improvements.md: 간단한 일정 생성 시스템 -------------------------
# ─────────────────────────────────────────────────────────────

@app.post("/schedule")
def create_simple_schedule(
    request: dict = Body(...),
    db: Session = Depends(get_db),
):
    """
    System_Improvements.md 요구사항에 따른 간단한 일정 생성
    
    요청 형식:
    {
        "natural_request": "9월 초에 2주 정도 전북 김제에서 과수원 체험하면서 힐링하고 싶어",
        "selected_farm": {
            "farm_name": "김제 과수원",
            "start_time": "08:00",
            "end_time": "17:00",
            "address": "전북 김제시 만경읍"
        },
        "selected_tours": [
            {"tour_name": "벽골제", "address": "전북 김제시"},
            {"tour_name": "금산사", "address": "전북 김제시"}
        ],
        "preferences": {
            "landscape_keywords": ["자연", "산"],
            "travel_style_keywords": ["체험", "힐링"],
            "job_type_keywords": ["과수", "채소"]
        }
    }
    """
    try:
        from app.services.simple_schedule_service import get_simple_schedule_service
        
        natural_request = request.get('natural_request', '')
        selected_farm = request.get('selected_farm', {})
        selected_tours = request.get('selected_tours', [])
        preferences = request.get('preferences', {})
        
        if not natural_request:
            raise HTTPException(status_code=400, detail="natural_request는 필수입니다.")
        if not selected_farm:
            raise HTTPException(status_code=400, detail="selected_farm은 필수입니다.")
        
        print(f"📅 일정 생성 요청: {natural_request[:50]}...")
        print(f"🚜 선택 농가: {selected_farm.get('farm_name', '정보없음')}")
        print(f"🏞️ 선택 관광지: {len(selected_tours)}개")
        
        # 일정 생성 서비스 호출
        schedule_service = get_simple_schedule_service()
        result = schedule_service.create_schedule(
            natural_request=natural_request,
            selected_farm=selected_farm,
            selected_tours=selected_tours,
            preferences=preferences
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 일정 생성 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"일정 생성 중 오류가 발생했습니다: {str(e)}")


@app.post("/schedule/feedback")  
def update_schedule_feedback(
    request: dict = Body(...),
):
    """
    System_Improvements.md: 자연어 피드백으로 일정 수정
    
    요청 형식:
    {
        "session_id": "session_123",
        "feedback": "첫째 날은 너무 이른 시간이니까 오후로 바꿔줘",
        "current_schedule": { ... }
    }
    """
    try:
        from app.services.simple_schedule_service import get_simple_schedule_service
        
        session_id = request.get('session_id', 'default_session')
        feedback = request.get('feedback', '')
        current_schedule = request.get('current_schedule', {})
        
        if not feedback:
            raise HTTPException(status_code=400, detail="feedback은 필수입니다.")
        
        print(f"🔄 피드백 처리 요청: {feedback[:50]}...")
        
        # 피드백 처리 서비스 호출
        schedule_service = get_simple_schedule_service()
        result = schedule_service.update_schedule_with_feedback(
            session_id=session_id,
            feedback=feedback,
            current_schedule=current_schedule
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 피드백 처리 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"피드백 처리 중 오류가 발생했습니다: {str(e)}")


# ─────────────────────────────────────────────────────────────
# 4) 스마트 스케줄링 시스템 (일정 생성 전용) - 레거시
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
        
        # 1) 사용자 선호도 기반 프로필 생성 (실제 서비스 로직)
        from app.recommendation.user_matching import create_user_profile_from_preferences
        
        user_profile_info = create_user_profile_from_preferences(
            req.query,
            req.user_preferences.terrain_tags,
            req.user_preferences.activity_style_tags,
            req.user_preferences.job_tags
        )
        print(f"사용자 선호도: 지형={req.user_preferences.terrain_tags}, 활동={req.user_preferences.activity_style_tags}, 일자리={req.user_preferences.job_tags}")
        
        # 2) AI Agent를 위한 사용자 선호도 정리
        user_preferences_for_ai = {
            "terrain_tags": req.user_preferences.terrain_tags,
            "activity_style_tags": req.user_preferences.activity_style_tags,
            "job_tags": req.user_preferences.job_tags,
            "preference_details": req.user_preferences.preference_details
        }
        
        # 3) 추가 정보용: 슬롯 추출 (일정 생성 시 참고용)
        slots = extract_slots(req.query)
        
        # 3) 선택된 카드 정보 조회
        selected_jobs = []
        if req.selected_jobs:
            selected_jobs = crud.get_jobs_by_ids(db, req.selected_jobs)
            print(f"✅ 일거리 카드 조회 완료: {len(selected_jobs)}개")
        
        selected_tours = []
        if req.selected_tours:
            selected_tours = crud.get_tours_by_ids(db, req.selected_tours)
            print(f"✅ 관광지 카드 조회 완료: {len(selected_tours)}개")
        
        # 4) System_Improvements.md: 간단한 일정 생성 서비스 사용
        from app.services.simple_schedule_service import get_simple_schedule_service
        
        # 선택된 농가와 관광지 정보 변환
        selected_farm = selected_jobs[0] if selected_jobs else {}
        selected_tours_data = [
            {
                "tour_name": tour.name,
                "address": getattr(tour, 'address', ''),
                "contentid": getattr(tour, 'contentid', '')
            } for tour in selected_tours
        ]
        
        # 선호도 정보 변환
        preferences = {
            "landscape_keywords": req.user_preferences.terrain_tags,
            "travel_style_keywords": req.user_preferences.activity_style_tags,
            "job_type_keywords": req.user_preferences.job_tags
        }
        
        # 농가 정보 변환
        if selected_farm:
            selected_farm_data = {
                "farm_name": selected_farm.title,
                "start_time": getattr(selected_farm, 'start_time', '08:00'),
                "end_time": getattr(selected_farm, 'end_time', '17:00'),
                "address": getattr(selected_farm, 'address', '')
            }
        else:
            selected_farm_data = {}
        
        # 일정 생성 서비스 호출
        schedule_service = get_simple_schedule_service()
        scheduling_result = schedule_service.create_schedule(
            natural_request=req.query,
            selected_farm=selected_farm_data,
            selected_tours=selected_tours_data,
            preferences=preferences
        )
        
        # 응답 형식 변환 (기존 DetailedItineraryResponse 형식에 맞게)
        from app.schemas import DetailedItineraryResponse
        
        if scheduling_result.get('status') == 'success':
            schedule_data = scheduling_result.get('schedule', {})
            total_days = schedule_data.get('total_days', 0)
            
            response = DetailedItineraryResponse(
                success=True,
                total_days=total_days,
                natural_language_itinerary=scheduling_result.get('ai_response', ''),
                structured_itinerary=schedule_data.get('schedule', []),
                execution_time=1.0,
                processing_details={
                    "schedule_generation": "System_Improvements.md 규칙 적용",
                    "ai_agent": "GPT-4o 기반 일정 완성"
                }
            )
        else:
            response = DetailedItineraryResponse(
                success=False,
                error=scheduling_result.get('error', '일정 생성 실패')
            )
        
        print(f"🎉 일정 생성 완료!")
        print(f"   📅 총 {response.total_days}일 일정")
        
        return response
        
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
        
        # 2) System_Improvements.md: 간단한 피드백 처리
        from app.services.simple_schedule_service import get_simple_schedule_service
        
        # 현재 일정 데이터는 세션에서 가져와야 하지만, 임시로 기본 처리
        current_schedule = {}  # TODO: 세션 관리 구현 필요
        feedback_text = " ".join([mod.get('description', '') for mod in modifications])
        
        schedule_service = get_simple_schedule_service()
        updated_result = schedule_service.update_schedule_with_feedback(
            session_id=session_id,
            feedback=feedback_text,
            current_schedule=current_schedule
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

# ─────────────────────────────────────────────────────────────
#  Demo 전용 엔드포인트들 (DEMO_GUIDE.md 요구사항)
# ─────────────────────────────────────────────────────────────

from app.services.demo_service import DemoService

demo_service = DemoService()

@app.post("/demo/preferences", response_model=dict)
async def demo_preferences(
    keywords: List[str] = Body(..., description="선택된 선호 키워드들")
):
    """
    Demo용 선호도 키워드 저장
    - 실제로는 저장하지 않고 성공 응답만 반환
    """
    return {
        "success": True,
        "message": f"{len(keywords)}개의 선호 키워드가 저장되었습니다.",
        "keywords": keywords
    }

@app.post("/demo/slots", response_model=dict)
async def demo_slots(
    natural_query: str = Body(..., description="사용자 자연어 입력")
):
    """
    Demo용 자연어 슬롯 추출 및 카드 추천
    - 고정된 농가 5개와 관광지 5개(랜덤) 반환
    """
    try:
        # 고정된 농가 카드 5개
        job_cards = demo_service.get_demo_job_cards(5)
        
        # 관광지 카드 5개 (랜덤)
        tour_cards = demo_service.get_demo_tour_cards(5)
        
        return {
            "success": True,
            "natural_query": natural_query,
            "extracted_slots": {
                "period": "2주",
                "location": "전북 김제",
                "activities": ["과수원 체험", "힐링", "축제"],
                "preferences": ["체험형", "힐링"]
            },
            "job_cards": [card.dict() for card in job_cards],
            "tour_cards": [card.dict() for card in tour_cards],
            "total_jobs": len(job_cards),
            "total_tours": len(tour_cards)
        }
        
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print("Demo 슬롯 추출 오류:", tb)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/demo/itinerary", response_model=dict)
async def demo_itinerary(
    selected_jobs: List[str] = Body(..., description="선택된 농가 일자리 ID들"),
    selected_tours: List[str] = Body(..., description="선택된 관광지 ID들")
):
    """
    Demo용 고정 일정 생성
    - 2025-09-04 ~ 2025-09-19 고정 일정 반환
    """
    try:
        # 고정 일정 생성
        itinerary = demo_service.generate_demo_itinerary(selected_jobs, selected_tours)
        
        return {
            "success": True,
            "itinerary": itinerary.dict(),
            "message": "김제 과수원 체험과 힐링 여행 일정이 생성되었습니다."
        }
        
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print("Demo 일정 생성 오류:", tb)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/demo/accommodations", response_model=dict)
async def demo_accommodations():
    """
    Demo용 숙박시설 정보
    """
    return {
        "success": True,
        "accommodations": demo_service.demo_data["accommodations"]
    }

@app.get("/demo/restaurants", response_model=dict)
async def demo_restaurants():
    """
    Demo용 음식점 정보
    """
    return {
        "success": True,
        "restaurants": demo_service.demo_data["restaurants"]
    }
