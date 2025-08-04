"""
app/main.py
===========

FastAPI 진입점(애플리케이션 팩토리)

* 역할
  - DB 스키마를 초기화(없을 때만)하고 `FastAPI` 앱 객체를 생성합니다.
  - `/healthz` 헬스 체크, `/slots`(슬롯 추출 & 미리보기), `/recommend`(최종 일정 추천)
    세 개의 엔드포인트를 제공합니다.
  - 사용자 자연어 질의 → **슬롯 추출** → **벡터 기반 추천** → **일정 생성** 으로
    이어지는 전체 파이프라인의 HTTP 인터페이스를 담당합니다.

* 주요 구성 요소
  - **DB 의존성 주입**: `get_db` 의존성으로 요청마다 세션을 열고 자동 close.
  - **StaticFiles**: `/public` 경로에 정적 HTML 파일을 서빙하여 간단한 테스트 UI 지원.
  - **Slot Extraction**: `app.nlp.slot_extraction.extract_slots`
  - **Vector Search**: `app.recommendation.vector_store.search_jobs / search_tours`
  - **Itinerary Builder**: `app.recommendation.scheduler.build_itineraries`

* 실행
  ```bash
  uvicorn app.main:app --reload
  ```
"""

from pathlib import Path
from typing import List
from fastapi import FastAPI, Depends, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, engine, Base
from app.db import crud
from app.nlp.slot_extraction import extract_slots
from app.recommendation.scheduler import build_itineraries
from app.schemas import (
    SlotsResponse,
    SlotQuery,
    RecommendRequest,
    Itinerary,
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
    # 1) 자연어에서 슬롯(JSON) 추출 (GPT 기반)
    slots = extract_slots(query.query)

    # 2) 사용자 선호도 매칭 시스템 적용
    from app.recommendation.user_matching import get_best_matching_user, enhance_user_vector_with_preferences
    from app.embeddings.embedding_service import embed_texts
    
    # 가장 유사한 사용자 프로필 찾기
    matched_user_id, similarity_score, user_info = get_best_matching_user(
        query.query,
        slots["activity_tags"],
        slots["region_pref"]
    )
    
    print(f"매칭된 사용자: ID={matched_user_id}, 유사도={similarity_score:.3f}")
    print(f"사용자 선호도: 지형={user_info['terrain_tags']}, 활동={user_info['activity_tags']}")

    # 3) 선호도가 반영된 벡터 생성
    base_tags = slots["activity_tags"] + slots["region_pref"]
    merged_tags = base_tags + user_info['terrain_tags'] + user_info['activity_tags']

    # 4) 향상된 벡터 생성
    base_vector = embed_texts([" ".join(base_tags)])[0] if base_tags else embed_texts(["농업체험 자연"])[0]
    enhanced_vector = enhance_user_vector_with_preferences(base_vector, matched_user_id, 0.3)
    
    # 5) 보장된 10개 결과 검색
    from app.recommendation.vector_store import search_jobs_guaranteed, search_tours_guaranteed
    from app.utils.location import get_location_coords
    
    # 사용자 지역 선호도에서 좌표 추출
    user_coords = None
    if slots["region_pref"]:
        # 첫 번째 지역 선호도를 기준으로 좌표 설정
        region_name = slots["region_pref"][0]
        user_coords = get_location_coords(region_name)
        print(f"지역 '{region_name}'의 좌표: {user_coords}")
    
    # 5) 지역 명시 여부 판단
    from app.utils.location import is_region_specified, get_location_coords
    
    region_specified = is_region_specified(slots["region_pref"])
    print(f"🔍 지역 명시 여부: {region_specified}, 추출된 지역: {slots['region_pref']}")
    
    # 6) 일거리 검색 (지역 명시 여부에 따라 다른 전략)
    from app.recommendation.vector_store import (
        search_jobs_region_first, search_jobs_guaranteed,
        search_tours_region_first
    )
    
    if region_specified:
        print(f"🎯 지역 명시됨: {slots['region_pref']} - 지역 우선 검색 적용")
        
        jobs = search_jobs_region_first(
            enhanced_vector,
            user_regions=slots["region_pref"],
            user_coords=user_coords,
            target_count=10,
            max_distance_km=100.0,
            location_weight=0.4
        )
        
        # 🔥 NEW: 지역 명시 시 사용자 지정 지역에서만 관광지 검색
        print(f"🏞️ 관광지 검색 지역: 사용자지정={slots['region_pref']} (지역 명시로 제한)")
        
        tours = search_tours_region_first(
            enhanced_vector,
            user_regions=slots["region_pref"],  # 사용자 지정 지역만 사용
            user_coords=user_coords,
            target_count=10,
            max_distance_km=50.0,  # 관광지는 더 가까운 거리로 제한
            location_weight=0.5    # 위치 가중치 높임
        )
    else:
        print("🌍 지역 미명시 - 활동 태그 우선 전국 검색 적용")
        
        # 지역 제약 없이 활동 태그 기반 검색
        jobs = search_jobs_guaranteed(
            enhanced_vector,
            user_coords=None,  # 위치 제약 제거
            target_count=10,
            max_distance_km=1000.0,  # 전국 범위
            location_weight=0.1  # 위치 가중치 최소화
        )
        
        # 🔥 NEW: 일거리와 1:1 매칭되는 관광지 검색 (개선된 로직)
        job_regions = []
        for job, _ in jobs:  # 모든 일거리의 지역 추출
            job_regions.append(job.region if job.region else None)
        
        print(f"🏞️ 일거리 지역 리스트: {job_regions}")
        
        from app.recommendation.vector_store import search_tours_matching_jobs
        tours = search_tours_matching_jobs(
            enhanced_vector,
            job_regions=job_regions,  # 일거리와 동일한 순서로 지역 전달
            user_coords=None,
            max_distance_km=50.0,
            location_weight=0.3
        )
    
    print(f"검색 결과: 일거리 {len(jobs)}개, 관광지 {len(tours)}개")
    
    # 지역 분포 분석 로그
    job_regions = {}
    for job, _ in jobs:
        region = job.region if job.region else "지역정보없음"
        job_regions[region] = job_regions.get(region, 0) + 1
    
    tour_regions = {}
    for tour, _ in tours:
        region = tour.region if hasattr(tour, 'region') and tour.region else "지역정보없음"
        tour_regions[region] = tour_regions.get(region, 0) + 1
    
    print("📊 일거리 지역 분포:", dict(sorted(job_regions.items(), key=lambda x: x[1], reverse=True)))
    print("📊 관광지 지역 분포:", dict(sorted(tour_regions.items(), key=lambda x: x[1], reverse=True)))

    # 5) 중복 제거 및 Preview DTO 변환 + 실시간 이미지 수집
    # 🔥 NEW: 일거리 중복 제거 및 10개 보장
    seen_job_ids = set()
    unique_jobs = []
    for job, score in jobs:
        if job.id not in seen_job_ids:
            unique_jobs.append((job, score))
            seen_job_ids.add(job.id)
        if len(unique_jobs) >= 10:  # 10개 달성하면 중단
            break
    
    # 10개 미만이면 추가 검색으로 보충
    if len(unique_jobs) < 10:
        print(f"⚠️ 일거리 부족 ({len(unique_jobs)}개) - 추가 검색으로 보충")
        from app.recommendation.vector_store import search_jobs
        additional_jobs = search_jobs(enhanced_vector, limit=50)  # 더 많이 검색
        
        for job, score in additional_jobs:
            if job.id not in seen_job_ids:
                unique_jobs.append((job, score))
                seen_job_ids.add(job.id)
                if len(unique_jobs) >= 10:
                    break
    
    jobs_preview = [
        {
            "job_id": job.id,
            "farm_name": job.title,
            "region": job.region if hasattr(job, 'region') and job.region else "지역정보없음",
            "tags": job.tags.split(",") if isinstance(job.tags, str) else job.tags,
        }
        for job, _ in unique_jobs
    ]
    
    # 🔥 NEW: 온디맨드 이미지 수집
    from app.utils.image_service import get_image_service
    image_service = get_image_service()
    
    # 🔥 NEW: 관광지 중복 제거 (개선된 search_tours_matching_jobs 함수가 이미 순서를 보장)
    seen_tour_ids = set()
    unique_tours = []
    
    if not region_specified:
        print(f"🎯 지역 미명시 - 개선된 순서 매칭 로직 적용 완료")
        # search_tours_matching_jobs 함수가 이미 순서를 보장하므로 단순히 중복만 제거
        for tour, score in tours:
            if tour.id not in seen_tour_ids:
                unique_tours.append((tour, score))
                seen_tour_ids.add(tour.id)
                if len(unique_tours) >= 10:
                    break
    else:
        # 지역 명시 시: 기존 로직 (점수순 정렬)
        for tour, score in tours:
            if tour.id not in seen_tour_ids:
                unique_tours.append((tour, score))
                seen_tour_ids.add(tour.id)
                if len(unique_tours) >= 10:
                    break
        
        unique_tours.sort(key=lambda x: x[1], reverse=True)
    
    # 10개 미만이면 추가 검색으로 보충
    if len(unique_tours) < 10:
        print(f"⚠️ 관광지 부족 ({len(unique_tours)}개) - 추가 검색으로 보충")
        from app.recommendation.vector_store import search_tours
        additional_tours = search_tours(enhanced_vector, limit=50)  # 더 많이 검색
        
        for tour, score in additional_tours:
            if tour.id not in seen_tour_ids:
                unique_tours.append((tour, score))
                seen_tour_ids.add(tour.id)
                if len(unique_tours) >= 10:
                    break
    
    # 관광지 정보 추출
    tour_data = []
    for tour, score in unique_tours:
        tour_info = {
            "content_id": tour.id,
            "title": tour.name,
            "region": tour.region if hasattr(tour, 'region') and tour.region else "지역정보없음",
            "overview": (", ".join(tour.tags.split(","))
                         if isinstance(tour.tags, str)
                         else " ".join(tour.tags)),
            "contentid": getattr(tour, 'contentid', ''),
            "score": score,  # 디버깅용
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
            "image_url": image_url,  # 🔥 실시간 수집된 이미지 URL
        })

    return SlotsResponse(
        slots=slots,
        jobs_preview=jobs_preview,
        tours_preview=tours_preview,
    )


# ─────────────────────────────────────────────────────────────
# 2) 최종 추천 → 일정 생성 ----------------------------------------
# ─────────────────────────────────────────────────────────────

@app.post("/recommend", response_model=List[Itinerary])
def recommend(
    req: RecommendRequest = Body(...),
    db: Session = Depends(get_db),
):
    """최종 선택/예산 반영 → 일정(Itinerary) 목록 반환."""
    try:
        # 1) 자연어에서 슬롯 재추출 (idempotent)
        slots = extract_slots(req.query)

        # 2) 동일한 사용자 선호도 매칭 로직 적용
        from app.recommendation.user_matching import get_best_matching_user, enhance_user_vector_with_preferences
        from app.embeddings.embedding_service import embed_texts
        
        matched_user_id, similarity_score, user_info = get_best_matching_user(
            req.query,
            slots["activity_tags"], 
            slots["region_pref"]
        )
        
        base_tags = slots["activity_tags"] + slots["region_pref"]
        base_vector = embed_texts([" ".join(base_tags)])[0] if base_tags else embed_texts(["농업체험 자연"])[0]
        enhanced_vector = enhance_user_vector_with_preferences(base_vector, matched_user_id, 0.3)

        # 3) 지역 명시 여부 판단
        from app.utils.location import is_region_specified, get_location_coords
        
        region_specified = is_region_specified(slots["region_pref"])
        print(f"🔍 추천 단계 - 지역 명시 여부: {region_specified}, 추출된 지역: {slots['region_pref']}")

        # 사용자 지역 선호도에서 좌표 추출 
        user_coords = None
        if region_specified and slots["region_pref"]:
            region_name = slots["region_pref"][0]
            user_coords = get_location_coords(region_name)
            print(f"추천 단계 - 지역 '{region_name}'의 좌표: {user_coords}")

        # 4) 사용자가 선택한 카드가 있으면 우선, 없으면 Top10
        if req.selected_jobs:
            ranked_jobs = crud.get_jobs_by_ids(db, req.selected_jobs)
        else:
            # 지역 명시 여부에 따른 검색 전략
            if region_specified:
                print(f"🎯 추천 단계 - 지역 우선 검색: {slots['region_pref']}")
                from app.recommendation.vector_store import search_jobs_region_first
                job_results = search_jobs_region_first(
                    enhanced_vector,
                    user_regions=slots["region_pref"],
                    user_coords=user_coords,
                    target_count=10,
                    max_distance_km=100.0,
                    location_weight=0.4
                )
            else:
                print("🌍 추천 단계 - 활동 태그 우선 전국 검색")
                from app.recommendation.vector_store import search_jobs_guaranteed
                job_results = search_jobs_guaranteed(
                    enhanced_vector,
                    user_coords=None,
                    target_count=10,
                    max_distance_km=1000.0,
                    location_weight=0.1
                )
            ranked_jobs = [job for job, _ in job_results]

        if req.selected_tours:
            ranked_tours = crud.get_tours_by_ids(db, req.selected_tours)
        else:
            # 관광지 검색 전략
            if region_specified:
                from app.recommendation.vector_store import search_tours_region_first
                
                # 🔥 NEW: 지역 명시 시 사용자 지정 지역에서만 관광지 검색
                print(f"🏞️ 최종 관광지 검색 지역: 사용자지정={slots['region_pref']} (지역 명시로 제한)")
                
                tour_results = search_tours_region_first(
                    enhanced_vector,
                    user_regions=slots["region_pref"],  # 사용자 지정 지역만 사용
                    user_coords=user_coords,
                    target_count=10,
                    max_distance_km=50.0,  # 더 엄격한 거리 제한
                    location_weight=0.5
                )
            else:
                # 🔥 NEW: 지역 미명시 시 일거리와 1:1 매칭되는 관광지 검색
                job_regions = []
                if req.selected_jobs:
                    selected_jobs = crud.get_jobs_by_ids(db, req.selected_jobs)
                    for job in selected_jobs:
                        job_regions.append(job.region if job.region else None)
                else:
                    for job in ranked_jobs:
                        job_regions.append(job.region if job.region else None)
                
                print(f"🏞️ 일거리 지역 리스트: {job_regions}")
                
                from app.recommendation.vector_store import search_tours_matching_jobs
                tour_results = search_tours_matching_jobs(
                    enhanced_vector,
                    job_regions=job_regions,  # 일거리와 동일한 순서로 지역 전달
                    user_coords=None,
                    max_distance_km=50.0,
                    location_weight=0.3
                )
            
            ranked_tours = [tour for tour, _ in tour_results] if tour_results else []

        # 5) 일정 생성기 호출
        itineraries = build_itineraries(
            slots,
            ranked_jobs,
            ranked_tours,
            req.budget,
        )
        print("build_itineraries 반환값:", itineraries)
        return itineraries

    except Exception as e:
        import traceback, sys

        tb = traceback.format_exc()
        print("/recommend 예외 발생:\n", tb, file=sys.stderr)
        raise HTTPException(status_code=500, detail=tb)
