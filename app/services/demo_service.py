"""
Demo 서비스 모듈
==============

DEMO_GUIDE.md에 정의된 시연용 고정 데이터를 제공하는 서비스입니다.
추천 시스템을 거치지 않고 미리 정의된 결과를 반환합니다.
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from pydantic import BaseModel

class DemoJobCard(BaseModel):
    """Demo용 농가 일자리 카드"""
    id: str
    title: str
    work_date: str
    work_hours: str
    required_people: str
    region: str
    address: str
    crop_type: str
    preference_condition: str
    image_url: str

class DemoTourCard(BaseModel):
    """Demo용 관광지 카드"""
    id: str
    name: str
    content_type: str
    addr1: str
    addr2: Optional[str] = None
    mapx: str
    mapy: str
    first_image: str
    overview: str
    tel: Optional[str] = None

class DemoScheduleItem(BaseModel):
    """Demo용 일정 항목"""
    date: str
    time: str
    type: str  # 'job', 'attraction', 'accommodation', 'restaurant'
    name: str
    address: str
    description: str
    image_url: str

class DemoItinerary(BaseModel):
    """Demo용 전체 일정"""
    title: str
    period: str
    schedule: List[DemoScheduleItem]

class DemoService:
    """Demo 전용 서비스"""
    
    def __init__(self):
        """Demo 데이터 로드"""
        self.data_dir = Path(__file__).parent.parent.parent / "data"
        self.demo_data = self._load_demo_data()
        self.demo_jobs = self._load_demo_jobs()
    
    def _load_demo_data(self) -> Dict:
        """demo_data.json 로드"""
        with open(self.data_dir / "demo_data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _load_demo_jobs(self) -> List[Dict]:
        """demo_jobs.json 로드"""
        with open(self.data_dir / "demo_jobs.json", "r", encoding="utf-8") as f:
            return json.load(f)
    
    def get_demo_job_cards(self, count: int = 5) -> List[DemoJobCard]:
        """Demo용 농가 일자리 카드 반환 (전체 5개)"""
        cards = []
        for i, job in enumerate(self.demo_jobs):
            cards.append(DemoJobCard(
                id=f"job_{i+1}",
                title=job["title"],
                work_date=job["work_date"],
                work_hours=job["work_hours"],
                required_people=job["required_people"],
                region=job["region"],
                address=job["address"],
                crop_type=job["crop_type"],
                preference_condition=job["preference_condition"],
                image_url=job["image_url"]
            ))
        return cards[:count]
    
    def get_demo_tour_cards(self, count: int = 5) -> List[DemoTourCard]:
        """Demo용 관광지 카드 반환 (7개 중 5개 랜덤)"""
        attractions = self.demo_data["attractions"]
        
        # 5개 랜덤 선택
        selected = random.sample(attractions, min(count, len(attractions)))
        
        cards = []
        for i, attraction in enumerate(selected):
            cards.append(DemoTourCard(
                id=f"tour_{i+1}",
                name=attraction["name"],
                content_type=attraction["content_type"],
                addr1=attraction["addr1"],
                addr2=attraction.get("addr2", ""),
                mapx=attraction["mapx"],
                mapy=attraction["mapy"],
                first_image=attraction["first_image"],
                overview=attraction["overview"],
                tel=attraction.get("tel", "")
            ))
        return cards
    
    def generate_demo_itinerary(self, selected_jobs: List[str], selected_tours: List[str]) -> DemoItinerary:
        """Demo용 고정 일정 생성 (2025-09-04 ~ 2025-09-13) - 10일간 사과 수확 체험"""
        
        # 농가 데이터 기반 일정 (사과 수확 도우미만 사용)
        schedule_items = []
        
        # 전체 기간 날짜 생성 (2025-09-04 ~ 2025-09-13)
        from datetime import datetime, timedelta
        start_date = datetime(2025, 9, 4)
        end_date = datetime(2025, 9, 13)
        current_date = start_date
        
        # 첫날 (2025-09-04) - 여행 시작
        schedule_items.extend([
            DemoScheduleItem(
                date="2025-09-04",
                time="12:00",
                type="arrival",
                name="김제 도착",
                address="전북특별자치도 김제시",
                description="김제 사과 수확 체험 여행 시작 - 현지 도착",
                image_url="https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=500"
            ),
            DemoScheduleItem(
                date="2025-09-04",
                time="15:00",
                type="attraction",
                name="김제 벽골제 탐방",
                address="전북특별자치도 김제시 부량면 벽골제로 442",
                description="우리나라 최고의 저수지 벽골제 탐방으로 여행 시작",
                image_url="https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=500"
            )
        ])
        
        # 사과 수확 기간 (2025-09-05~2025-09-11, 08:00-15:00)
        apple_dates = ["2025-09-05", "2025-09-06", "2025-09-07", "2025-09-08", "2025-09-09", "2025-09-10", "2025-09-11"]
        for i, date in enumerate(apple_dates):
            schedule_items.append(DemoScheduleItem(
                date=date,
                time="08:00",
                type="job",
                name=f"사과 수확 도우미 ({i+1}일차)",
                address="전북 김제시 봉남면 사과로 456",
                description="과수원에서 사과 수확 체험 및 농업 일손 돕기 (08:00-15:00)",
                image_url="https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=500"
            ))
            
            # 사과 수확 후 오후 활동
            if date == "2025-09-05":  # 국가유산 야행 (18:00-22:00)
                schedule_items.append(DemoScheduleItem(
                    date=date,
                    time="18:00",
                    type="attraction",
                    name="김제 국가유산 야행",
                    address="전북특별자치도 김제시 요촌동",
                    description="야간 문화유산 체험 프로그램 (18:00-22:00)",
                    image_url="https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=500"
                ))
            elif date == "2025-09-07":  # 김제장 (2,7일)
                schedule_items.append(DemoScheduleItem(
                    date=date,
                    time="16:00",
                    type="attraction",
                    name="김제장 (2, 7일)",
                    address="전북특별자치도 김제시 요촌중길 50",
                    description="전통 5일장에서 지역 특산품 쇼핑",
                    image_url="https://images.unsplash.com/photo-1513475382585-d06e58bcb0e0?w=500"
                ))
            elif date == "2025-09-09":  # 모악산 등산 (09:00-18:00)
                schedule_items.append(DemoScheduleItem(
                    date=date,
                    time="16:00",
                    type="attraction",
                    name="모악산도립공원 등산",
                    address="전북특별자치도 완주군 구이면 모악산길 111-6",
                    description="모악산 등산 및 자연경관 감상",
                    image_url="https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=500"
                ))
            elif date == "2025-09-10":  # 아리랑문학마을 (09:00-18:00)
                schedule_items.append(DemoScheduleItem(
                    date=date,
                    time="16:00",
                    type="attraction",
                    name="아리랑문학마을",
                    address="전북특별자치도 김제시 부량면 용성1길 24",
                    description="조정래 작가의 아리랑 문학관 견학",
                    image_url="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=500"
                ))
        
        # 사과 수확 후 여유 관광 (2025-09-12)
        schedule_items.extend([
            DemoScheduleItem(
                date="2025-09-12",
                time="10:00",
                type="attraction",
                name="백산서원(김제)",
                address="전북특별자치도 김제시 백산면 하서3길 84",
                description="조선시대 서원에서 전통 문화 체험",
                image_url="https://images.unsplash.com/photo-1551961806-bb9de0b5b2eb?w=500"
            ),
            DemoScheduleItem(
                date="2025-09-12",
                time="16:00",
                type="attraction",
                name="김제장 (2, 7일)",
                address="전북특별자치도 김제시 요촌중길 50",
                description="전통 5일장에서 여행 마지막 쇼핑 및 기념품 구입",
                image_url="https://images.unsplash.com/photo-1513475382585-d06e58bcb0e0?w=500"
            )
        ])
        
        # 마지막 날 (2025-09-13) - 출발
        schedule_items.extend([
            DemoScheduleItem(
                date="2025-09-13",
                time="10:00",
                type="departure",
                name="여행 마무리 및 출발 준비",
                address="전북특별자치도 김제시",
                description="9일간의 김제 사과 수확 체험 여행 마무리",
                image_url="https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=500"
            ),
            DemoScheduleItem(
                date="2025-09-13",
                time="14:00",
                type="departure", 
                name="김제 출발",
                address="전북특별자치도 김제시",
                description="김제에서 집으로 돌아가기 - 여행 종료",
                image_url="https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=500"
            )
        ])
        
        # 날짜순 정렬
        schedule_items.sort(key=lambda x: (x.date, x.time))
        
        return DemoItinerary(
            title="김제 사과 수확 체험과 힐링 여행",
            period="2025.09.04 ~ 2025.09.13 (10일간)",
            schedule=schedule_items
        )