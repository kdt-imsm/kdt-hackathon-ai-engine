#!/usr/bin/env python3
"""
/detailImage2 엔드포인트로 각 content_id의 실제 이미지 가져오기
"""

import requests
import json
import urllib3
from pathlib import Path
import sys

# SSL 경고 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.insert(0, str(Path(__file__).parent))
from app.config import get_settings

def get_image_from_detail_api(content_id: str) -> str:
    """detailImage2 엔드포인트로 실제 이미지 URL 가져오기"""
    settings = get_settings()
    
    url = f"{settings.tour_base_url}/detailImage2"
    params = {
        "ServiceKey": settings.tour_api_key,
        "contentId": content_id,
        "MobileOS": "ETC",
        "MobileApp": "KDT_DEMO",
        "imageYN": "Y",
        "subImageYN": "Y", 
        "_type": "json",
        "numOfRows": "1",
        "pageNo": "1"
    }
    
    try:
        response = requests.get(url, params=params, verify=False, timeout=15)
        print(f"Content ID {content_id}: HTTP {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if (data.get("response", {}).get("header", {}).get("resultCode") == "0000" and
                data.get("response", {}).get("body", {}).get("items")):
                
                items = data["response"]["body"]["items"]["item"]
                if isinstance(items, list) and len(items) > 0:
                    image_url = items[0].get("originimgurl", "")
                    print(f"  ✅ 이미지: {image_url}")
                    return image_url
                elif isinstance(items, dict):
                    image_url = items.get("originimgurl", "")
                    print(f"  ✅ 이미지: {image_url}")
                    return image_url
                else:
                    print(f"  ❌ 이미지 없음")
            else:
                print(f"  ❌ API 응답 오류: {data.get('response', {}).get('header', {})}")
        else:
            print(f"  ❌ HTTP 오류: {response.text[:100]}")
    except Exception as e:
        print(f"  ❌ 예외: {e}")
    
    return ""

def main():
    # demo_data.json에서 실제 content_id들 읽기
    with open("data/demo_data.json", "r", encoding="utf-8") as f:
        demo_data = json.load(f)
    
    print("=== /detailImage2로 실제 이미지 수집 ===")
    
    # 관광지 이미지 수집
    for attraction in demo_data["attractions"]:
        content_id = attraction["content_id"]
        if not content_id.startswith("fake"):
            print(f"\n{attraction['name']} ({content_id})")
            image_url = get_image_from_detail_api(content_id)
            if image_url:
                attraction["first_image"] = image_url
    
    # 숙박시설 이미지 수집
    for accommodation in demo_data["accommodations"]:
        content_id = accommodation["content_id"]
        if not content_id.startswith("fake"):
            print(f"\n{accommodation['name']} ({content_id})")
            image_url = get_image_from_detail_api(content_id)
            if image_url:
                accommodation["first_image"] = image_url
    
    # 업데이트된 데이터 저장
    with open("data/demo_data.json", "w", encoding="utf-8") as f:
        json.dump(demo_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ demo_data.json 업데이트 완료")

if __name__ == "__main__":
    main()