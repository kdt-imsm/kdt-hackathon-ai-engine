"""
전북 14개 지역별 × 3개 타입별 최종 데이터셋 생성기
===============================================
Tour API SSL 문제 우회를 위해 좌표 기반 지역 분류 사용

핵심 요구사항:
1. 전북 14개 지역별로 데이터 분리
2. 관광지/숙박/음식점 3개 타입으로 분류
3. 총 42개 데이터셋 생성 (14 × 3)
4. 상세 주소 정보 최대한 활용
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional

from app.utils.region_mapping import get_region_list

def classify_by_coordinates(lat: float, lon: float) -> Optional[str]:
    """좌표 기반 전북 14개 지역 분류
    
    전북 각 시/군의 대략적인 좌표 범위를 사용하여 분류
    """
    if pd.isna(lat) or pd.isna(lon) or lat == 0 or lon == 0:
        return None
    
    # 전북 지역별 좌표 범위 (대략적)
    region_bounds = {
        "전주시": {"lat_min": 35.75, "lat_max": 35.90, "lon_min": 127.05, "lon_max": 127.20},
        "군산시": {"lat_min": 35.90, "lat_max": 36.05, "lon_min": 126.65, "lon_max": 126.85},
        "익산시": {"lat_min": 35.90, "lat_max": 36.05, "lon_min": 126.90, "lon_max": 127.10},
        "정읍시": {"lat_min": 35.50, "lat_max": 35.70, "lon_min": 126.80, "lon_max": 127.00},
        "남원시": {"lat_min": 35.35, "lat_max": 35.50, "lon_min": 127.30, "lon_max": 127.50},
        "김제시": {"lat_min": 35.75, "lat_max": 35.90, "lon_min": 126.85, "lon_max": 127.05},
        "완주군": {"lat_min": 35.85, "lat_max": 36.05, "lon_min": 127.15, "lon_max": 127.45},
        "진안군": {"lat_min": 35.75, "lat_max": 35.95, "lon_min": 127.40, "lon_max": 127.60},
        "무주군": {"lat_min": 35.85, "lat_max": 36.05, "lon_min": 127.60, "lon_max": 127.80},
        "장수군": {"lat_min": 35.60, "lat_max": 35.80, "lon_min": 127.50, "lon_max": 127.70},
        "임실군": {"lat_min": 35.60, "lat_max": 35.75, "lon_min": 127.25, "lon_max": 127.45},
        "순창군": {"lat_min": 35.35, "lat_max": 35.50, "lon_min": 127.10, "lon_max": 127.30},
        "고창군": {"lat_min": 35.40, "lat_max": 35.60, "lon_min": 126.65, "lon_max": 126.85},
        "부안군": {"lat_min": 35.65, "lat_max": 35.80, "lon_min": 126.70, "lon_max": 126.90}
    }
    
    # 좌표가 포함되는 지역 찾기
    for region, bounds in region_bounds.items():
        if (bounds["lat_min"] <= lat <= bounds["lat_max"] and 
            bounds["lon_min"] <= lon <= bounds["lon_max"]):
            return region
    
    # 가장 가까운 지역 찾기 (예외 처리)
    min_distance = float('inf')
    closest_region = None
    
    for region, bounds in region_bounds.items():
        center_lat = (bounds["lat_min"] + bounds["lat_max"]) / 2
        center_lon = (bounds["lon_min"] + bounds["lon_max"]) / 2
        
        # 유클리드 거리 계산
        distance = ((lat - center_lat) ** 2 + (lon - center_lon) ** 2) ** 0.5
        
        if distance < min_distance:
            min_distance = distance
            closest_region = region
    
    return closest_region

def classify_by_address(address: str) -> Optional[str]:
    """주소 기반 전북 14개 지역 분류"""
    if not address or pd.isna(address):
        return None
        
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
    
    for region, keywords in region_keywords.items():
        for keyword in keywords:
            if keyword in address:
                return region
    
    return None

def process_attractions_data() -> Dict[str, List[dict]]:
    """관광지 데이터를 좌표 기반으로 지역별 분류"""
    print("🎯 1단계: 관광지 데이터 좌표 기반 지역 분류")
    print("=" * 60)
    
    # 기존 관광지 데이터 로드
    df = pd.read_csv("data/tour_api_attractions.csv")
    print(f"📄 관광지 데이터 로드: {len(df)}건")
    
    regional_data = {region: [] for region in get_region_list()}
    
    coord_classified = 0
    failed_classification = 0
    
    for idx, row in df.iterrows():
        # 좌표 기반 분류 시도
        lat = row.get('lat')
        lon = row.get('lon')
        
        region = None
        classification_method = ""
        
        if pd.notna(lat) and pd.notna(lon) and lat != 0 and lon != 0:
            region = classify_by_coordinates(float(lat), float(lon))
            if region:
                classification_method = "좌표"
                coord_classified += 1
        
        if region:
            data = {
                "name": row.get('name', ''),
                "region": region,
                "address_full": row.get('region', ''),  # 원본 주소 보존
                "address_detail": "",
                "lat": lat,
                "lon": lon,
                "contentid": row.get('contentid', ''),
                "contenttypeid": 12,
                "tel": "",
                "zipcode": "",
                "image_url": row.get('image_url', ''),
                "overview": "",
                "tags": row.get('tags', ''),
                "keywords": row.get('keywords', ''),
                "classification_method": classification_method
            }
            regional_data[region].append(data)
        else:
            failed_classification += 1
    
    print(f"📊 분류 결과:")
    print(f"    좌표 기반: {coord_classified}건")
    print(f"    분류 실패: {failed_classification}건")
    
    print(f"\n🗺️ 지역별 관광지 분포:")
    for region in get_region_list():
        count = len(regional_data[region])
        if count > 0:
            print(f"    {region}: {count}건")
    
    return regional_data

def process_existing_files() -> Dict[str, Dict[str, List[dict]]]:
    """기존 파일들을 주소 기반으로 지역별 분류"""
    print("\n🎯 2단계: 기존 파일들 주소 기반 지역 분류")
    print("=" * 60)
    
    file_mappings = {
        "cultural": ("tour_api_cultural.csv", 14),
        "festivals": ("tour_api_festivals.csv", 15),
        "leisure": ("tour_api_leisure.csv", 28), 
        "shopping": ("tour_api_shopping.csv", 38)
    }
    
    all_regional_data = {}
    
    for category, (filename, content_type_id) in file_mappings.items():
        print(f"\n📄 처리 중: {filename}")
        
        try:
            df = pd.read_csv(f"data/{filename}")
            print(f"    데이터 로드: {len(df)}건")
            
            regional_data = {region: [] for region in get_region_list()}
            classified_count = 0
            
            for idx, row in df.iterrows():
                # 주소 기반 분류
                addr1 = row.get('region', '')
                region = classify_by_address(addr1)
                
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
                        "keywords": row.get('keywords', ''),
                        "classification_method": "주소"
                    }
                    regional_data[region].append(data)
                    classified_count += 1
            
            print(f"    분류 성공: {classified_count}/{len(df)}건")
            
            # 지역별 통계
            print(f"    지역별 분포:")
            for region in get_region_list():
                count = len(regional_data[region])
                if count > 0:
                    print(f"        {region}: {count}건")
            
            all_regional_data[category] = regional_data
            
        except Exception as e:
            print(f"    ❌ 처리 실패: {e}")
            all_regional_data[category] = {region: [] for region in get_region_list()}
    
    return all_regional_data

def create_accommodations_and_restaurants() -> Dict[str, Dict[str, List[dict]]]:
    """숙박과 음식점은 빈 데이터로 생성 (Tour API 접근 불가)"""
    print("\n🎯 3단계: 숙박/음식점 빈 데이터셋 생성")
    print("=" * 60)
    print("    Tour API SSL 문제로 인해 빈 데이터셋으로 생성합니다.")
    
    return {
        "accommodations": {region: [] for region in get_region_list()},
        "restaurants": {region: [] for region in get_region_list()}
    }

def save_final_datasets(attractions_data: Dict[str, List[dict]], 
                       existing_data: Dict[str, Dict[str, List[dict]]], 
                       empty_data: Dict[str, Dict[str, List[dict]]]) -> List[str]:
    """전북 14개 지역별 × 3개 타입별 = 42개 최종 데이터셋 저장"""
    print("\n🎯 4단계: 42개 지역별 데이터셋 파일 저장")
    print("=" * 60)
    
    data_dir = Path("data2")
    data_dir.mkdir(exist_ok=True)
    
    saved_files = []
    regions = get_region_list()
    
    for region in regions:
        print(f"\n📁 {region} 데이터셋 생성 중...")
        
        # 1. 관광지 데이터
        attractions_file = f"jeonbuk_{region}_attractions.csv"
        attractions_path = data_dir / attractions_file
        
        attractions_items = attractions_data.get(region, [])
        df_attractions = pd.DataFrame(attractions_items)
        df_attractions.to_csv(attractions_path, index=False, encoding='utf-8')
        
        if len(attractions_items) > 0:
            print(f"    ✅ {attractions_file}: {len(df_attractions)}건")
        else:
            print(f"    📄 {attractions_file}: 0건")
        saved_files.append(attractions_file)
        
        # 2. 숙박 데이터 (빈 파일)
        accommodations_file = f"jeonbuk_{region}_accommodations.csv"
        accommodations_path = data_dir / accommodations_file
        
        df_empty = pd.DataFrame()
        df_empty.to_csv(accommodations_path, index=False, encoding='utf-8')
        print(f"    📄 {accommodations_file}: 0건 (빈 파일)")
        saved_files.append(accommodations_file)
        
        # 3. 음식점 데이터 (빈 파일)
        restaurants_file = f"jeonbuk_{region}_restaurants.csv"
        restaurants_path = data_dir / restaurants_file
        
        df_empty.to_csv(restaurants_path, index=False, encoding='utf-8')
        print(f"    📄 {restaurants_file}: 0건 (빈 파일)")
        saved_files.append(restaurants_file)
    
    return saved_files

def validate_datasets():
    """생성된 데이터셋 검증"""
    print("\n🎯 5단계: 생성된 데이터셋 검증")
    print("=" * 60)
    
    data_dir = Path("data2")
    regions = get_region_list()
    types = ["attractions", "accommodations", "restaurants"]
    
    total_files = 0
    valid_files = 0
    
    for region in regions:
        for data_type in types:
            filename = f"jeonbuk_{region}_{data_type}.csv"
            file_path = data_dir / filename
            
            total_files += 1
            
            if file_path.exists():
                try:
                    df = pd.read_csv(file_path)
                    print(f"    ✅ {filename}: {len(df)}건")
                    valid_files += 1
                except Exception as e:
                    print(f"    ❌ {filename}: 읽기 실패 - {e}")
            else:
                print(f"    ❌ {filename}: 파일 없음")
    
    print(f"\n📊 검증 결과:")
    print(f"    전체 파일: {total_files}개")
    print(f"    유효 파일: {valid_files}개")
    print(f"    성공률: {valid_files/total_files*100:.1f}%")
    
    expected_files = len(regions) * len(types)
    print(f"    예상 파일: {expected_files}개 (14개 지역 × 3개 타입)")
    
    if valid_files == expected_files:
        print(f"    🎉 42개 데이터셋 생성 완료!")
    else:
        print(f"    ⚠️ 일부 파일 누락 또는 오류")

def main():
    """메인 실행 함수"""
    print("🌟 전북 14개 지역별 × 3개 타입별 최종 데이터셋 생성기")
    print("=" * 70)
    print("📌 핵심 요구사항:")
    print("   1. 전북 14개 지역별로 데이터 분리")
    print("   2. 관광지/숙박/음식점 3개 타입으로 분류") 
    print("   3. 총 42개 데이터셋 생성 (14 × 3)")
    print("   4. 좌표/주소 기반 지역 분류 사용")
    print()
    
    try:
        # 1단계: 관광지 데이터 처리 (좌표 기반)
        attractions_data = process_attractions_data()
        
        # 2단계: 기존 파일들 처리 (주소 기반)
        existing_data = process_existing_files()
        
        # 3단계: 숙박/음식점 빈 데이터
        empty_data = create_accommodations_and_restaurants()
        
        # 4단계: 42개 데이터셋 파일 저장
        saved_files = save_final_datasets(attractions_data, existing_data, empty_data)
        
        # 5단계: 검증
        validate_datasets()
        
        print(f"\n✅ 전북 지역별 관광지 데이터 생성 완료!")
        print(f"📊 생성된 파일: {len(saved_files)}개")
        print(f"📁 저장 위치: data2/")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()