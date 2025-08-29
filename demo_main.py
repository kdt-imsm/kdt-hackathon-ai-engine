"""
Demo 전용 FastAPI 서버
- 기존 추천시스템과 완전 분리
- 최소 의존성만 사용
- Vercel 배포 최적화
"""

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List
import os
from pathlib import Path

from app.services.demo_service import DemoService

# FastAPI 앱 생성
app = FastAPI(
    title="농촌 일자리·관광 통합 추천 시스템 - Demo API",
    description="시연용 고정 데이터 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Demo 서비스 초기화
demo_service = DemoService()

# 정적 파일 서빙
app.mount("/public", StaticFiles(directory="public"), name="static")

@app.get("/")
async def root():
    return {"message": "농촌 일자리·관광 통합 추천 시스템 Demo API", "version": "1.0.0"}

@app.get("/healthz")
async def health_check():
    return {"status": "healthy", "service": "demo"}

@app.post("/demo/preferences", response_model=dict)
async def demo_preferences(
    keywords: List[str] = Body(..., description="선택된 선호 키워드들")
):
    """Demo용 선호도 키워드 저장"""
    return {
        "success": True,
        "message": f"{len(keywords)}개의 선호 키워드가 저장되었습니다.",
        "keywords": keywords
    }

@app.post("/demo/slots", response_model=dict)
async def demo_slots(
    natural_query: str = Body(..., description="사용자 자연어 입력")
):
    """Demo용 자연어 슬롯 추출 및 카드 추천"""
    try:
        job_cards = demo_service.get_demo_job_cards(5)
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
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/demo/itinerary", response_model=dict)  
async def demo_itinerary(
    selected_jobs: List[str] = Body(..., description="선택된 농가 일자리 ID들"),
    selected_tours: List[str] = Body(..., description="선택된 관광지 ID들")
):
    """Demo용 고정 일정 생성"""
    try:
        itinerary = demo_service.generate_demo_itinerary(selected_jobs, selected_tours)
        return {
            "success": True,
            "itinerary": itinerary.dict(),
            "message": "김제 과수원 체험과 힐링 여행 일정이 생성되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/demo/accommodations", response_model=dict)
async def demo_accommodations():
    """Demo용 숙박시설 정보"""
    accommodations = []
    for acc in demo_service.demo_data["accommodations"]:
        accommodations.append({
            "name": acc["name"],
            "addr1": acc["addr1"],
            "tel": acc["tel"],
            "first_image": acc["first_image"]
        })
    
    return {
        "success": True,
        "accommodations": accommodations
    }

@app.get("/demo/restaurants", response_model=dict)
async def demo_restaurants():
    """Demo용 음식점 정보"""
    restaurants = []
    for rest in demo_service.demo_data["restaurants"]:
        restaurants.append({
            "name": rest["name"],
            "addr1": rest["addr1"],
            "tel": rest["tel"],
            "first_image": rest["first_image"]
        })
    
    return {
        "success": True,
        "restaurants": restaurants
    }

# Demo UI 접근
@app.get("/demo", response_class=FileResponse)
async def demo_page():
    import os
    file_path = os.path.join(os.path.dirname(__file__), "public", "demo.html")
    return FileResponse(file_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)