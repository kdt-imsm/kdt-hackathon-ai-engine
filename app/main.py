"""
단순화된 FastAPI 메인 애플리케이션
전북 지역 농촌 일여행 추천 및 일정 생성 API
"""

from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
from typing import Dict, List, Any

from app.services.simple_recommendation_service import get_simple_recommendation_service
from app.services.simple_scheduling_service import get_simple_scheduling_service

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

# 정적 파일 서빙 (이미지 등)
project_root = Path(__file__).parent.parent
public_dir = project_root / "public"
if public_dir.exists():
    app.mount("/public", StaticFiles(directory=str(public_dir)), name="public")

# 서비스 인스턴스
recommendation_service = get_simple_recommendation_service()
scheduling_service = get_simple_scheduling_service()

# 전역 일정 저장소 (실제 서비스에서는 데이터베이스 사용)
schedules_storage = {}

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
        
        # 일정 생성 서비스 호출
        result = scheduling_service.generate_schedule(
            natural_request, selected_farm, selected_tours, preferences, region
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

@app.post("/api/schedule/feedback")
def update_schedule_feedback(request: Dict[str, Any] = Body(...)):
    """
    일정 피드백 처리 API
    
    요청 형식:
    {
        "itinerary_id": "schedule_20250831_143000",
        "feedback": "첫째날 일정을 다른 관광지로 바꿔주세요"
    }
    """
    try:
        itinerary_id = request.get("itinerary_id", "")
        feedback = request.get("feedback", "")
        
        if not itinerary_id or not feedback:
            raise HTTPException(status_code=400, detail="itinerary_id와 feedback은 필수입니다.")
        
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

@app.get("/api/regions")
def get_available_regions():
    """사용 가능한 전북 지역 목록 반환"""
    regions = [
        "고창군", "군산시", "김제시", "남원시", "무주군", "부안군",
        "순창군", "완주군", "익산시", "임실군", "장수군", "전주시", "정읍시", "진안군"
    ]
    return {"regions": regions}

# 루트 경로 (API 문서 안내)
@app.get("/")
def root():
    return {
        "service": "전북 농촌 일여행 추천 시스템",
        "version": "2.0.0",
        "docs": "/docs",
        "endpoints": {
            "recommendations": "/recommendations",
            "schedule": "/api/schedule", 
            "feedback": "/api/schedule/feedback",
            "regions": "/api/regions"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)