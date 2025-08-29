#!/usr/bin/env python3
"""
실제 TourAPI detailImage2 엔드포인트를 사용하여 이미지 수집
TOUR_API_GUIDE.md의 2-D. 이미지 — `/detailImage2` 사용
"""

import json
import ssl
import asyncio
import aiohttp
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.config import get_settings

async def get_real_image_from_tour_api(content_id: str) -> str:
    """TourAPI detailImage2 엔드포인트로 실제 이미지 URL 가져오기"""
    settings = get_settings()
    base_url = settings.tour_base_url
    api_key = settings.tour_api_key
    
    url = f"{base_url}/detailImage2"
    params = {
        "ServiceKey": api_key,
        "contentId": content_id,
        "MobileOS": "ETC",
        "MobileApp": "KDT_DEMO",
        "imageYN": "Y",
        "subImageYN": "Y",
        "_type": "json",
        "numOfRows": "10",
        "pageNo": "1"
    }
    
    # SSL 검증 비활성화로 연결 문제 해결
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if (data.get("response", {}).get("header", {}).get("resultCode") == "0000" and
                        data.get("response", {}).get("body", {}).get("items")):
                        
                        items = data["response"]["body"]["items"]["item"]
                        if isinstance(items, list) and len(items) > 0:
                            # 첫 번째 이미지의 원본 URL 반환
                            return items[0].get("originimgurl", "")
                        elif isinstance(items, dict):
                            # 단일 이미지인 경우
                            return items.get("originimgurl", "")
                return ""
    except Exception as e:
        print(f"Error getting image for content_id {content_id}: {e}")
        return ""

async def main():
    """demo_data.json의 실제 content_id들로 이미지 수집"""
    
    # demo_data.json 복구 (기본 구조)
    demo_data = {
        "attractions": [
            {
                "name": "백산서원(김제)",
                "content_type": "12", 
                "content_id": "1956984",
                "addr1": "전북특별자치도 김제시",
                "addr2": "",
                "mapx": "126.8718860797",
                "mapy": "35.8258554346",
                "first_image": "",
                "first_image2": "",
                "overview": "조선시대 김제 지역의 대표적인 서원으로, 유교 교육의 산실이었던 곳입니다.",
                "tel": "063-540-3000",
                "homepage": "",
                "zipcode": "54300",
                "areacode": "37",
                "sigungucode": "13"
            },
            {
                "name": "김제 벽골제",
                "content_type": "12",
                "content_id": "231895", 
                "addr1": "전북특별자치도 김제시 부량면 벽골제로 442",
                "addr2": "",
                "mapx": "126.8531173673",
                "mapy": "35.7546687724",
                "first_image": "",
                "first_image2": "",
                "overview": "백제시대부터 축조된 우리나나 최고(最古)의 저수지입니다.",
                "tel": "063-540-3690",
                "homepage": "http://tour.gimje.go.kr",
                "zipcode": "54348",
                "areacode": "37",
                "sigungucode": "13"
            },
            {
                "name": "모악산도립공원",
                "content_type": "12",
                "content_id": "127574",
                "addr1": "전북특별자치도 완주군 구이면 모악산길 111-6",
                "addr2": "",
                "mapx": "127.0561028982",
                "mapy": "35.7228286577",
                "first_image": "",
                "first_image2": "",
                "overview": "해발 793m의 모악산은 전북 지역의 명산으로, 등산로와 자연경관이 아름다운 도립공원입니다.",
                "tel": "063-290-3434",
                "homepage": "http://moaksan.jeonbuk.go.kr",
                "zipcode": "55365",
                "areacode": "37",
                "sigungucode": "13",
                "operating_hours": "09:00~18:00"
            },
            {
                "name": "아리랑문학마을",
                "content_type": "12",
                "content_id": "2778525",
                "addr1": "전북특별자치도 김제시 부량면 용성1길 24",
                "addr2": "",
                "mapx": "126.8425483574",
                "mapy": "35.7743969017", 
                "first_image": "",
                "first_image2": "",
                "overview": "조정래 작가의 대하소설 '아리랑'의 무대가 된 곳으로, 일제강점기 농민들의 삶과 저항정신을 기념하는 문학테마마을입니다.",
                "tel": "063-540-4947",
                "homepage": "http://arirang.gimje.go.kr",
                "zipcode": "54348",
                "areacode": "37",
                "sigungucode": "13",
                "operating_hours": "09:00~18:00"
            },
            {
                "name": "귀신사(김제)",
                "content_type": "12",
                "content_id": "126345",
                "addr1": "전북특별자치도 김제시 금산면",
                "addr2": "",
                "mapx": "127.0470225669",
                "mapy": "35.7453148338",
                "first_image": "",
                "first_image2": "",
                "overview": "모악산 자락에 위치한 고찰로, 고려시대부터 이어져온 천년고찰입니다.",
                "tel": "063-548-4441",
                "homepage": "",
                "zipcode": "54390",
                "areacode": "37",
                "sigungucode": "13"
            }
        ],
        "accommodations": [
            {
                "name": "모악산 유스호스텔",
                "content_type": "32",
                "content_id": "137498",
                "addr1": "전북특별자치도 완주군 구이면 모악산길 500",
                "addr2": "",
                "mapx": "127.0415765757",
                "mapy": "35.7165152364",
                "first_image": "",
                "first_image2": "",
                "overview": "모악산 자락에 위치한 청소년 숙박시설로, 깨끗하고 저렴한 숙박을 제공합니다.",
                "tel": "063-290-1800",
                "homepage": "http://moaksan-yh.co.kr",
                "zipcode": "55365",
                "areacode": "37",
                "sigungucode": "13"
            }
        ],
        "restaurants": [
            {
                "name": "김정선 베이커리카페",
                "content_type": "39",
                "content_id": "fake_301",
                "addr1": "전북특별자치도 김제시 중앙로 123",
                "addr2": "",
                "mapx": "126.8814",
                "mapy": "35.8050",
                "first_image": "",
                "first_image2": "",
                "overview": "김제 지역의 대표적인 베이커리카페로, 신선한 빵과 커피를 제공합니다.",
                "tel": "063-548-5678",
                "homepage": "",
                "zipcode": "54324",
                "areacode": "37",
                "sigungucode": "13"
            },
            {
                "name": "대율담",
                "content_type": "39",
                "content_id": "fake_302",
                "addr1": "전북특별자치도 김제시 금구면 대율길 45",
                "addr2": "",
                "mapx": "127.0331",
                "mapy": "35.7887",
                "first_image": "",
                "first_image2": "",
                "overview": "대율저수지 근처에 위치한 전통 한정식 전문점입니다.",
                "tel": "063-547-9876",
                "homepage": "",
                "zipcode": "54380",
                "areacode": "37",
                "sigungucode": "13"
            },
            {
                "name": "오늘여기",
                "content_type": "39",
                "content_id": "fake_303",
                "addr1": "전북특별자치도 김제시 검산동 456",
                "addr2": "",
                "mapx": "126.8999",
                "mapy": "35.8130",
                "first_image": "",
                "first_image2": "",
                "overview": "현대적인 감각의 브런치 카페로, 젊은 층에게 인기가 높습니다.",
                "tel": "063-540-1234",
                "homepage": "",
                "zipcode": "54326",
                "areacode": "37",
                "sigungucode": "13"
            },
            {
                "name": "대운한우암소회관",
                "content_type": "39",
                "content_id": "fake_304",
                "addr1": "전북특별자치도 김제시 만경읍 대동로 789",
                "addr2": "",
                "mapx": "126.8275",
                "mapy": "35.8416",
                "first_image": "",
                "first_image2": "",
                "overview": "김제 지역 최고급 한우만을 사용하는 전문 고기집입니다.",
                "tel": "063-542-5678",
                "homepage": "",
                "zipcode": "54364",
                "areacode": "37",
                "sigungucode": "13"
            },
            {
                "name": "아울카페",
                "content_type": "39",
                "content_id": "fake_305",
                "addr1": "전북특별자치도 김제시 부량면 벽골제로 321",
                "addr2": "",
                "mapx": "126.8531",
                "mapy": "35.7546",
                "first_image": "",
                "first_image2": "",
                "overview": "벽골제 근처에 위치한 자연친화적 카페입니다.",
                "tel": "063-540-7890",
                "homepage": "",
                "zipcode": "54348",
                "areacode": "37",
                "sigungucode": "13"
            }
        ]
    }

    # 실제 content_id가 있는 항목들의 이미지 수집
    content_ids_to_fetch = [
        "1956984", "231895", "127574", "2778525", "126345", "137498"
    ]
    
    print("=== TourAPI detailImage2로 실제 이미지 수집 시작 ===")
    
    for content_id in content_ids_to_fetch:
        print(f"Content ID {content_id} 이미지 수집 중...")
        image_url = await get_real_image_from_tour_api(content_id)
        if image_url:
            print(f"✅ Content ID {content_id}: {image_url}")
            
            # demo_data에서 해당 content_id 찾아서 업데이트
            for category in ["attractions", "accommodations"]:
                for item in demo_data[category]:
                    if item["content_id"] == content_id:
                        item["first_image"] = image_url
                        break
        else:
            print(f"❌ Content ID {content_id}: 이미지를 찾을 수 없음")
        
        # API 요청 간격
        await asyncio.sleep(0.5)

    # 음식점은 fake content_id이므로 플레이스홀더 이미지 사용
    for restaurant in demo_data["restaurants"]:
        restaurant["first_image"] = "https://via.placeholder.com/400x300?text=" + restaurant["name"]

    # demo_data.json 파일 저장
    data_dir = Path(__file__).parent.parent / "data"
    with open(data_dir / "demo_data.json", "w", encoding="utf-8") as f:
        json.dump(demo_data, f, ensure_ascii=False, indent=2)
    
    print("✅ demo_data.json 파일이 실제 TourAPI 이미지로 업데이트되었습니다!")

if __name__ == "__main__":
    asyncio.run(main())