"""
Demo용 TourAPI 데이터 수집 스크립트
==================================

DEMO_GUIDE.md에 명시된 관광지, 숙박, 음식점 데이터를 TourAPI에서 수집하여 저장합니다.
"""

import asyncio
import csv
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp
import pandas as pd
from pydantic import BaseModel

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings


class TourSpotData(BaseModel):
    """관광지 데이터 모델"""
    name: str
    content_type: str
    content_id: str
    addr1: str
    addr2: Optional[str] = None
    mapx: Optional[str] = None
    mapy: Optional[str] = None
    first_image: Optional[str] = None
    first_image2: Optional[str] = None
    overview: Optional[str] = None
    tel: Optional[str] = None
    homepage: Optional[str] = None
    zipcode: Optional[str] = None
    booktour: Optional[str] = None
    mlevel: Optional[str] = None
    areacode: str = "37"  # 전북
    sigungucode: str = "13"  # 김제시


class DemoDataCollector:
    """Demo용 관광 데이터 수집기"""
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.tour_base_url
        self.api_key = self.settings.tour_api_key
        
        # DEMO_GUIDE.md에 명시된 고정 데이터들
        self.demo_attractions = [
            "김제 국가유산 야행",
            "백산서원(김제)", 
            "김제 벽골제",
            "김제장 (2, 7일)",
            "모악산도립공원",
            "아리랑문학마을",
            "귀신사(김제)"
        ]
        
        self.demo_accommodations = [
            "모악산 유스호스텔"
        ]
        
        self.demo_restaurants = [
            "김정선 베이커리카페",
            "대율담", 
            "오늘여기",
            "대운한우암소회관",
            "아울카페"
        ]

    async def search_by_keyword(self, session: aiohttp.ClientSession, keyword: str, content_type: str = "12") -> List[Dict]:
        """키워드로 TourAPI 검색"""
        url = f"{self.base_url}/searchKeyword1"
        
        params = {
            "ServiceKey": self.api_key,
            "numOfRows": 20,
            "pageNo": 1,
            "MobileOS": "ETC",
            "MobileApp": "KDT_DEMO",
            "keyword": keyword,
            "contentTypeId": content_type,
            "areaCode": "37",  # 전북
            "sigunguCode": "13",  # 김제시
            "_type": "json"
        }
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if (data.get("response", {}).get("header", {}).get("resultCode") == "0000" and
                        data.get("response", {}).get("body", {}).get("items")):
                        return data["response"]["body"]["items"]["item"]
                    else:
                        print(f"키워드 '{keyword}' 검색 결과 없음")
                        return []
                else:
                    print(f"키워드 '{keyword}' 검색 실패: {response.status}")
                    return []
        except Exception as e:
            print(f"키워드 '{keyword}' 검색 중 오류: {e}")
            return []

    async def get_detail_info(self, session: aiohttp.ClientSession, content_id: str, content_type: str) -> Optional[Dict]:
        """상세정보 조회"""
        url = f"{self.base_url}/detailCommon1"
        
        params = {
            "ServiceKey": self.api_key,
            "contentId": content_id,
            "contentTypeId": content_type,
            "MobileOS": "ETC", 
            "MobileApp": "KDT_DEMO",
            "defaultYN": "Y",
            "firstImageYN": "Y",
            "addrinfoYN": "Y",
            "mapinfoYN": "Y",
            "overviewYN": "Y",
            "_type": "json"
        }
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if (data.get("response", {}).get("header", {}).get("resultCode") == "0000" and
                        data.get("response", {}).get("body", {}).get("items")):
                        return data["response"]["body"]["items"]["item"][0]
                    else:
                        return None
                else:
                    print(f"상세정보 조회 실패 (ID: {content_id}): {response.status}")
                    return None
        except Exception as e:
            print(f"상세정보 조회 중 오류 (ID: {content_id}): {e}")
            return None

    async def collect_attractions_data(self) -> List[Dict]:
        """관광지 데이터 수집"""
        results = []
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            for attraction in self.demo_attractions:
                print(f"관광지 검색 중: {attraction}")
                
                # 키워드 검색 (관광지 = content_type 12)
                search_results = await self.search_by_keyword(session, attraction, "12")
                
                if search_results:
                    # 가장 유사한 결과 선택 (첫 번째 결과)
                    item = search_results[0]
                    
                    # 상세정보 조회
                    detail = await self.get_detail_info(session, item["contentid"], item["contenttypeid"])
                    
                    # 데이터 병합
                    if detail:
                        item.update(detail)
                    
                    # 필요한 필드만 추출
                    attraction_data = {
                        "name": item.get("title", attraction),
                        "content_type": item.get("contenttypeid", "12"),
                        "content_id": item.get("contentid", ""),
                        "addr1": item.get("addr1", ""),
                        "addr2": item.get("addr2", ""),
                        "mapx": item.get("mapx", ""),
                        "mapy": item.get("mapy", ""),
                        "first_image": item.get("firstimage", ""),
                        "first_image2": item.get("firstimage2", ""),
                        "overview": item.get("overview", ""),
                        "tel": item.get("tel", ""),
                        "homepage": item.get("homepage", ""),
                        "zipcode": item.get("zipcode", ""),
                        "areacode": "37",
                        "sigungucode": "13"
                    }
                    
                    results.append(attraction_data)
                    print(f"✅ {attraction} 데이터 수집 완료")
                    
                else:
                    print(f"❌ {attraction} 데이터 수집 실패")
                
                # API 요청 간격
                await asyncio.sleep(0.5)
        
        return results

    async def collect_accommodations_data(self) -> List[Dict]:
        """숙박 데이터 수집"""
        results = []
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            for accommodation in self.demo_accommodations:
                print(f"숙박시설 검색 중: {accommodation}")
                
                # 키워드 검색 (숙박 = content_type 32)
                search_results = await self.search_by_keyword(session, accommodation, "32")
                
                if search_results:
                    item = search_results[0]
                    
                    # 상세정보 조회
                    detail = await self.get_detail_info(session, item["contentid"], item["contenttypeid"])
                    
                    if detail:
                        item.update(detail)
                    
                    accommodation_data = {
                        "name": item.get("title", accommodation),
                        "content_type": item.get("contenttypeid", "32"),
                        "content_id": item.get("contentid", ""),
                        "addr1": item.get("addr1", ""),
                        "addr2": item.get("addr2", ""),
                        "mapx": item.get("mapx", ""),
                        "mapy": item.get("mapy", ""),
                        "first_image": item.get("firstimage", ""),
                        "first_image2": item.get("firstimage2", ""),
                        "overview": item.get("overview", ""),
                        "tel": item.get("tel", ""),
                        "homepage": item.get("homepage", ""),
                        "zipcode": item.get("zipcode", ""),
                        "areacode": "37",
                        "sigungucode": "13"
                    }
                    
                    results.append(accommodation_data)
                    print(f"✅ {accommodation} 데이터 수집 완료")
                    
                else:
                    print(f"❌ {accommodation} 데이터 수집 실패")
                
                await asyncio.sleep(0.5)
        
        return results

    async def collect_restaurants_data(self) -> List[Dict]:
        """음식점 데이터 수집"""
        results = []
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            for restaurant in self.demo_restaurants:
                print(f"음식점 검색 중: {restaurant}")
                
                # 키워드 검색 (음식점 = content_type 39)
                search_results = await self.search_by_keyword(session, restaurant, "39")
                
                if search_results:
                    item = search_results[0]
                    
                    # 상세정보 조회
                    detail = await self.get_detail_info(session, item["contentid"], item["contenttypeid"])
                    
                    if detail:
                        item.update(detail)
                    
                    restaurant_data = {
                        "name": item.get("title", restaurant),
                        "content_type": item.get("contenttypeid", "39"),
                        "content_id": item.get("contentid", ""),
                        "addr1": item.get("addr1", ""),
                        "addr2": item.get("addr2", ""),
                        "mapx": item.get("mapx", ""),
                        "mapy": item.get("mapy", ""),
                        "first_image": item.get("firstimage", ""),
                        "first_image2": item.get("firstimage2", ""),
                        "overview": item.get("overview", ""),
                        "tel": item.get("tel", ""),
                        "homepage": item.get("homepage", ""),
                        "zipcode": item.get("zipcode", ""),
                        "areacode": "37",
                        "sigungucode": "13"
                    }
                    
                    results.append(restaurant_data)
                    print(f"✅ {restaurant} 데이터 수집 완료")
                    
                else:
                    print(f"❌ {restaurant} 데이터 수집 실패")
                
                await asyncio.sleep(0.5)
        
        return results

    async def collect_all_data(self):
        """모든 데이터 수집 및 저장"""
        print("=== Demo 데이터 수집 시작 ===\n")
        
        # 1. 관광지 데이터 수집
        print("1. 관광지 데이터 수집 중...")
        attractions = await self.collect_attractions_data()
        
        # 2. 숙박 데이터 수집  
        print("\n2. 숙박시설 데이터 수집 중...")
        accommodations = await self.collect_accommodations_data()
        
        # 3. 음식점 데이터 수집
        print("\n3. 음식점 데이터 수집 중...")
        restaurants = await self.collect_restaurants_data()
        
        # 4. 데이터 저장
        data_dir = Path(__file__).parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        
        # CSV 파일로 저장
        if attractions:
            df_attractions = pd.DataFrame(attractions)
            df_attractions.to_csv(data_dir / "demo_attractions.csv", index=False, encoding="utf-8-sig")
            print(f"\n✅ 관광지 데이터 저장 완료: {len(attractions)}개")
        
        if accommodations:
            df_accommodations = pd.DataFrame(accommodations)
            df_accommodations.to_csv(data_dir / "demo_accommodations.csv", index=False, encoding="utf-8-sig")
            print(f"✅ 숙박시설 데이터 저장 완료: {len(accommodations)}개")
        
        if restaurants:
            df_restaurants = pd.DataFrame(restaurants)
            df_restaurants.to_csv(data_dir / "demo_restaurants.csv", index=False, encoding="utf-8-sig")
            print(f"✅ 음식점 데이터 저장 완료: {len(restaurants)}개")
        
        # JSON 파일로도 저장 (프론트엔드에서 사용하기 쉽도록)
        demo_data = {
            "attractions": attractions,
            "accommodations": accommodations,
            "restaurants": restaurants
        }
        
        with open(data_dir / "demo_data.json", "w", encoding="utf-8") as f:
            json.dump(demo_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 통합 JSON 파일 저장 완료: demo_data.json")
        print("\n=== Demo 데이터 수집 완료 ===")


async def main():
    """메인 실행 함수"""
    collector = DemoDataCollector()
    await collector.collect_all_data()


if __name__ == "__main__":
    asyncio.run(main())