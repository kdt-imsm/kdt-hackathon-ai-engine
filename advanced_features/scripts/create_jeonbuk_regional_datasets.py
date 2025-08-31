"""
전북 14개 지역별 × 3개 타입별 관광지 데이터 생성기
===============================================
Tour API에서 실제 상세 주소를 수집하여 
전북 14개 지역별로 관광지/숙박/음식점 데이터를 분리합니다.

핵심 요구사항:
1. 전북 14개 지역별로 데이터 분리
2. 관광지/숙박/음식점 3개 타입으로 분류  
3. 총 42개 데이터셋 생성 (14 × 3)
4. 상세 주소 정보 수집 (시/군 단위까지)
"""

import httpx
import pandas as pd
import time
import json
import ssl
import urllib3
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from app.config import get_settings
from app.utils.region_mapping import get_region_list

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 환경 설정
settings = get_settings()
BASE_URL = settings.tour_base_url.rstrip("/")
SERVICE_KEY = settings.tour_api_key

# SSL 컨텍스트 생성 (모든 검증 무시)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# httpx 클라이언트 SSL 우회 설정 강화
CLIENT = httpx.Client(
    timeout=httpx.Timeout(30.0, connect=15.0),
    verify=False,  # SSL 검증 완전 비활성화
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Connection': 'close'
    }
)

def classify_jeonbuk_region(addr1: str, addr2: str = "") -> Optional[str]:
    """실제 주소로 전북 14개 지역 분류"""
    if not addr1:
        return None
        
    full_address = f"{addr1} {addr2}".strip()
    
    # 전북 14개 지역 키워드 매핑 (정확도 순서)
    region_keywords = {
        "고창군": ["고창군", "고창읍", "고창"],
        "군산시": ["군산시", "군산"],
        "김제시": ["김제시", "김제"],
        "남원시": ["남원시", "남원"],
        "무주군": ["무주군", "무주읍", "무주"],
        "부안군": ["부안군", "부안읍", "부안"],
        "순창군": ["순창군", "순창읍", "순창"],
        "완주군": ["완주군", "완주"],
        "익산시": ["익산시", "익산"],
        "임실군": ["임실군", "임실읍", "임실"],
        "장수군": ["장수군", "장수읍", "장수"],
        "전주시": ["전주시", "전주", "완산구", "덕진구"],
        "정읍시": ["정읍시", "정읍"],
        "진안군": ["진안군", "진안읍", "진안"]
    }
    
    # 주소에서 지역 찾기
    for region, keywords in region_keywords.items():
        for keyword in keywords:
            if keyword in full_address:
                return region
    
    return None

def fetch_detail_with_retry(contentid: str, max_retries: int = 5) -> Optional[dict]:
    """다양한 방법으로 상세 주소 수집 시도"""
    
    # 방법 1: 기본 detailCommon2
    detail_info = fetch_detail_common_basic(contentid)
    if detail_info and detail_info.get("addr1"):
        return detail_info
    
    # 방법 2: 다른 파라미터로 재시도
    detail_info = fetch_detail_common_alternative(contentid)
    if detail_info and detail_info.get("addr1"):
        return detail_info
        
    return None

def fetch_detail_common_basic(contentid: str) -> Optional[dict]:
    """기본 detailCommon2 호출"""
    params = {
        "serviceKey": SERVICE_KEY,
        "MobileOS": "ETC",
        "MobileApp": "KDT-JeonbukTour",
        "_type": "json",
        "contentId": contentid,
        "defaultYN": "Y",
        "addrinfoYN": "Y",
        "mapinfoYN": "Y"
    }
    
    return call_detail_api(params)

def fetch_detail_common_alternative(contentid: str) -> Optional[dict]:
    """대안 파라미터로 detailCommon2 호출"""
    params = {
        "serviceKey": SERVICE_KEY,
        "MobileOS": "WIN",
        "MobileApp": "AppTest",
        "_type": "json",
        "contentId": contentid,
        "defaultYN": "Y",
        "addrinfoYN": "Y"
    }
    
    return call_detail_api(params)

def call_detail_api(params: dict) -> Optional[dict]:
    """실제 API 호출 (SSL 우회 강화)"""
    url = f"{BASE_URL}/detailCommon2"
    
    try:
        # requests 라이브러리로도 시도
        import requests
        requests.packages.urllib3.disable_warnings()
        
        response = requests.get(
            url, 
            params=params, 
            timeout=15,
            verify=False,  # SSL 검증 비활성화
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        response.raise_for_status()
        data = response.json()
        
        if "response" not in data:
            return None
            
        body = data["response"]["body"]
        if not body or body.get("totalCount", 0) == 0:
            return None
        
        items = body.get("items", {})
        if not items:
            return None
        
        item = items.get("item", {})
        if isinstance(item, list):
            item = item[0] if item else {}
            
        return item
        
    except Exception as e:
        try:
            # httpx로 재시도
            response = CLIENT.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if "response" not in data:
                return None
                
            body = data["response"]["body"]
            if not body or body.get("totalCount", 0) == 0:
                return None
            
            items = body.get("items", {})
            if not items:
                return None
            
            item = items.get("item", {})
            if isinstance(item, list):
                item = item[0] if item else {}
                
            return item
            
        except Exception as e2:
            return None

def process_attractions_data():
    """관광지 데이터 처리 - 상세 주소 수집하여 지역별 분리"""
    print("🎯 1단계: 관광지 데이터 상세 주소 수집 및 지역별 분리")
    print("=" * 70)
    
    # 기존 관광지 데이터 로드
    df = pd.read_csv("data/tour_api_attractions.csv")
    print(f"📄 관광지 데이터 로드: {len(df)}건")
    
    # contentid가 있는 데이터만 처리
    df_with_contentid = df[df['contentid'].notna()].copy()
    print(f"📊 처리 대상: {len(df_with_contentid)}건 (contentid 보유)")
    
    regional_data = {region: [] for region in get_region_list()}
    failed_data = []
    
    processed_count = 0
    success_count = 0
    
    for idx, row in df_with_contentid.iterrows():
        contentid = str(row['contentid']).strip()
        title = row['name']
        processed_count += 1
        
        print(f"[{processed_count}/{len(df_with_contentid)}] {title}")
        
        # 상세 정보 수집
        detail_info = fetch_detail_with_retry(contentid)
        
        if detail_info and detail_info.get("addr1"):
            addr1 = detail_info.get("addr1", "")
            addr2 = detail_info.get("addr2", "")
            region = classify_jeonbuk_region(addr1, addr2)
            
            print(f"    ✅ 주소: {addr1}")
            if region:
                print(f"    🗺️ 분류: {region}")
                
                # 데이터 병합
                merged_data = {
                    "name": title,
                    "region": region,
                    "address_full": addr1,
                    "address_detail": addr2,
                    "lat": row.get('lat'),
                    "lon": row.get('lon'),
                    "contentid": contentid,
                    "contenttypeid": 12,
                    "tel": detail_info.get("tel", ""),
                    "zipcode": detail_info.get("zipcode", ""),
                    "image_url": detail_info.get("firstimage", ""),
                    "overview": detail_info.get("overview", ""),
                    "tags": row.get('tags', ''),
                    "keywords": row.get('keywords', '')
                }
                
                regional_data[region].append(merged_data)
                success_count += 1
            else:
                print(f"    ⚠️ 지역 분류 실패: {addr1}")
                failed_data.append(row.to_dict())
        else:
            print(f"    ❌ 상세 정보 수집 실패")
            failed_data.append(row.to_dict())
        
        # 진행 상황 출력
        if processed_count % 50 == 0:
            print(f"\n📊 진행 상황: {processed_count}/{len(df_with_contentid)} ({processed_count/len(df_with_contentid)*100:.1f}%)")
            print(f"    성공: {success_count}건, 실패: {len(failed_data)}건")
            
            # 중간 결과 출력
            region_counts = {region: len(items) for region, items in regional_data.items() if items}
            print(f"    지역별 수집: {region_counts}")
            print()
        
        # API 안정성을 위한 대기 (중요!)
        time.sleep(0.2)
    
    print(f"\n📊 관광지 데이터 처리 완료:")
    print(f"    총 처리: {processed_count}건")
    print(f"    성공: {success_count}건")
    print(f"    실패: {len(failed_data)}건")
    
    # 지역별 통계
    print(f"\n🗺️ 지역별 관광지 분포:")
    for region in get_region_list():
        count = len(regional_data[region])
        if count > 0:
            print(f"    {region}: {count}건")
    
    return regional_data, failed_data

def process_existing_data():
    """기존 파일들의 데이터를 지역별로 분리"""
    print("\n🎯 2단계: 기존 파일들 지역별 분리")
    print("=" * 70)
    
    file_mappings = {
        "tour_api_cultural.csv": ("cultural", 14),
        "tour_api_festivals.csv": ("festivals", 15), 
        "tour_api_leisure.csv": ("leisure", 28),
        "tour_api_shopping.csv": ("shopping", 38)
    }
    
    all_regional_data = {}
    
    for filename, (category, content_type_id) in file_mappings.items():
        print(f"\n📄 처리 중: {filename}")
        
        try:
            df = pd.read_csv(f"data/{filename}")
            print(f"    데이터 로드: {len(df)}건")
            
            regional_data = {region: [] for region in get_region_list()}
            
            for idx, row in df.iterrows():
                addr1 = row.get('region', '')  # region 필드에 이미 상세 주소가 있음
                region = classify_jeonbuk_region(addr1)
                
                if region:
                    data = {
                        "name": row.get('name', ''),
                        "region": region,
                        "address_full": addr1,
                        "address_detail": "",
                        "lat": row.get('lat'),
                        "lon": row.get('lon'), 
                        "contentid": row.get('contentid', ''),
                        "contenttypeid": content_type_id,
                        "tel": "",
                        "zipcode": "",
                        "image_url": row.get('image_url', ''),
                        "overview": "",
                        "tags": row.get('tags', ''),
                        "keywords": row.get('keywords', '')
                    }
                    regional_data[region].append(data)
            
            # 통계 출력
            print(f"    지역별 분포:")
            for region in get_region_list():
                count = len(regional_data[region])
                if count > 0:
                    print(f"        {region}: {count}건")
            
            all_regional_data[category] = regional_data
            
        except Exception as e:
            print(f"    ❌ 처리 실패: {e}")
    
    return all_regional_data

def create_accommodations_and_restaurants():
    """숙박과 음식점 데이터를 Tour API로 새로 수집"""
    print("\n🎯 3단계: 숙박/음식점 데이터 Tour API 수집")
    print("=" * 70)
    
    content_types = {
        32: "accommodations",  # 숙박
        39: "restaurants"      # 음식점  
    }
    
    all_data = {}
    
    for content_type_id, type_name in content_types.items():
        print(f"\n📡 {type_name} (contentType: {content_type_id}) 수집 중...")
        
        # areaBasedList2로 전북 지역 데이터 수집
        all_items = []
        page = 1
        
        while True:
            items, total_count = fetch_area_based_list(content_type_id, page)
            if not items:
                break
            all_items.extend(items)
            
            total_pages = (total_count + 99) // 100
            if page >= total_pages:
                break
            page += 1
            time.sleep(0.3)
        
        print(f"    기본 정보 수집: {len(all_items)}건")
        
        if not all_items:
            all_data[type_name] = {region: [] for region in get_region_list()}
            continue
        
        # 상세 주소 수집 및 지역별 분류
        regional_data = {region: [] for region in get_region_list()}
        
        for item in all_items[:100]:  # 테스트용 100개만
            contentid = item.get("contentid")
            if not contentid:
                continue
            
            detail_info = fetch_detail_with_retry(contentid)
            
            if detail_info and detail_info.get("addr1"):
                addr1 = detail_info.get("addr1", "")
                addr2 = detail_info.get("addr2", "")
                region = classify_jeonbuk_region(addr1, addr2)
                
                if region:
                    data = {
                        "name": item.get("title", ""),
                        "region": region,
                        "address_full": addr1,
                        "address_detail": addr2,
                        "lat": float(item.get("mapy", 0)) if item.get("mapy") else None,
                        "lon": float(item.get("mapx", 0)) if item.get("mapx") else None,
                        "contentid": contentid,
                        "contenttypeid": content_type_id,
                        "tel": detail_info.get("tel", ""),
                        "zipcode": detail_info.get("zipcode", ""),
                        "image_url": detail_info.get("firstimage", ""),
                        "overview": detail_info.get("overview", ""),
                        "tags": "",
                        "keywords": ""
                    }
                    regional_data[region].append(data)
            
            time.sleep(0.2)
        
        # 통계 출력
        print(f"    지역별 분포:")
        for region in get_region_list():
            count = len(regional_data[region])
            if count > 0:
                print(f"        {region}: {count}건")
        
        all_data[type_name] = regional_data
    
    return all_data

def fetch_area_based_list(content_type_id: int, page: int = 1) -> Tuple[List[dict], int]:
    """areaBasedList2 API 호출"""
    params = {
        "serviceKey": SERVICE_KEY,
        "MobileOS": "ETC",
        "MobileApp": "KDT-JeonbukTour",
        "_type": "json",
        "arrange": "A",
        "numOfRows": 100,
        "pageNo": page,
        "areaCode": 37,  # 전북
        "contentTypeId": content_type_id
    }
    
    url = f"{BASE_URL}/areaBasedList2"
    
    try:
        response = CLIENT.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "response" not in data:
            return [], 0
        
        body = data["response"].get("body", {})
        if not body or body.get("totalCount", 0) == 0:
            return [], 0
        
        items = body.get("items", {})
        if not items:
            return [], body.get("totalCount", 0)
        
        item_list = items.get("item", [])
        if not isinstance(item_list, list):
            item_list = [item_list]
        
        return item_list, body.get("totalCount", 0)
        
    except Exception as e:
        print(f"    ❌ API 호출 실패: {e}")
        return [], 0

def save_regional_datasets(attractions_data, existing_data, new_data):
    """전북 14개 지역별 × 3개 타입별 = 42개 데이터셋 저장"""
    print("\n🎯 4단계: 42개 지역별 데이터셋 파일 저장")
    print("=" * 70)
    
    data_dir = Path("data2")
    data_dir.mkdir(exist_ok=True)
    
    saved_files = []
    regions = get_region_list()
    
    for region in regions:
        print(f"\n📁 {region} 데이터셋 생성 중...")
        
        # 1. 관광지 파일
        attractions_file = f"jeonbuk_{region}_attractions.csv"
        attractions_path = data_dir / attractions_file
        
        if region in attractions_data and attractions_data[region]:
            df = pd.DataFrame(attractions_data[region])
            df.to_csv(attractions_path, index=False, encoding='utf-8')
            print(f"    ✅ {attractions_file}: {len(df)}건")
            saved_files.append(attractions_file)
        else:
            # 빈 파일이라도 생성
            pd.DataFrame().to_csv(attractions_path, index=False, encoding='utf-8')
            print(f"    📄 {attractions_file}: 0건 (빈 파일)")
            saved_files.append(attractions_file)
        
        # 2. 숙박 파일  
        accommodations_file = f"jeonbuk_{region}_accommodations.csv"
        accommodations_path = data_dir / accommodations_file
        
        accommodations_items = new_data.get("accommodations", {}).get(region, [])
        if accommodations_items:
            df = pd.DataFrame(accommodations_items)
            df.to_csv(accommodations_path, index=False, encoding='utf-8')
            print(f"    ✅ {accommodations_file}: {len(df)}건")
        else:
            pd.DataFrame().to_csv(accommodations_path, index=False, encoding='utf-8')
            print(f"    📄 {accommodations_file}: 0건 (빈 파일)")
        saved_files.append(accommodations_file)
        
        # 3. 음식점 파일
        restaurants_file = f"jeonbuk_{region}_restaurants.csv"  
        restaurants_path = data_dir / restaurants_file
        
        restaurants_items = new_data.get("restaurants", {}).get(region, [])
        if restaurants_items:
            df = pd.DataFrame(restaurants_items)
            df.to_csv(restaurants_path, index=False, encoding='utf-8')
            print(f"    ✅ {restaurants_file}: {len(df)}건")
        else:
            pd.DataFrame().to_csv(restaurants_path, index=False, encoding='utf-8')
            print(f"    📄 {restaurants_file}: 0건 (빈 파일)")
        saved_files.append(restaurants_file)
    
    print(f"\n🎉 전북 14개 지역별 × 3개 타입별 데이터셋 생성 완료!")
    print(f"📊 총 생성 파일: {len(saved_files)}개")
    print(f"📁 저장 위치: {data_dir}/")
    
    return saved_files

def main():
    """메인 실행 함수"""
    print("🌟 전북 14개 지역별 × 3개 타입별 관광지 데이터 생성기")
    print("=" * 70)
    print("📌 핵심 요구사항:")
    print("   1. 전북 14개 지역별로 데이터 분리") 
    print("   2. 관광지/숙박/음식점 3개 타입으로 분류")
    print("   3. 총 42개 데이터셋 생성 (14 × 3)")
    print("   4. 상세 주소 정보 수집 (시/군 단위까지)")
    print()
    
    try:
        # 1단계: 관광지 데이터 처리 (가장 중요!)
        attractions_data, failed_attractions = process_attractions_data()
        
        # 2단계: 기존 파일들 처리 
        existing_data = process_existing_data()
        
        # 3단계: 숙박/음식점 신규 수집
        new_data = create_accommodations_and_restaurants()
        
        # 4단계: 42개 데이터셋 파일 저장
        saved_files = save_regional_datasets(attractions_data, existing_data, new_data)
        
        print(f"\n✅ 전북 지역별 관광지 데이터 생성 완료!")
        print(f"📁 생성된 파일: {len(saved_files)}개")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()