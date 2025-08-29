#!/usr/bin/env python3
"""
TourAPI 연결 상태 확인 및 대안 방법 시도
"""

import requests
import urllib3
from pathlib import Path
import sys
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.insert(0, str(Path(__file__).parent))
from app.config import get_settings

def test_connection():
    """다양한 방법으로 TourAPI 연결 테스트"""
    settings = get_settings()
    
    # 1. 기본 연결 테스트 (간단한 API 호출)
    print("1. 기본 areaBasedList2 API 테스트...")
    url = f"{settings.tour_base_url}/areaBasedList2"
    params = {
        "ServiceKey": settings.tour_api_key,
        "numOfRows": "1",
        "pageNo": "1",
        "MobileOS": "ETC",
        "MobileApp": "KDT_DEMO",
        "_type": "json",
        "areaCode": "37",
        "sigunguCode": "13"
    }
    
    try:
        response = requests.get(url, params=params, verify=False, timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ 기본 API 연결 성공")
            return True
        else:
            print(f"   ❌ HTTP 오류: {response.text[:100]}")
    except Exception as e:
        print(f"   ❌ 연결 오류: {e}")
    
    # 2. 다른 SSL 설정으로 재시도
    print("\n2. SSL 설정 변경하여 재시도...")
    try:
        import ssl
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # requests의 adapter 설정
        session = requests.Session()
        session.verify = False
        
        response = session.get(url, params=params, timeout=15)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ SSL 설정 변경으로 연결 성공")
            return True
    except Exception as e:
        print(f"   ❌ SSL 설정 변경으로도 실패: {e}")
    
    return False

def try_detailImage_with_working_connection():
    """연결이 되는 경우 detailImage2 테스트"""
    settings = get_settings()
    
    print("\n3. detailImage2 API 테스트...")
    url = f"{settings.tour_base_url}/detailImage2"
    params = {
        "ServiceKey": settings.tour_api_key,
        "contentId": "231895",  # 김제 벽골제
        "MobileOS": "ETC",
        "MobileApp": "KDT_DEMO",
        "imageYN": "Y",
        "_type": "json",
        "numOfRows": "1",
        "pageNo": "1"
    }
    
    session = requests.Session()
    session.verify = False
    
    try:
        response = session.get(url, params=params, timeout=15)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {str(data)[:200]}...")
            
            if (data.get("response", {}).get("header", {}).get("resultCode") == "0000" and
                data.get("response", {}).get("body", {}).get("items")):
                items = data["response"]["body"]["items"]["item"]
                if isinstance(items, list):
                    image_url = items[0].get("originimgurl", "") if items else ""
                else:
                    image_url = items.get("originimgurl", "")
                print(f"   ✅ 이미지 URL 획득: {image_url}")
                return image_url
    except Exception as e:
        print(f"   ❌ detailImage2 오류: {e}")
    
    return ""

if __name__ == "__main__":
    print("=== TourAPI 연결 상태 확인 ===")
    
    if test_connection():
        image_url = try_detailImage_with_working_connection()
        if image_url:
            print(f"\n✅ 성공! 이미지 URL을 가져올 수 있습니다.")
            print("이제 get_images.py를 다시 실행해보세요.")
        else:
            print(f"\n❌ 기본 API는 되지만 detailImage2는 안됩니다.")
    else:
        print(f"\n❌ TourAPI 연결이 안 됩니다. 서버 문제이거나 일시적 장애일 수 있습니다.")
        print("나중에 다시 시도하거나, 현재 적용된 이미지 URL 패턴을 사용하세요.")