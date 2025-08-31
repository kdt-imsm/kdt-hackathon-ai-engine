"""
전북 14개 지역별 × 3개 타입별 데이터셋 생성기 (올바른 버전)
=======================================================
data/ 폴더의 기존 파일들을 활용하여 정확한 데이터셋 생성

데이터 소스:
1. 관광지: tour_api_*.csv 6개 파일 통합 (attractions, cultural, festivals, leisure, shopping, courses)
2. 숙박: accommodations.csv에서 전북만 추출
3. 음식점: restaurants.csv에서 전북만 추출

최종 결과: 14개 지역 × 3개 타입 = 42개 파일
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional

from app.utils.region_mapping import get_region_list

def classify_by_coordinates(lat: float, lon: float) -> Optional[str]:
    """좌표 기반 전북 14개 지역 분류"""
    if pd.isna(lat) or pd.isna(lon) or lat == 0 or lon == 0:
        return None
    
    # 전북 지역별 좌표 범위
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
    
    # 가장 가까운 지역 찾기
    min_distance = float('inf')
    closest_region = None
    
    for region, bounds in region_bounds.items():
        center_lat = (bounds["lat_min"] + bounds["lat_max"]) / 2
        center_lon = (bounds["lon_min"] + bounds["lon_max"]) / 2
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

def classify_by_region_field(region: str) -> Optional[str]:
    """전북 지역 필터링"""
    if not region or pd.isna(region):
        return None
        
    if "전북" in region or "전라북도" in region:
        return classify_by_address(region)
    
    return None

def process_tourism_data() -> Dict[str, List[dict]]:
    """6개 tour_api 파일을 통합하여 관광지 데이터 생성"""
    print("🎯 1단계: 관광지 데이터 통합 및 지역별 분류")
    print("=" * 60)
    
    # 6개 tour_api 파일 정의
    tour_files = [
        "tour_api_attractions.csv",
        "tour_api_cultural.csv", 
        "tour_api_festivals.csv",
        "tour_api_leisure.csv",
        "tour_api_shopping.csv",
        "tour_api_courses.csv"
    ]
    
    all_tourism_data = []
    regional_data = {region: [] for region in get_region_list()}
    
    for filename in tour_files:
        file_path = Path("data") / filename
        
        if not file_path.exists():
            print(f"⚠️ {filename} 파일이 없습니다.")
            continue
            
        try:
            df = pd.read_csv(file_path)
            print(f"📄 {filename}: {len(df)}건")
            
            classified_count = 0
            
            for idx, row in df.iterrows():
                region = None
                classification_method = ""
                
                # attractions 파일은 좌표 기반 분류
                if filename == "tour_api_attractions.csv":
                    lat = row.get('lat')
                    lon = row.get('lon')
                    if pd.notna(lat) and pd.notna(lon):
                        region = classify_by_coordinates(float(lat), float(lon))
                        if region:
                            classification_method = "좌표"
                else:
                    # 다른 파일들은 주소 기반 분류
                    addr = row.get('region', '')
                    region = classify_by_address(addr)
                    if region:
                        classification_method = "주소"
                
                if region:
                    data = {
                        "name": row.get('name', ''),
                        "region": region,
                        "address_full": row.get('region', ''),
                        "lat": row.get('lat'),
                        "lon": row.get('lon'),
                        "contentid": row.get('contentid', ''),
                        "image_url": row.get('image_url', ''),
                        "tags": row.get('tags', ''),
                        "keywords": row.get('keywords', ''),
                        "source_file": filename,
                        "classification_method": classification_method
                    }
                    regional_data[region].append(data)
                    classified_count += 1
            
            print(f"    분류 성공: {classified_count}/{len(df)}건")
            
        except Exception as e:
            print(f"❌ {filename} 처리 실패: {e}")
    
    print(f"\n🗺️ 지역별 관광지 분포:")
    total_count = 0
    for region in get_region_list():
        count = len(regional_data[region])
        if count > 0:
            print(f"    {region}: {count}건")
            total_count += count
    
    print(f"📊 총 관광지 데이터: {total_count}건")
    return regional_data

def process_accommodations_data() -> Dict[str, List[dict]]:
    """accommodations.csv에서 전북 데이터만 추출하여 지역별 분류"""
    print("\n🎯 2단계: 숙박 데이터 전북 추출 및 지역별 분류")
    print("=" * 60)
    
    regional_data = {region: [] for region in get_region_list()}
    
    file_path = Path("data/accommodations.csv")
    
    if not file_path.exists():
        print("❌ accommodations.csv 파일이 없습니다.")
        return regional_data
    
    try:
        df = pd.read_csv(file_path)
        print(f"📄 전체 숙박 데이터: {len(df)}건")
        
        jeonbuk_count = 0
        classified_count = 0
        
        for idx, row in df.iterrows():
            # 전북 지역 필터링
            region_field = row.get('region', '')
            
            if "전북" in region_field or "전라북도" in region_field:
                jeonbuk_count += 1
                
                # 지역 분류
                region = classify_by_address(region_field)
                
                if not region:
                    # 좌표로도 시도
                    lat = row.get('lat')
                    lon = row.get('lon') 
                    if pd.notna(lat) and pd.notna(lon):
                        region = classify_by_coordinates(float(lat), float(lon))
                
                if region:
                    data = {
                        "name": row.get('name', ''),
                        "region": region,
                        "address_full": region_field,
                        "lat": row.get('lat'),
                        "lon": row.get('lon'),
                        "contentid": row.get('contentid', ''),
                        "image_url": row.get('image_url', ''),
                        "tags": row.get('tags', ''),
                        "checkin_time": row.get('checkin_time', ''),
                        "checkout_time": row.get('checkout_time', ''),
                        "room_count": row.get('room_count', ''),
                        "parking": row.get('parking', ''),
                        "facilities": row.get('facilities', '')
                    }
                    regional_data[region].append(data)
                    classified_count += 1
        
        print(f"📊 전북 숙박 데이터: {jeonbuk_count}건")
        print(f"    분류 성공: {classified_count}건")
        
        print(f"\n🗺️ 지역별 숙박 분포:")
        for region in get_region_list():
            count = len(regional_data[region])
            if count > 0:
                print(f"    {region}: {count}건")
                
    except Exception as e:
        print(f"❌ 숙박 데이터 처리 실패: {e}")
    
    return regional_data

def process_restaurants_data() -> Dict[str, List[dict]]:
    """restaurants.csv에서 전북 데이터만 추출하여 지역별 분류"""
    print("\n🎯 3단계: 음식점 데이터 전북 추출 및 지역별 분류")
    print("=" * 60)
    
    regional_data = {region: [] for region in get_region_list()}
    
    file_path = Path("data/restaurants.csv")
    
    if not file_path.exists():
        print("❌ restaurants.csv 파일이 없습니다.")
        return regional_data
    
    try:
        df = pd.read_csv(file_path)
        print(f"📄 전체 음식점 데이터: {len(df)}건")
        
        jeonbuk_count = 0
        classified_count = 0
        
        for idx, row in df.iterrows():
            # 전북 지역 필터링
            region_field = row.get('region', '')
            
            if "전북" in region_field or "전라북도" in region_field:
                jeonbuk_count += 1
                
                # 지역 분류
                region = classify_by_address(region_field)
                
                if not region:
                    # 좌표로도 시도
                    lat = row.get('lat')
                    lon = row.get('lon')
                    if pd.notna(lat) and pd.notna(lon):
                        region = classify_by_coordinates(float(lat), float(lon))
                
                if region:
                    data = {
                        "name": row.get('name', ''),
                        "region": region,
                        "address_full": region_field,
                        "lat": row.get('lat'),
                        "lon": row.get('lon'),
                        "contentid": row.get('contentid', ''),
                        "image_url": row.get('image_url', ''),
                        "tags": row.get('tags', ''),
                        "menu": row.get('menu', ''),
                        "open_time": row.get('open_time', ''),
                        "rest_date": row.get('rest_date', ''),
                        "parking": row.get('parking', ''),
                        "reservation": row.get('reservation', ''),
                        "packaging": row.get('packaging', '')
                    }
                    regional_data[region].append(data)
                    classified_count += 1
        
        print(f"📊 전북 음식점 데이터: {jeonbuk_count}건")
        print(f"    분류 성공: {classified_count}건")
        
        print(f"\n🗺️ 지역별 음식점 분포:")
        for region in get_region_list():
            count = len(regional_data[region])
            if count > 0:
                print(f"    {region}: {count}건")
                
    except Exception as e:
        print(f"❌ 음식점 데이터 처리 실패: {e}")
    
    return regional_data

def save_final_datasets(tourism_data: Dict[str, List[dict]], 
                       accommodation_data: Dict[str, List[dict]],
                       restaurant_data: Dict[str, List[dict]]) -> List[str]:
    """전북 14개 지역별 × 3개 타입별 = 42개 최종 데이터셋 저장"""
    print("\n🎯 4단계: 42개 지역별 데이터셋 파일 저장")
    print("=" * 60)
    
    data_dir = Path("data2")
    data_dir.mkdir(exist_ok=True)
    
    # 기존 파일들 삭제 (새로 생성)
    for existing_file in data_dir.glob("jeonbuk_*.csv"):
        existing_file.unlink()
    
    saved_files = []
    regions = get_region_list()
    
    for region in regions:
        print(f"\n📁 {region} 데이터셋 생성 중...")
        
        # 1. 관광지 데이터
        tourism_file = f"jeonbuk_{region}_attractions.csv"
        tourism_path = data_dir / tourism_file
        
        tourism_items = tourism_data.get(region, [])
        if tourism_items:
            df_tourism = pd.DataFrame(tourism_items)
            df_tourism.to_csv(tourism_path, index=False, encoding='utf-8')
            print(f"    ✅ {tourism_file}: {len(df_tourism)}건")
        else:
            # 빈 파일도 헤더와 함께 생성
            empty_df = pd.DataFrame(columns=['name', 'region', 'address_full', 'lat', 'lon', 'contentid', 'image_url', 'tags', 'keywords'])
            empty_df.to_csv(tourism_path, index=False, encoding='utf-8')
            print(f"    📄 {tourism_file}: 0건")
        saved_files.append(tourism_file)
        
        # 2. 숙박 데이터
        accommodation_file = f"jeonbuk_{region}_accommodations.csv"
        accommodation_path = data_dir / accommodation_file
        
        accommodation_items = accommodation_data.get(region, [])
        if accommodation_items:
            df_accommodation = pd.DataFrame(accommodation_items)
            df_accommodation.to_csv(accommodation_path, index=False, encoding='utf-8')
            print(f"    ✅ {accommodation_file}: {len(df_accommodation)}건")
        else:
            # 빈 파일도 헤더와 함께 생성
            empty_df = pd.DataFrame(columns=['name', 'region', 'address_full', 'lat', 'lon', 'contentid', 'image_url', 'tags', 'checkin_time', 'checkout_time', 'room_count', 'parking', 'facilities'])
            empty_df.to_csv(accommodation_path, index=False, encoding='utf-8')
            print(f"    📄 {accommodation_file}: 0건")
        saved_files.append(accommodation_file)
        
        # 3. 음식점 데이터
        restaurant_file = f"jeonbuk_{region}_restaurants.csv"
        restaurant_path = data_dir / restaurant_file
        
        restaurant_items = restaurant_data.get(region, [])
        if restaurant_items:
            df_restaurant = pd.DataFrame(restaurant_items)
            df_restaurant.to_csv(restaurant_path, index=False, encoding='utf-8')
            print(f"    ✅ {restaurant_file}: {len(df_restaurant)}건")
        else:
            # 빈 파일도 헤더와 함께 생성
            empty_df = pd.DataFrame(columns=['name', 'region', 'address_full', 'lat', 'lon', 'contentid', 'image_url', 'tags', 'menu', 'open_time', 'rest_date', 'parking', 'reservation', 'packaging'])
            empty_df.to_csv(restaurant_path, index=False, encoding='utf-8')
            print(f"    📄 {restaurant_file}: 0건")
        saved_files.append(restaurant_file)
    
    return saved_files

def validate_final_datasets():
    """생성된 데이터셋 검증"""
    print("\n🎯 5단계: 최종 데이터셋 검증")
    print("=" * 60)
    
    data_dir = Path("data2")
    regions = get_region_list()
    types = ["attractions", "accommodations", "restaurants"]
    
    total_files = 0
    valid_files = 0
    total_records = 0
    
    print("📊 지역별 데이터 현황:")
    
    for region in regions:
        region_total = 0
        print(f"\n🗺️ {region}:")
        
        for data_type in types:
            filename = f"jeonbuk_{region}_{data_type}.csv"
            file_path = data_dir / filename
            
            total_files += 1
            
            if file_path.exists():
                try:
                    df = pd.read_csv(file_path)
                    record_count = len(df)
                    print(f"    {data_type}: {record_count}건")
                    region_total += record_count
                    total_records += record_count
                    valid_files += 1
                except Exception as e:
                    print(f"    {data_type}: 읽기 실패 - {e}")
            else:
                print(f"    {data_type}: 파일 없음")
        
        print(f"    소계: {region_total}건")
    
    print(f"\n📊 전체 검증 결과:")
    print(f"    생성된 파일: {valid_files}/{total_files}개")
    print(f"    전체 레코드: {total_records}건")
    print(f"    예상 파일: {len(regions) * len(types)}개 (14개 지역 × 3개 타입)")
    
    if valid_files == len(regions) * len(types):
        print(f"    🎉 42개 데이터셋 생성 완료!")
    else:
        print(f"    ⚠️ 일부 파일 누락 또는 오류")

def main():
    """메인 실행 함수"""
    print("🌟 전북 14개 지역별 × 3개 타입별 데이터셋 생성기 (올바른 버전)")
    print("=" * 70)
    print("📌 데이터 소스:")
    print("   1. 관광지: tour_api_*.csv 6개 파일 통합")
    print("   2. 숙박: accommodations.csv에서 전북 추출")
    print("   3. 음식점: restaurants.csv에서 전북 추출")
    print("📌 최종 결과: 14개 지역 × 3개 타입 = 42개 파일")
    print()
    
    try:
        # 1단계: 관광지 데이터 통합 처리
        tourism_data = process_tourism_data()
        
        # 2단계: 숙박 데이터 처리
        accommodation_data = process_accommodations_data()
        
        # 3단계: 음식점 데이터 처리
        restaurant_data = process_restaurants_data()
        
        # 4단계: 42개 데이터셋 파일 저장
        saved_files = save_final_datasets(tourism_data, accommodation_data, restaurant_data)
        
        # 5단계: 검증
        validate_final_datasets()
        
        print(f"\n✅ 전북 지역별 데이터셋 생성 완료!")
        print(f"📊 생성된 파일: {len(saved_files)}개")
        print(f"📁 저장 위치: data2/")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()