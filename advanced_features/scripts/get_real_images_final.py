#!/usr/bin/env python3
"""
올바른 파라미터로 detailImage2 호출하여 실제 이미지 수집
"""

import httpx
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from app.config import get_settings

def get_real_image_from_tourapi(content_id: str) -> str:
    """올바른 파라미터로 detailImage2 호출"""
    settings = get_settings()
    client = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))
    
    params = {
        "serviceKey": settings.tour_api_key,
        "contentId": content_id,
        "MobileOS": "ETC", 
        "MobileApp": "ruralplanner",
        "imageYN": "Y",
        "_type": "json",
        "numOfRows": "1",
        "pageNo": "1"
    }
    
    url = f"{settings.tour_base_url}/detailImage2"
    
    try:
        response = client.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if (data.get("response", {}).get("header", {}).get("resultCode") == "0000" and
                data.get("response", {}).get("body", {}).get("items")):
                
                items = data["response"]["body"]["items"]["item"]
                if isinstance(items, list) and len(items) > 0:
                    image_url = items[0].get("originimgurl", "")
                    print(f"  ✅ 실제 이미지: {image_url}")
                    return image_url
                elif isinstance(items, dict):
                    image_url = items.get("originimgurl", "")
                    print(f"  ✅ 실제 이미지: {image_url}")
                    return image_url
                else:
                    print(f"  ❌ 이미지 없음")
            else:
                result_msg = data.get("response", {}).get("header", {}).get("resultMsg", "")
                print(f"  ❌ API 오류: {result_msg}")
        else:
            print(f"  ❌ HTTP {response.status_code}")
    except Exception as e:
        print(f"  ❌ 예외: {e}")
    finally:
        client.close()
    
    return ""

def main():
    # demo_data.json 읽기
    with open("data/demo_data.json", "r", encoding="utf-8") as f:
        demo_data = json.load(f)
    
    print("=== TourAPI detailImage2로 실제 이미지 수집 ===")
    
    # 관광지 이미지 수집
    for attraction in demo_data["attractions"]:
        content_id = attraction["content_id"]
        if not content_id.startswith("fake"):
            print(f"\n{attraction['name']} (ID: {content_id})")
            image_url = get_real_image_from_tourapi(content_id)
            if image_url:
                attraction["first_image"] = image_url
    
    # 숙박시설 이미지 수집  
    for accommodation in demo_data["accommodations"]:
        content_id = accommodation["content_id"]
        if not content_id.startswith("fake"):
            print(f"\n{accommodation['name']} (ID: {content_id})")
            image_url = get_real_image_from_tourapi(content_id)
            if image_url:
                accommodation["first_image"] = image_url
    
    # 업데이트된 데이터 저장
    with open("data/demo_data.json", "w", encoding="utf-8") as f:
        json.dump(demo_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n🎉 실제 TourAPI 이미지로 demo_data.json 업데이트 완료!")

if __name__ == "__main__":
    main()