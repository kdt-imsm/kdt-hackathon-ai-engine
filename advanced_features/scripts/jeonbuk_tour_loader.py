"""
scripts/jeonbuk_tour_loader.py
===============================
전북 14개 지역별 × 3개 타입별 관광지 데이터 수집 및 저장

요구사항:
1. 전북 14개 지역별로 데이터 분리
2. 관광지/숙박/음식점 3개 타입으로 분류  
3. 총 42개 데이터셋 생성
4. 상세 주소 정보 수집 (시/군 단위까지)
"""

import httpx
import pandas as pd
import time
import json
import ssl
from pathlib import Path
from typing import List, Dict, Optional
from app.config import get_settings
from app.utils.region_mapping import jeonbuk_regions
from app.db.database import SessionLocal, Base, engine
from app.db.models import TourSpot
from app.embeddings.embedding_service import embed_texts
from sqlalchemy import func

# 설정
settings = get_settings()

# SSL 우회를 위한 설정
ssl_context = httpx.create_ssl_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

CLIENT = httpx.Client(
    timeout=httpx.Timeout(30.0, connect=10.0), 
    verify=False,
    http2=False
)

# TourAPI contentTypeId 매핑
CONTENT_TYPES = {
    'attractions': [12, 14, 15, 25, 28, 38],  # 관광지, 문화시설, 축제, 여행코스, 레포츠, 쇼핑
    'accommodations': [32],  # 숙박
    'restaurants': [39]      # 음식점
}

def get_detailed_address(contentid: str) -> Dict[str, str]:
    """detailCommon1 API로 상세 주소 정보 가져오기"""
    url = "https://apis.data.go.kr/B551011/KorService1/detailCommon1"
    params = {
        'serviceKey': settings.tour_api_key,
        'contentId': contentid,
        'MobileOS': 'ETC', 
        'MobileApp': 'TestApp',
        'defaultYN': 'Y',
        'addrinfoYN': 'Y',
        '_type': 'json'
    }
    
    try:
        response = CLIENT.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if items:
                item = items[0] if isinstance(items, list) else items
                return {
                    'addr1': item.get('addr1', ''),  # 기본 주소
                    'addr2': item.get('addr2', ''),  # 상세 주소
                    'zipcode': item.get('zipcode', ''),
                    'homepage': item.get('homepage', ''),
                    'overview': item.get('overview', '')
                }
    except Exception as e:
        print(f"⚠️ ContentID {contentid} 상세 주소 조회 실패: {e}")
    
    return {}

def extract_region_from_address(addr1: str, addr2: str = '') -> Optional[str]:
    """주소에서 전북 14개 지역 중 하나 추출"""
    full_address = f"{addr1} {addr2}".strip()
    
    # 전북 지역명 직접 매칭
    for region in jeonbuk_regions.keys():
        if region in full_address:
            return region
        # 시/군 제외한 이름으로도 검색
        region_short = region.replace('군', '').replace('시', '')
        if region_short in full_address and len(region_short) > 1:
            return region
    
    return None

def collect_jeonbuk_data_by_region_and_type():
    """전북 14개 지역 × 3개 타입별 데이터 수집"""
    
    print("🗺️ 전북 14개 지역별 × 3개 타입별 관광지 데이터 수집 시작")
    
    # 전북(지역코드 37) 데이터 수집
    all_data = []
    
    for content_type_name, type_ids in CONTENT_TYPES.items():
        for type_id in type_ids:
            print(f"📋 수집 중: {content_type_name} (contentTypeId: {type_id})")
            
            page = 1
            while page <= 10:  # 최대 10페이지
                url = "https://apis.data.go.kr/B551011/KorService1/areaBasedList1"
                params = {
                    'serviceKey': settings.tour_api_key,
                    'numOfRows': 100,
                    'pageNo': page,
                    'MobileOS': 'ETC',
                    'MobileApp': 'TestApp', 
                    'areaCode': 37,  # 전북특별자치도
                    'contentTypeId': type_id,
                    '_type': 'json'
                }
                
                try:
                    response = CLIENT.get(url, params=params)
                    if response.status_code != 200:
                        print(f"❌ API 호출 실패: {response.status_code}")
                        break
                        
                    data = response.json()
                    items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
                    
                    if not items:
                        print(f"📄 페이지 {page}: 데이터 없음 - 수집 완료")
                        break
                    
                    if isinstance(items, dict):
                        items = [items]
                    
                    print(f"📄 페이지 {page}: {len(items)}개 항목 처리 중...")
                    
                    for item in items:
                        # 기본 정보
                        contentid = item.get('contentid', '')
                        title = item.get('title', '')
                        addr1 = item.get('addr1', '')
                        
                        if not contentid or not title:
                            continue
                        
                        # 상세 주소 정보 가져오기 (일부만 - API 제한)
                        detailed_info = {}
                        if len(all_data) % 20 == 0:  # 20개 중 1개만 상세 조회
                            detailed_info = get_detailed_address(contentid)
                            time.sleep(0.1)
                        
                        addr2 = detailed_info.get('addr2', '')
                        
                        # 전북 지역 추출
                        region = extract_region_from_address(addr1, addr2)
                        
                        if not region:
                            print(f"⚠️ 지역을 찾을 수 없음: {title} - {addr1}")
                            continue
                        
                        # 데이터 저장
                        all_data.append({
                            'contentid': contentid,
                            'name': title,
                            'content_type': content_type_name,
                            'content_type_id': type_id,
                            'region': region,
                            'addr1': addr1,
                            'addr2': addr2,
                            'lat': float(item.get('mapy', 0)) if item.get('mapy') else None,
                            'lon': float(item.get('mapx', 0)) if item.get('mapx') else None,
                            'overview': detailed_info.get('overview', ''),
                            'homepage': detailed_info.get('homepage', ''),
                        })
                    
                    page += 1
                    time.sleep(0.5)  # API 호출 간격
                    
                except Exception as e:
                    print(f"❌ 페이지 {page} 수집 실패: {e}")
                    break
    
    print(f"🎯 총 수집된 데이터: {len(all_data)}개")
    
    # 지역별/타입별 분류 및 저장
    save_data_by_region_and_type(all_data)
    
    # 데이터베이스에 저장
    save_to_database(all_data)

def save_data_by_region_and_type(all_data: List[Dict]):
    """지역별/타입별로 데이터 분리 저장"""
    
    data_dir = Path('data/jeonbuk_regions')
    data_dir.mkdir(exist_ok=True)
    
    # 지역별/타입별 분류
    region_type_data = {}
    
    for item in all_data:
        region = item['region']
        content_type = item['content_type']
        
        key = f"{region}_{content_type}"
        if key not in region_type_data:
            region_type_data[key] = []
        
        region_type_data[key].append(item)
    
    # CSV 파일로 저장
    saved_count = 0
    for key, data_list in region_type_data.items():
        if not data_list:
            continue
            
        filename = f"{key}.csv"
        filepath = data_dir / filename
        
        df = pd.DataFrame(data_list)
        df.to_csv(filepath, index=False, encoding='utf-8')
        
        print(f"💾 저장: {filename} ({len(data_list)}개)")
        saved_count += 1
    
    print(f"✅ 총 {saved_count}개 파일 저장 완료")
    
    # 통계 출력
    print("\n📊 지역별 통계:")
    region_stats = {}
    for item in all_data:
        region = item['region']
        region_stats[region] = region_stats.get(region, 0) + 1
    
    for region, count in sorted(region_stats.items()):
        print(f"  {region}: {count}개")
    
    print("\n📊 타입별 통계:")
    type_stats = {}
    for item in all_data:
        content_type = item['content_type']
        type_stats[content_type] = type_stats.get(content_type, 0) + 1
    
    for content_type, count in type_stats.items():
        print(f"  {content_type}: {count}개")

def save_to_database(all_data: List[Dict]):
    """데이터베이스에 저장 (벡터 임베딩 포함)"""
    
    print("🗄️ 데이터베이스 저장 시작...")
    
    # 테이블 생성
    Base.metadata.create_all(bind=engine)
    
    with SessionLocal() as db:
        # 기존 TourSpot 데이터 삭제
        db.query(TourSpot).delete()
        db.commit()
        
        # 벡터화를 위한 텍스트 준비
        tour_texts = []
        tour_data = []
        
        for item in all_data:
            # 관광지 정보를 텍스트로 결합
            text_parts = [
                item['name'],
                item['region'],
                item.get('overview', ''),
                f"{item['content_type']} 관광"
            ]
            tour_text = ' '.join(filter(None, text_parts))
            tour_texts.append(tour_text)
            tour_data.append(item)
        
        print(f"📊 {len(tour_texts)}개 관광지 텍스트 벡터화 중...")
        
        # 벡터화
        try:
            tour_vectors = embed_texts(tour_texts)
            print(f"✅ 벡터화 완료: {len(tour_vectors)}개")
        except Exception as e:
            print(f"❌ 벡터화 실패: {e}")
            tour_vectors = []
        
        # 데이터베이스 저장
        saved_count = 0
        for i, item in enumerate(tour_data):
            vector = tour_vectors[i] if i < len(tour_vectors) else None
            
            tour_spot = TourSpot(
                name=item['name'],
                region=item['region'],  # 이제 구체적인 지역명
                tags=item['content_type'],
                lat=item['lat'],
                lon=item['lon'],
                contentid=item['contentid'],
                pref_vector=vector
            )
            
            db.add(tour_spot)
            saved_count += 1
        
        db.commit()
        
        print(f"✅ {saved_count}개 관광지 데이터 DB 저장 완료")
        
        # 저장 결과 확인
        region_stats = db.query(TourSpot.region, func.count(TourSpot.id)).group_by(TourSpot.region).all()
        print("\n📊 DB 저장 결과 - 지역별 통계:")
        for region, count in region_stats:
            print(f"  {region}: {count}개")

if __name__ == "__main__":
    collect_jeonbuk_data_by_region_and_type()