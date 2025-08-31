"""
scripts/filter_jeonbuk_tours.py
================================
TourAPI 데이터에서 전북 지역별로 분류하고 필터링하는 스크립트

System_Improvements.md 요구사항:
- 전북 14개 지역으로 분류
- 지역별 관광지 데이터 정리
- 이미지 URL이 있는 데이터만 추천 대상으로 사용
"""

import pandas as pd
import os
from app.utils.region_mapping import normalize_region_name, jeonbuk_regions
import requests
import time


def get_tour_detail_with_images(contentid: str, contenttypeid: str = "12") -> dict:
    """TourAPI에서 관광지 상세 정보 및 이미지 조회"""
    from app.config import get_settings
    
    settings = get_settings()
    
    # detailCommon API 호출 (개요 정보)
    detail_url = "http://apis.data.go.kr/B551011/KorService1/detailCommon1"
    detail_params = {
        'serviceKey': settings.tour_api_key,
        'numOfRows': 10,
        'pageNo': 1,
        'MobileOS': 'ETC',
        'MobileApp': 'AppTest',
        'contentId': contentid,
        'contentTypeId': contenttypeid,
        'defaultYN': 'Y',
        'firstImageYN': 'Y',
        'areacodeYN': 'Y',
        'catcodeYN': 'Y',
        'addrinfoYN': 'Y',
        'mapinfoYN': 'Y',
        'overviewYN': 'Y',
        '_type': 'json'
    }
    
    try:
        response = requests.get(detail_url, params=detail_params, verify=False)
        if response.status_code == 200:
            data = response.json()
            items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if items and len(items) > 0:
                item = items[0] if isinstance(items, list) else items
                return {
                    'overview': item.get('overview', ''),
                    'image_url': item.get('firstimage', ''),
                    'address': item.get('addr1', ''),
                    'sigungucode': item.get('sigungucode', ''),
                    'latitude': item.get('mapy', ''),
                    'longitude': item.get('mapx', '')
                }
    except Exception as e:
        print(f"⚠️ ContentID {contentid} 상세 정보 조회 실패: {e}")
    
    return {}


def extract_region_from_name_or_address(name: str, address: str = '') -> str:
    """관광지 이름이나 주소에서 전북 지역 추출"""
    # 이름에서 지역명 찾기
    for region in jeonbuk_regions.keys():
        region_short = region.replace('군', '').replace('시', '')
        if region_short in name or region in name:
            return region
    
    # 주소에서 지역명 찾기
    if address:
        for region in jeonbuk_regions.keys():
            if region in address:
                return region
    
    return None


def process_tour_files():
    """모든 TourAPI CSV 파일 처리"""
    print("🗺️ 전북 관광지 데이터 필터링 시작...")
    
    tour_files = [
        'tour_api_attractions.csv',
        'tour_api_courses.csv', 
        'tour_api_cultural.csv',
        'tour_api_festivals.csv',
        'tour_api_leisure.csv',
        'tour_api_shopping.csv'
    ]
    
    all_tours = []
    
    for file_name in tour_files:
        file_path = f'data/{file_name}'
        if not os.path.exists(file_path):
            print(f"⚠️ 파일 없음: {file_path}")
            continue
            
        print(f"📂 처리 중: {file_name}")
        df = pd.read_csv(file_path)
        
        processed_count = 0
        image_found_count = 0
        
        for _, row in df.iterrows():
            # 기본 정보
            contentid = str(row.get('contentid', ''))
            name = row.get('name', '')
            
            if not contentid or contentid == 'nan':
                continue
                
            # 지역 추출
            region = extract_region_from_name_or_address(name, '')
            
            if not region:
                continue  # 전북 지역이 아닌 경우 제외
            
            # 상세 정보 및 이미지 조회 (API 호출 제한으로 일부만 처리)
            detail_info = {}
            if processed_count < 5:  # 테스트용으로 5개만
                detail_info = get_tour_detail_with_images(contentid)
                time.sleep(0.1)  # API 호출 간격
            
            tour_data = {
                'name': name,
                'region': region,
                'contentid': contentid,
                'lat': row.get('lat', ''),
                'lon': row.get('lon', ''),
                'tags': row.get('tags', ''),
                'keywords': row.get('keywords', ''),
                'file_source': file_name,
                'overview': detail_info.get('overview', ''),
                'image_url': detail_info.get('image_url', ''),
                'address': detail_info.get('address', ''),
            }
            
            if detail_info.get('image_url'):
                image_found_count += 1
            
            all_tours.append(tour_data)
            processed_count += 1
        
        print(f"  ✅ {processed_count}개 처리 완료 (이미지 있음: {image_found_count}개)")
    
    # 결과 저장
    if all_tours:
        result_df = pd.DataFrame(all_tours)
        result_df.to_csv('data/jeonbuk_filtered_tours.csv', index=False, encoding='utf-8')
        print(f"💾 전체 {len(all_tours)}개 관광지 데이터 저장 완료")
        
        # 지역별 통계
        region_stats = result_df['region'].value_counts()
        print("\n📊 지역별 관광지 통계:")
        for region, count in region_stats.items():
            print(f"  {region}: {count}개")
        
        # 이미지가 있는 데이터 통계
        with_image_count = len(result_df[result_df['image_url'] != ''])
        print(f"\n🖼️ 이미지가 있는 관광지: {with_image_count}개 / {len(all_tours)}개")
    
    else:
        print("❌ 처리할 데이터가 없습니다.")


if __name__ == "__main__":
    process_tour_files()