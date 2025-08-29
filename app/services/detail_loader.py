"""
detail_loader.py
================
실시간 상세정보 및 이미지 로드 서비스

숙박·음식점 카드 표시 시점에 TourAPI에서 실시간으로 이미지와 상세정보를 가져옵니다.
"""

import httpx
import time
from typing import Dict, Optional, List
from app.config import get_settings

# 설정 로드
settings = get_settings()
BASE_URL = settings.tour_base_url.rstrip("/")
SERVICE_KEY = settings.tour_api_key

# httpx 클라이언트 (타임아웃 설정)
CLIENT = httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0))


def fetch_detail_intro(contentid: str, content_type_id: int) -> Dict[str, str]:
    """detailIntro2 엔드포인트로 숙박/음식점 상세 정보를 실시간으로 가져옵니다."""
    if not contentid:
        return {}
        
    params = {
        "serviceKey": SERVICE_KEY,
        "MobileOS": "ETC",
        "MobileApp": "ruralplanner", 
        "contentId": contentid,
        "contentTypeId": content_type_id,
        "_type": "json"
    }
    
    url = f"{BASE_URL}/detailIntro2"
    
    try:
        r = CLIENT.get(url, params=params)
        r.raise_for_status()
        body = r.json()["response"]["body"]
        
        items_field = body.get("items")
        if not items_field:
            return {}
            
        if isinstance(items_field, dict):
            raw_items = items_field.get("item", [])
            items = raw_items if isinstance(raw_items, list) else [raw_items]
        elif isinstance(items_field, list):
            items = items_field
        else:
            return {}
            
        # 첫 번째 아이템의 상세 정보 반환
        if items and len(items) > 0:
            return items[0]
            
    except Exception as e:
        print(f"⚠️ 상세 정보 로드 실패 (contentid: {contentid}): {e}")
        
    return {}


def fetch_detail_image(contentid: str) -> Optional[str]:
    """detailImage2 엔드포인트로 이미지 URL을 실시간으로 가져옵니다."""
    if not contentid:
        return None
        
    params = {
        "serviceKey": SERVICE_KEY,
        "MobileOS": "ETC",
        "MobileApp": "ruralplanner",
        "contentId": contentid,
        "imageYN": "Y",
        "numOfRows": 1,
        "_type": "json"
    }
    
    url = f"{BASE_URL}/detailImage2"
    
    try:
        r = CLIENT.get(url, params=params)
        r.raise_for_status()
        body = r.json()["response"]["body"]
        
        items_field = body.get("items")
        if not items_field:
            return None
            
        if isinstance(items_field, dict):
            raw_items = items_field.get("item", [])
            items = raw_items if isinstance(raw_items, list) else [raw_items]
        elif isinstance(items_field, list):
            items = items_field
        else:
            return None
            
        if items and len(items) > 0:
            return items[0].get("originimgurl")
            
    except Exception as e:
        print(f"⚠️ 이미지 로드 실패 (contentid: {contentid}): {e}")
        
    return None


def enrich_accommodation_cards(accommodations: List[Dict]) -> List[Dict]:
    """숙박 카드에 실시간 상세정보와 이미지를 추가합니다."""
    enriched = []
    
    for acc in accommodations:
        contentid = acc.get('contentid')
        if contentid:
            # 실시간 상세정보 로드 (contentTypeId=32: 숙박)
            detail_info = fetch_detail_intro(contentid, 32)
            
            # 실시간 이미지 로드
            image_url = fetch_detail_image(contentid)
            
            # 기존 정보에 실시간 정보 추가/업데이트
            enriched_acc = acc.copy()
            enriched_acc.update({
                'image_url': image_url or acc.get('image_url'),
                'checkin_time': detail_info.get('checkintime') or acc.get('checkin_time'),
                'checkout_time': detail_info.get('checkouttime') or acc.get('checkout_time'),
                'room_count': detail_info.get('roomcount') or acc.get('room_count'),
                'parking': detail_info.get('parkinglodging') or acc.get('parking'),
                'facilities': detail_info.get('subfacility') or acc.get('facilities'),
            })
            
        else:
            enriched_acc = acc.copy()
            
        enriched.append(enriched_acc)
        time.sleep(0.1)  # API 호출 간격 조절
    
    return enriched


def enrich_restaurant_cards(restaurants: List[Dict]) -> List[Dict]:
    """음식점 카드에 실시간 상세정보와 이미지를 추가합니다."""
    enriched = []
    
    for rest in restaurants:
        contentid = rest.get('contentid')
        if contentid:
            # 실시간 상세정보 로드 (contentTypeId=39: 음식점)
            detail_info = fetch_detail_intro(contentid, 39)
            
            # 실시간 이미지 로드
            image_url = fetch_detail_image(contentid)
            
            # 기존 정보에 실시간 정보 추가/업데이트
            enriched_rest = rest.copy()
            enriched_rest.update({
                'image_url': image_url or rest.get('image_url'),
                'menu': detail_info.get('firstmenu') or rest.get('menu'),
                'open_time': detail_info.get('opentimefood') or rest.get('open_time'),
                'rest_date': detail_info.get('restdatefood') or rest.get('rest_date'),
                'parking': detail_info.get('parkingfood') or rest.get('parking'),
                'reservation': detail_info.get('reservationfood') or rest.get('reservation'),
                'packaging': detail_info.get('packing') or rest.get('packaging'),
            })
            
        else:
            enriched_rest = rest.copy()
            
        enriched.append(enriched_rest)
        time.sleep(0.1)  # API 호출 간격 조절
    
    return enriched