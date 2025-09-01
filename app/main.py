"""
단순화된 FastAPI 메인 애플리케이션
전북 지역 농촌 일여행 추천 및 일정 생성 API
"""

from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from pathlib import Path
from typing import Dict, List, Any

from app.services.simple_recommendation_service import get_simple_recommendation_service
from app.services.simple_scheduling_service import get_simple_scheduling_service
from app.schemas.user_schemas import OnboardingRequest, BubbleUser2

# FastAPI 앱 생성
app = FastAPI(
    title="전북 농촌 일여행 추천 시스템",
    description="전북 지역 농가 일자리와 관광지를 연결한 맞춤형 일여행 추천 및 일정 생성 API",
    version="2.0.0"
)

# CORS 설정 (프론트엔드 연동)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Vercel 배포 시 조정 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 모든 요청 로깅 미들웨어
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # /api/onboarding 요청인 경우 상세 로깅
    if request.url.path == "/api/onboarding":
        print(f"\n{'='*60}")
        print(f"📨 Incoming Request to /api/onboarding")
        print(f"   Method: {request.method}")
        print(f"   Headers: {dict(request.headers)}")
        
        # Body 복사본 만들기 (한 번만 읽을 수 있으므로)
        body = await request.body()
        print(f"   Raw Body: {body.decode() if body else 'Empty'}")
        print(f"{'='*60}\n")
        
        # Request 객체 재생성 (body를 읽었으므로)
        from starlette.datastructures import Headers
        from starlette.requests import Request as StarletteRequest
        
        async def receive():
            return {"type": "http.request", "body": body}
        
        request = StarletteRequest(request.scope, receive)
    
    response = await call_next(request)
    return response

# Validation 에러 핸들러 추가
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 에러 상세 정보 로깅
    print(f"\n{'='*60}")
    print(f"❌ VALIDATION ERROR DETAILS:")
    print(f"   URL: {request.url}")
    print(f"   Method: {request.method}")
    print(f"   Validation Errors: {exc.errors()}")
    print(f"   Body Received: {exc.body}")
    print(f"{'='*60}\n")
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": str(exc.body),
            "message": "Request validation failed. Check server logs for details."
        }
    )

# 정적 파일 서빙 (이미지 등)
project_root = Path(__file__).parent.parent
public_dir = project_root / "public"
if public_dir.exists():
    app.mount("/public", StaticFiles(directory=str(public_dir)), name="public")

# 서비스 인스턴스
recommendation_service = get_simple_recommendation_service()
scheduling_service = get_simple_scheduling_service()

# 전역 저장소 (실제 서비스에서는 데이터베이스 사용)
schedules_storage = {}
users_storage = {}  # Bubble User2 데이터 저장소

@app.get("/healthz")
def health_check():
    """헬스 체크"""
    return {"status": "ok", "service": "jeonbuk-rural-travel"}

@app.post("/recommendations")
def get_recommendations(request: Dict[str, Any] = Body(...)):
    """
    농가 일자리 + 관광지 추천 API
    
    요청 형식:
    {
        "natural_request": "9월에 김제에서 과수원 체험하고 싶어",
        "preferences": {
            "landscape_keywords": ["자연", "산"],
            "travel_style_keywords": ["체험", "힐링"],
            "job_type_keywords": ["과수", "채소"]
        }
    }
    """
    try:
        natural_request = request.get("natural_request", "")
        preferences = request.get("preferences", {})
        
        if not natural_request:
            raise HTTPException(status_code=400, detail="natural_request는 필수입니다.")
        
        print(f"📋 추천 요청: {natural_request}")
        
        # 추천 서비스 호출
        result = recommendation_service.get_recommendations(natural_request, preferences)
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 추천 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"추천 처리 중 오류: {str(e)}")

@app.post("/api/schedule")
def create_schedule(request: Dict[str, Any] = Body(...)):
    """
    일정 생성 API
    
    요청 형식:
    {
        "natural_request": "9월에 김제에서 3일간 과수원 체험하고 싶어",
        "selected_farm": { ... },  # 선택된 농가 1개
        "selected_tours": [ ... ], # 선택된 관광지들
        "preferences": { ... }     # 사용자 선호도
    }
    """
    try:
        natural_request = request.get("natural_request", "")
        selected_farm = request.get("selected_farm", {})
        selected_tours = request.get("selected_tours", [])
        preferences = request.get("preferences", {})
        
        if not natural_request:
            raise HTTPException(status_code=400, detail="natural_request는 필수입니다.")
        
        if not selected_farm:
            raise HTTPException(status_code=400, detail="농가를 1개 선택해야 합니다.")
        
        print(f"📅 일정 생성 요청: {natural_request}")
        
        # 농가 주소에서 지역 추출
        region = None
        if selected_farm:
            farm_address = selected_farm.get("address", "")
            for r in ["김제시", "전주시", "군산시", "익산시", "정읍시", "남원시", "고창군", "부안군", "임실군", "순창군", "진안군", "무주군", "장수군", "완주군"]:
                if r in farm_address:
                    region = r
                    break
        
        # 스코어링된 관광지 데이터와 추천 카드 ID 추출
        scored_attractions = request.get("scored_attractions", [])
        recommended_tour_ids = []
        if "tour_spots" in request:
            recommended_tour_ids = [tour.get("tour_id") for tour in request["tour_spots"]]
        
        print(f"📊 스코어링 데이터: {len(scored_attractions)}개, 추천 카드: {len(recommended_tour_ids)}개")
        
        # 일정 생성 서비스 호출
        result = scheduling_service.generate_schedule(
            natural_request, selected_farm, selected_tours, preferences, region,
            scored_attractions, recommended_tour_ids
        )
        
        if result["status"] == "success":
            # 전역 저장소에 일정 저장 (피드백용)
            itinerary_id = result["data"]["itinerary_id"]
            schedules_storage[itinerary_id] = {
                "schedule": result["data"],
                "original_request": {
                    "natural_request": natural_request,
                    "selected_farm": selected_farm,
                    "selected_tours": selected_tours,
                    "preferences": preferences
                }
            }
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 일정 생성 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"일정 생성 중 오류: {str(e)}")

@app.post("/api/schedule/{itinerary_id}/feedback")
def update_schedule_feedback_with_id(itinerary_id: str, request: Dict[str, Any] = Body(...)):
    """
    일정 피드백 처리 API (itinerary_id 기반)
    
    요청 형식:
    {
        "feedback": "첫째날 일정을 다른 관광지로 바꿔주세요"
    }
    """
    try:
        feedback = request.get("feedback", "")
        
        if not feedback:
            raise HTTPException(status_code=400, detail="feedback은 필수입니다.")
        
        # 기존 일정 조회
        if itinerary_id not in schedules_storage:
            raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")
        
        original_schedule = schedules_storage[itinerary_id]["schedule"]
        
        print(f"🔄 일정 수정 요청: {feedback}")
        
        # 피드백 처리 서비스 호출
        result = scheduling_service.process_feedback(itinerary_id, feedback, original_schedule)
        
        if result["status"] == "success":
            # 수정된 일정 저장
            schedules_storage[itinerary_id]["schedule"] = result["data"]
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 피드백 처리 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"피드백 처리 중 오류: {str(e)}")

@app.post("/api/schedule/{itinerary_id}/summary")
def generate_travel_summary(itinerary_id: str):
    """
    일정 확정 후 매력적인 일여행 요약 생성 API
    
    사용자가 일정 확정 버튼을 누르면 AI가 개인화된 여행 요약을 생성합니다.
    """
    try:
        # 기존 일정 조회
        if itinerary_id not in schedules_storage:
            raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")
        
        schedule_data = schedules_storage[itinerary_id]
        itinerary_data = schedule_data["schedule"]["itinerary"]
        original_request = schedule_data["original_request"]
        
        # 지역 정보 추출
        region = None
        if original_request.get("selected_farm"):
            farm_address = original_request["selected_farm"].get("address", "")
            for r in ["김제시", "전주시", "군산시", "익산시", "정읍시", "남원시", "고창군", "부안군", "임실군", "순창군", "진안군", "무주군", "장수군", "완주군"]:
                if r in farm_address:
                    region = r
                    break
        
        if not region:
            region = "전북"
        
        print(f"🎨 일여행 요약 생성 요청: {itinerary_id} ({region})")
        
        # AI 요약 생성
        result = scheduling_service.generate_travel_summary(
            itinerary_data=itinerary_data,
            natural_request=original_request.get("natural_request", ""),
            user_preferences=original_request.get("preferences", {}),
            region=region
        )
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 여행 요약 생성 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"여행 요약 생성 중 오류: {str(e)}")

@app.post("/api/onboarding/debug")
async def debug_onboarding(request: Request):
    """온보딩 디버그 엔드포인트 - raw 요청 확인용"""
    try:
        body = await request.body()
        body_str = body.decode()
        print(f"📥 Raw 온보딩 요청 바디: {body_str}")
        
        import json
        try:
            body_json = json.loads(body_str) if body_str else {}
            print(f"📥 파싱된 JSON: {body_json}")
        except json.JSONDecodeError as e:
            print(f"❌ JSON 파싱 에러: {e}")
            body_json = {}
        
        return JSONResponse(content={
            "status": "debug",
            "raw_body": body_str,
            "parsed_json": body_json,
            "message": "디버그 정보를 터미널에서 확인하세요"
        })
    except Exception as e:
        print(f"❌ 디버그 에러: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/api/onboarding")
def create_user_onboarding(request: OnboardingRequest = Body(...)):
    """
    Bubble 온보딩 데이터 수집 API
    
    BUBBLE User2 테이블 구조에 맞춰 사용자 선호도 데이터를 저장합니다.
    온보딩 과정: 누구와 → 풍경 선호도 → 여행 스타일 → 체험 유형 → 추가 요청
    """
    try:
        # 디버깅: 받은 데이터 로깅
        print(f"📥 온보딩 요청 데이터: {request.model_dump()}")
        
        # 기본값 처리 (빈 값인 경우 기본값 설정)
        name = request.name or "사용자"
        age = request.age or "25"
        gender = request.gender or "미정"
        sido = request.sido or "전북"
        sigungu = request.sigungu or "전주시"
        with_whom = request.with_whom or "혼자"
        real_name = request.real_name or "사용자"
        
        # User2 데이터 구조로 변환
        user_data = BubbleUser2(
            address=f"{sido} {sigungu}",
            age=age,
            gender=gender,
            name=name,
            pref_etc=request.additional_requests,  # 6단계 서술형 (5개 칸)
            pref_jobs=request.selected_jobs,        # 5단계 체험 유형
            pref_style=request.selected_styles,     # 4단계 여행 스타일
            pref_view=request.selected_views,       # 3단계 풍경 선호도
            real_name=real_name,
            with_whom=with_whom                     # 2단계 누구와
        )
        
        # 사용자 ID 생성 (실제로는 UUID 등 사용)
        import time
        user_id = f"user_{int(time.time())}"
        
        # 전역 저장소에 저장
        users_storage[user_id] = user_data
        
        print(f"📝 온보딩 완료: {user_data.name} ({user_id})")
        print(f"선호도: 풍경={user_data.pref_view}, 스타일={user_data.pref_style}, 체험={user_data.pref_jobs}")
        
        return JSONResponse(content={
            "status": "success",
            "message": "온보딩이 완료되었습니다.",
            "user_id": user_id,
            "user_data": user_data.model_dump()
        })
        
    except Exception as e:
        print(f"❌ 온보딩 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"온보딩 처리 중 오류: {str(e)}")

@app.get("/api/user/{user_id}")
def get_user_data(user_id: str):
    """사용자 데이터 조회 API"""
    if user_id not in users_storage:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    
    return {
        "status": "success",
        "user_data": users_storage[user_id].model_dump()
    }

@app.post("/recommendations/with-user")
def get_recommendations_with_user(request: Dict[str, Any] = Body(...)):
    """
    사용자 ID 기반 추천 API (Bubble 연동용)
    
    요청 형식:
    {
        "user_id": "user_1234567890",
        "natural_request": "9월에 김제에서 과수원 체험하고 싶어"
    }
    """
    try:
        user_id = request.get("user_id", "")
        natural_request = request.get("natural_request", "")
        
        if not natural_request:
            raise HTTPException(status_code=400, detail="natural_request는 필수입니다.")
        
        # 해커톤용: 사용자 데이터 조회 또는 기본값 사용
        if not user_id or user_id not in users_storage:
            # 해커톤용 기본 사용자 데이터 (사용자가 없어도 작동)
            if user_id:
                print(f"⚠️  사용자 {user_id}를 찾을 수 없어 기본 선호도 사용")
            else:
                print(f"⚠️  user_id가 제공되지 않아 기본 선호도 사용")
            user_data = BubbleUser2(
                address="전국",
                age="25",
                gender="전체",
                name="데모사용자",
                pref_etc=["자연친화", "체험학습", "농촌여행", "힐링", "사진촬영"],
                pref_jobs=["과수", "채소", "축산"],
                pref_style=["체험형", "힐링·여유", "자연·생태"],
                pref_view=["산", "들판", "숲"],
                real_name="데모사용자",
                with_whom="친구와"
            )
        else:
            user_data = users_storage[user_id]
        
        # User2 선호도를 기존 preferences 형식으로 변환
        preferences = {
            "landscape_keywords": user_data.pref_view,     # 풍경 선호도
            "travel_style_keywords": user_data.pref_style, # 여행 스타일
            "job_type_keywords": user_data.pref_jobs,      # 체험 유형
            "simple_natural_words": user_data.pref_etc     # 추가 요청사항
        }
        
        print(f"📋 사용자 기반 추천 요청: {user_data.name} - {natural_request}")
        print(f"사용자 선호도: {preferences}")
        
        # 추천 서비스 호출
        result = recommendation_service.get_recommendations(natural_request, preferences)
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        
        # 응답에 사용자 정보 추가
        result["user_info"] = {
            "user_id": user_id,
            "name": user_data.name,
            "with_whom": user_data.with_whom,
            "address": user_data.address
        }
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 사용자 기반 추천 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"추천 처리 중 오류: {str(e)}")

@app.get("/api/regions")
def get_available_regions():
    """사용 가능한 전북 지역 목록 반환"""
    regions = [
        "고창군", "군산시", "김제시", "남원시", "무주군", "부안군",
        "순창군", "완주군", "익산시", "임실군", "장수군", "전주시", "정읍시", "진안군"
    ]
    return {"regions": regions}

@app.get("/api/preferences/options")
def get_preference_options():
    """온보딩에서 사용할 선호도 옵션들 반환 (index.html과 동일)"""
    return {
        "status": "success",
        "data": {
            "landscape_options": [
                "산", "바다", "강·호수", "숲", "섬"
            ],
            "travel_style_options": [
                "힐링·여유", "체험형", "야외활동", "레저·액티비티", 
                "문화·역사", "축제·이벤트", "먹거리 탐방", "사진 스팟"
            ],
            "job_type_options": [
                "채소", "과수", "화훼", "식량작물", "축산", "농기계"
            ]
        }
    }

@app.post("/api/schedule/with-user")
def create_schedule_with_user(request: Dict[str, Any] = Body(...)):
    """
    사용자 ID 기반 일정 생성 API (Bubble 연동용)
    
    요청 형식:
    {
        "user_id": "user_1234567890",
        "natural_request": "10월에 열흘간 김제에서 과수원 체험하고 싶어",
        "selected_farm": { ... },
        "selected_tours": [ ... ]
    }
    """
    try:
        user_id = request.get("user_id", "")
        natural_request = request.get("natural_request", "")
        selected_farm = request.get("selected_farm", {})
        selected_tours = request.get("selected_tours", [])
        
        if not natural_request:
            raise HTTPException(status_code=400, detail="natural_request는 필수입니다.")
        
        if not selected_farm:
            raise HTTPException(status_code=400, detail="농가를 1개 선택해야 합니다.")
        
        # 해커톤용: 사용자 데이터 조회 또는 기본값 사용
        if not user_id or user_id not in users_storage:
            # 해커톤용 기본 사용자 데이터 (사용자가 없어도 작동)
            if user_id:
                print(f"⚠️  사용자 {user_id}를 찾을 수 없어 기본 선호도 사용")
            else:
                print(f"⚠️  user_id가 제공되지 않아 기본 선호도 사용")
            user_data = BubbleUser2(
                address="전국",
                age="25",
                gender="전체",
                name="데모사용자",
                pref_etc=["자연친화", "체험학습", "농촌여행", "힐링", "사진촬영"],
                pref_jobs=["과수", "채소", "축산"],
                pref_style=["체험형", "힐링·여유", "자연·생태"],
                pref_view=["산", "들판", "숲"],
                real_name="데모사용자",
                with_whom="친구와"
            )
        else:
            user_data = users_storage[user_id]
        
        # User2 선호도를 기존 preferences 형식으로 변환
        preferences = {
            "landscape_keywords": user_data.pref_view,
            "travel_style_keywords": user_data.pref_style, 
            "job_type_keywords": user_data.pref_jobs,
            "simple_natural_words": user_data.pref_etc
        }
        
        print(f"📅 사용자 기반 일정 생성: {user_data.name} - {natural_request}")
        print(f"🚜 선택된 농가: {selected_farm}")
        print(f"🏞️ 선택된 관광지: {selected_tours}")
        
        # 농가 주소에서 지역 추출
        region = None
        if selected_farm:
            farm_address = selected_farm.get("address", "")
            for r in ["김제시", "전주시", "군산시", "익산시", "정읍시", "남원시", "고창군", "부안군", "임실군", "순창군", "진안군", "무주군", "장수군", "완주군"]:
                if r in farm_address:
                    region = r
                    break
        
        # 사용자 선호도 기반으로 스코어링된 관광지 데이터 생성
        scored_attractions = None
        recommended_tour_ids = []
        
        try:
            # 추천 서비스에서 스코어링된 관광지 가져오기
            recommendation_result = recommendation_service.get_recommendations(natural_request, preferences)
            if recommendation_result["status"] == "success" and "data" in recommendation_result:
                data = recommendation_result["data"]
                if "scored_attractions" in data:
                    scored_attractions = data["scored_attractions"]
                    recommended_tour_ids = [tour.get("tour_id") for tour in data["tour_spots"]]
                    print(f"🎯 스코어링된 관광지 데이터 활용: {len(scored_attractions)}개, 추천 카드: {len(recommended_tour_ids)}개")
                else:
                    print(f"⚠️  추천 결과에서 scored_attractions 필드 없음")
        except Exception as e:
            print(f"⚠️  스코어링 데이터 생성 실패, 기본 로직 사용: {e}")
        
        # 일정 생성 서비스 호출
        result = scheduling_service.generate_schedule(
            natural_request, selected_farm, selected_tours, preferences, region,
            scored_attractions, recommended_tour_ids
        )
        
        if result["status"] == "success":
            # 전역 저장소에 일정 저장
            itinerary_id = result["data"]["itinerary_id"]
            schedules_storage[itinerary_id] = {
                "schedule": result["data"],
                "user_id": user_id,
                "original_request": {
                    "natural_request": natural_request,
                    "selected_farm": selected_farm,
                    "selected_tours": selected_tours,
                    "preferences": preferences
                }
            }
            
            # 응답에 사용자 정보 추가
            result["user_info"] = {
                "user_id": user_id,
                "name": user_data.name,
                "with_whom": user_data.with_whom,
                "address": user_data.address
            }
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 사용자 기반 일정 생성 오류: {e}")
        raise HTTPException(status_code=500, detail=f"일정 생성 중 오류: {str(e)}")

@app.get("/api/schedule/{itinerary_id}")
def get_schedule(itinerary_id: str):
    """저장된 일정 조회 API"""
    if itinerary_id not in schedules_storage:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")
    
    schedule_data = schedules_storage[itinerary_id]
    return {
        "status": "success",
        "data": schedule_data["schedule"],
        "user_id": schedule_data.get("user_id")
    }

@app.post("/api/schedule/feedback")
def send_schedule_feedback(request: Dict[str, Any] = Body(...)):
    """
    일정 피드백 처리 API (itinerary_id 또는 user_id 기반)
    
    요청 형식 1 (itinerary_id 기반):
    {
        "itinerary_id": "schedule_20250831_143000",
        "feedback": "첫째날 일정을 다른 관광지로 바꿔주세요"
    }
    
    요청 형식 2 (user_id 기반):
    {
        "user_id": "user_1234567890", 
        "feedback": "첫째날 일정을 다른 관광지로 바꿔주세요"
    }
    """
    try:
        itinerary_id = request.get("itinerary_id", "")
        user_id = request.get("user_id", "")
        feedback = request.get("feedback", "")
        
        if not feedback:
            raise HTTPException(status_code=400, detail="feedback은 필수입니다.")
        
        target_itinerary_id = None
        target_schedule_data = None
        
        # 방법 1: itinerary_id 직접 사용 (index.html용)
        if itinerary_id:
            if itinerary_id not in schedules_storage:
                raise HTTPException(status_code=404, detail="해당 일정을 찾을 수 없습니다.")
            
            target_itinerary_id = itinerary_id
            target_schedule_data = schedules_storage[itinerary_id]
            print(f"🔄 일정 수정 요청 (일정ID: {itinerary_id}): {feedback}")
        
        # 방법 2: user_id로 최근 일정 찾기 (Bubble용)
        elif user_id:
            user_schedules = []
            for iid, schedule_data in schedules_storage.items():
                if schedule_data.get("user_id") == user_id:
                    user_schedules.append((iid, schedule_data))
            
            if not user_schedules:
                raise HTTPException(status_code=404, detail="해당 사용자의 일정을 찾을 수 없습니다.")
            
            # 가장 최근 일정 선택
            target_itinerary_id, target_schedule_data = max(user_schedules, key=lambda x: x[0])
            print(f"🔄 일정 수정 요청 (사용자: {user_id}, 일정: {target_itinerary_id}): {feedback}")
        
        else:
            raise HTTPException(status_code=400, detail="itinerary_id 또는 user_id 중 하나는 필수입니다.")
        
        original_schedule = target_schedule_data["schedule"]
        
        # 피드백 처리 서비스 호출
        result = scheduling_service.process_feedback(target_itinerary_id, feedback, original_schedule)
        
        if result["status"] == "success":
            # 수정된 일정 저장
            schedules_storage[target_itinerary_id]["schedule"] = result["data"]
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 피드백 처리 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"피드백 처리 중 오류: {str(e)}")

@app.get("/api/user/{user_id}/schedules")
def get_user_schedules(user_id: str):
    """사용자별 생성된 일정 목록 조회"""
    user_schedules = []
    
    for itinerary_id, schedule_data in schedules_storage.items():
        if schedule_data.get("user_id") == user_id:
            user_schedules.append({
                "itinerary_id": itinerary_id,
                "title": f"{schedule_data['schedule'].get('summary', {}).get('duration', 0)}일 일정",
                "region": schedule_data['schedule'].get('summary', {}).get('region', ''),
                "created_at": schedule_data['schedule'].get('itinerary_id', '').replace('schedule_', '').replace('_', '-'),
                "total_days": schedule_data['schedule'].get('total_days', 0)
            })
    
    return {
        "status": "success",
        "data": user_schedules
    }

# 루트 경로 (API 문서 안내)
@app.get("/")
def root():
    return {
        "service": "전북 농촌 일여행 추천 시스템",
        "version": "2.0.0",
        "docs": "/docs",
        "bubble_integration": "완료",
        "endpoints": {
            "onboarding": "/api/onboarding",
            "preference_options": "/api/preferences/options",
            "user_data": "/api/user/{user_id}",
            "user_schedules": "/api/user/{user_id}/schedules",
            "recommendations": "/recommendations",
            "recommendations_with_user": "/recommendations/with-user",
            "schedule": "/api/schedule", 
            "schedule_with_user": "/api/schedule/with-user",
            "get_schedule": "/api/schedule/{itinerary_id}",
            "feedback": "/api/schedule/feedback",
            "feedback_with_id": "/api/schedule/{itinerary_id}/feedback",
            "regions": "/api/regions"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)