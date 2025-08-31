"""
지역별 관광지 CSV 데이터를 데이터베이스에 로드하고 벡터화
"""

import pandas as pd
from pathlib import Path
from app.db.database import SessionLocal, Base, engine
from app.db.models import TourSpot
from app.embeddings.embedding_service import embed_texts
from sqlalchemy import func

def load_regional_tour_data():
    """지역별 CSV 데이터를 데이터베이스에 로드"""
    
    print("🗄️ 지역별 관광지 CSV 데이터 로드 시작...")
    
    # 테이블 생성
    Base.metadata.create_all(bind=engine)
    
    # 지역별 데이터 폴더
    regional_dir = Path('data/regional')
    all_data = []
    
    # 각 지역 폴더에서 attractions.csv 읽기
    jeonbuk_regions = [
        '고창군', '군산시', '김제시', '남원시', '무주군', '부안군', '순창군',
        '완주군', '익산시', '임실군', '장수군', '전주시', '정읍시', '진안군'
    ]
    
    for region in jeonbuk_regions:
        region_dir = regional_dir / region
        attractions_file = region_dir / 'attractions.csv'
        
        if attractions_file.exists():
            print(f"📋 로드 중: {region}/attractions.csv")
            try:
                df = pd.read_csv(attractions_file)
                
                region_data = []
                for _, row in df.iterrows():
                    if pd.notna(row.get('name')) and str(row.get('name')).strip():
                        region_data.append({
                            'name': str(row.get('name', '')).strip(),
                            'region': region,  # classified_region 컬럼 값 사용
                            'contentid': str(row.get('contentid', '')),
                            'tags': str(row.get('tags', 'attractions')),
                            'keywords': str(row.get('keywords', '')),
                            'lat': float(row.get('lat', 0)) if pd.notna(row.get('lat')) else None,
                            'lon': float(row.get('lon', 0)) if pd.notna(row.get('lon')) else None,
                        })
                
                print(f"  {region}: {len(region_data)}개")
                all_data.extend(region_data)
                
            except Exception as e:
                print(f"  ❌ {region} 로드 실패: {e}")
        else:
            print(f"  ⚠️ {region}: attractions.csv 파일 없음")
    
    print(f"🎯 총 전북 관광지 데이터: {len(all_data)}개")
    
    # 데이터베이스에 저장
    save_to_database(all_data)

def save_to_database(all_data):
    """데이터베이스에 저장 (벡터 임베딩 포함)"""
    
    print("🗄️ 데이터베이스 저장 시작...")
    
    with SessionLocal() as db:
        # 기존 TourSpot 데이터 삭제
        existing_count = db.query(TourSpot).count()
        print(f"  기존 관광지 데이터: {existing_count}개")
        
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
                item['keywords'],
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
        
        print(f"\n📊 DB 저장 결과:")
        print(f"  전체 관광지: {total_count}개")
        print(f"  벡터화된 관광지: {vectorized_count}개")
        
        # 지역별 통계
        region_stats = db.query(TourSpot.region, func.count(TourSpot.id)).group_by(TourSpot.region).order_by(func.count(TourSpot.id).desc()).all()
        print("\n📊 지역별 통계:")
        for region, count in region_stats:
            print(f"  {region}: {count}개")
            
        # 김제시 데이터 확인
        kimje_count = db.query(TourSpot).filter(TourSpot.region == '김제시').count()
        kimje_vectorized = db.query(TourSpot).filter(
            TourSpot.region == '김제시',
            TourSpot.pref_vector.isnot(None)
        ).count()
        
        print(f"\n🎯 김제시 확인:")
        print(f"  김제시 관광지: {kimje_count}개")
        print(f"  김제시 벡터화된 관광지: {kimje_vectorized}개")
        
        # 관광지 샘플 출력 (벡터 확인 시 numpy array 처리)
        samples = db.query(TourSpot).limit(5).all()
        print(f"\n📋 관광지 샘플:")
        for spot in samples:
            has_vector = spot.pref_vector is not None
            if has_vector:
                # numpy array인 경우 shape 속성 사용
                if hasattr(spot.pref_vector, 'shape'):
                    vector_len = spot.pref_vector.shape[0]
                elif hasattr(spot.pref_vector, '__len__'):
                    vector_len = len(spot.pref_vector)
                else:
                    vector_len = "알 수 없음"
            else:
                vector_len = 0
            print(f"  - {spot.name} ({spot.region}) - 벡터: {has_vector} ({vector_len}차원)")

if __name__ == "__main__":
    load_regional_tour_data()