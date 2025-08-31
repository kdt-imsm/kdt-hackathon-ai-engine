"""
기존 tour_api CSV 데이터를 데이터베이스에 로드하고 벡터화
"""

import pandas as pd
from pathlib import Path
from app.db.database import SessionLocal, Base, engine
from app.db.models import TourSpot
from app.embeddings.embedding_service import embed_texts
from app.utils.region_mapping import normalize_region_name
from sqlalchemy import func

def load_existing_tour_data():
    """기존 CSV 데이터를 데이터베이스에 로드"""
    
    print("🗄️ 기존 관광지 CSV 데이터 로드 시작...")
    
    # 테이블 생성
    Base.metadata.create_all(bind=engine)
    
    # 데이터 파일들
    data_dir = Path('data')
    csv_files = [
        'tour_api_attractions.csv',
        'tour_api_cultural.csv', 
        'tour_api_festivals.csv',
        'tour_api_leisure.csv',
        'tour_api_shopping.csv'
    ]
    
    all_data = []
    
    # CSV 파일들 읽기
    for csv_file in csv_files:
        file_path = data_dir / csv_file
        if file_path.exists():
            print(f"📋 로드 중: {csv_file}")
            df = pd.read_csv(file_path)
            
            # 전북 지역 데이터만 필터링 (이미 전북 데이터만 있음)
            jeonbuk_data = []
            for _, row in df.iterrows():
                region_info = str(row.get('region', ''))
                if '전북' in region_info or '전라북도' in region_info:
                    # ContentID 기반으로 지역명 추출 (임시로 전주시 사용)
                    region = "전주시"  # 기본값으로 전주시 설정
                    
                    jeonbuk_data.append({
                        'name': str(row.get('name', '')),
                        'region': region,
                        'addr1': region_info,
                        'contentid': str(row.get('contentid', '')),
                        'tags': csv_file.replace('tour_api_', '').replace('.csv', ''),
                        'lat': float(row.get('lat', 0)) if pd.notna(row.get('lat')) else None,
                        'lon': float(row.get('lon', 0)) if pd.notna(row.get('lon')) else None,
                    })
            
            print(f"  전북 데이터: {len(jeonbuk_data)}개")
            all_data.extend(jeonbuk_data)
    
    print(f"🎯 총 전북 관광지 데이터: {len(all_data)}개")
    
    # 데이터베이스에 저장
    save_to_database(all_data)

def extract_jeonbuk_region(addr: str) -> str:
    """주소에서 전북 지역명 추출"""
    jeonbuk_regions = [
        '고창군', '군산시', '김제시', '남원시', '무주군', '부안군', '순창군',
        '완주군', '익산시', '임실군', '장수군', '전주시', '정읍시', '진안군'
    ]
    
    for region in jeonbuk_regions:
        if region in addr:
            return region
        # 시/군 제외한 이름으로도 검색
        region_short = region.replace('군', '').replace('시', '')
        if region_short in addr and len(region_short) > 1:
            return region
    
    return None

def save_to_database(all_data):
    """데이터베이스에 저장 (벡터 임베딩 포함)"""
    
    print("🗄️ 데이터베이스 저장 시작...")
    
    with SessionLocal() as db:
        # 기존 TourSpot 데이터 삭제
        db.query(TourSpot).delete()
        db.commit()
        print("✅ 기존 관광지 데이터 삭제 완료")
        
        # 벡터화를 위한 텍스트 준비
        tour_texts = []
        tour_data = []
        
        for item in all_data:
            # 관광지 정보를 텍스트로 결합
            text_parts = [
                item['name'],
                item['region'],
                item['tags'],
                "관광지"
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
                region=item['region'],
                tags=item['tags'],
                lat=item.get('lat'),
                lon=item.get('lon'),
                contentid=item['contentid'],
                pref_vector=vector
            )
            
            db.add(tour_spot)
            saved_count += 1
        
        db.commit()
        print(f"✅ {saved_count}개 관광지 데이터 DB 저장 완료")
        
        # 저장 결과 확인
        total_count = db.query(TourSpot).count()
        vectorized_count = db.query(TourSpot).filter(TourSpot.pref_vector.isnot(None)).count()
        
        print(f"📊 DB 저장 결과:")
        print(f"  전체 관광지: {total_count}개")
        print(f"  벡터화된 관광지: {vectorized_count}개")
        
        region_stats = db.query(TourSpot.region, func.count(TourSpot.id)).group_by(TourSpot.region).all()
        print("\n📊 지역별 통계:")
        for region, count in region_stats:
            print(f"  {region}: {count}개")

if __name__ == "__main__":
    load_existing_tour_data()