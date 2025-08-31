"""
전북 14개 지역의 관광지, 숙박, 음식점 데이터를 완전히 데이터베이스에 로드
System_Improvements.md 요구사항에 따른 완전한 데이터 통합
"""

import pandas as pd
from pathlib import Path
from app.db.database import SessionLocal, Base, engine
from app.db.models import TourSpot
from app.embeddings.embedding_service import embed_texts
from sqlalchemy import func

def load_complete_jeonbuk_data():
    """전북 14개 지역의 모든 유형 데이터를 완전히 로드"""
    
    print("🌾 전북 완전 데이터 로드 시작 (관광지+숙박+음식점)")
    print("=" * 60)
    
    # 테이블 생성
    Base.metadata.create_all(bind=engine)
    
    # 지역별 데이터 폴더
    regional_dir = Path('data/regional')
    all_data = []
    
    # 전북 14개 지역
    jeonbuk_regions = [
        '고창군', '군산시', '김제시', '남원시', '무주군', '부안군', '순창군',
        '완주군', '익산시', '임실군', '장수군', '전주시', '정읍시', '진안군'
    ]
    
    # 데이터 유형별
    data_types = ['attractions', 'accommodations', 'restaurants']
    data_type_korean = {
        'attractions': '관광지',
        'accommodations': '숙박시설', 
        'restaurants': '음식점'
    }
    
    # 지역별, 유형별 데이터 수집 통계
    region_stats = {}
    type_stats = {'attractions': 0, 'accommodations': 0, 'restaurants': 0}
    
    for region in jeonbuk_regions:
        print(f"📍 {region} 데이터 처리 중...")
        region_dir = regional_dir / region
        region_total = 0
        
        region_stats[region] = {'attractions': 0, 'accommodations': 0, 'restaurants': 0}
        
        for data_type in data_types:
            data_file = region_dir / f"{data_type}.csv"
            
            if data_file.exists():
                try:
                    df = pd.read_csv(data_file)
                    
                    type_data = []
                    for _, row in df.iterrows():
                        name = str(row.get('name', '')).strip()
                        if name and name != 'nan':
                            type_data.append({
                                'name': name,
                                'region': region,
                                'data_type': data_type,
                                'data_type_korean': data_type_korean[data_type],
                                'contentid': str(row.get('contentid', '')),
                                'tags': str(row.get('tags', data_type)),
                                'keywords': str(row.get('keywords', '')),
                                'lat': float(row.get('lat', 0)) if pd.notna(row.get('lat')) else None,
                                'lon': float(row.get('lon', 0)) if pd.notna(row.get('lon')) else None,
                            })
                    
                    region_stats[region][data_type] = len(type_data)
                    type_stats[data_type] += len(type_data)
                    region_total += len(type_data)
                    all_data.extend(type_data)
                    
                    print(f"  - {data_type_korean[data_type]}: {len(type_data)}개")
                    
                except Exception as e:
                    print(f"  ❌ {data_type} 로드 실패: {e}")
                    region_stats[region][data_type] = 0
            else:
                print(f"  ⚠️ {data_type}.csv 파일 없음")
                region_stats[region][data_type] = 0
        
        print(f"  {region} 소계: {region_total}개")
        print()
    
    print("=" * 60)
    print(f"🎯 전북 전체 데이터 수집 완료: {len(all_data)}개")
    print()
    
    # 유형별 통계
    print("📊 유형별 통계:")
    for data_type, count in type_stats.items():
        print(f"  {data_type_korean[data_type]}: {count}개")
    print()
    
    # 지역별 통계 (상위 5개)
    region_totals = {region: sum(stats.values()) for region, stats in region_stats.items()}
    sorted_regions = sorted(region_totals.items(), key=lambda x: x[1], reverse=True)
    
    print("📊 지역별 통계 (상위 10개):")
    for i, (region, total) in enumerate(sorted_regions[:10]):
        stats = region_stats[region]
        print(f"  {i+1:2d}. {region}: {total}개 (관광지:{stats['attractions']}, 숙박:{stats['accommodations']}, 음식점:{stats['restaurants']})")
    print()
    
    # 데이터베이스에 저장
    save_complete_data_to_database(all_data, region_stats, type_stats)

def save_complete_data_to_database(all_data, region_stats, type_stats):
    """완전한 데이터를 데이터베이스에 저장"""
    
    print("🗄️ 데이터베이스 완전 저장 시작...")
    
    with SessionLocal() as db:
        # 기존 데이터 상태 확인
        existing_count = db.query(TourSpot).count()
        print(f"  기존 데이터: {existing_count}개")
        
        # 기존 데이터 삭제
        db.query(TourSpot).delete()
        db.commit()
        print("✅ 기존 데이터 삭제 완료")
        
        # 벡터화를 위한 텍스트 준비
        print(f"📊 {len(all_data)}개 항목 벡터화 준비 중...")
        
        tour_texts = []
        tour_data = []
        
        for item in all_data:
            # 각 항목의 정보를 의미있는 텍스트로 결합
            text_parts = [
                item['name'],
                item['region'],
                item['data_type_korean'],  # 관광지/숙박시설/음식점
                item['keywords'],
                item['tags']
            ]
            # 빈 값 제거하고 결합
            text_parts = [str(part).strip() for part in text_parts if part and str(part).strip() and str(part) != 'nan']
            tour_text = ' '.join(text_parts)
            
            tour_texts.append(tour_text)
            tour_data.append(item)
        
        print(f"📊 {len(tour_texts)}개 텍스트 벡터화 시작...")
        
        # 벡터화 (대량 데이터 처리)
        try:
            tour_vectors = embed_texts(tour_texts)
            print(f"✅ 벡터화 완료: {len(tour_vectors)}개")
        except Exception as e:
            print(f"❌ 벡터화 실패: {e}")
            import traceback
            traceback.print_exc()
            tour_vectors = []
        
        # 데이터베이스 저장
        print(f"💾 {len(tour_data)}개 항목 데이터베이스 저장 중...")
        
        saved_count = 0
        for i, item in enumerate(tour_data):
            vector = tour_vectors[i] if i < len(tour_vectors) else None
            
            tour_spot = TourSpot(
                name=item['name'],
                region=item['region'],
                tags=f"{item['data_type_korean']},{item['tags']}",  # 유형 정보 포함
                lat=item.get('lat'),
                lon=item.get('lon'),
                contentid=item['contentid'],
                pref_vector=vector
            )
            
            db.add(tour_spot)
            saved_count += 1
            
            # 진행상황 출력 (1000개마다)
            if saved_count % 1000 == 0:
                print(f"  저장 진행: {saved_count}/{len(tour_data)}")
        
        db.commit()
        print(f"✅ {saved_count}개 항목 데이터베이스 저장 완료")
        
        # 저장 결과 최종 검증
        verify_saved_data(db, region_stats, type_stats)

def verify_saved_data(db, expected_region_stats, expected_type_stats):
    """저장된 데이터 완전성 검증"""
    
    print("\n🔍 데이터 저장 완전성 검증...")
    print("=" * 50)
    
    # 전체 통계
    total_count = db.query(TourSpot).count()
    vectorized_count = db.query(TourSpot).filter(TourSpot.pref_vector.isnot(None)).count()
    
    print(f"📊 전체 결과:")
    print(f"  총 저장된 항목: {total_count}개")
    print(f"  벡터화된 항목: {vectorized_count}개")
    print(f"  벡터화 비율: {vectorized_count/total_count*100:.1f}%" if total_count > 0 else "  벡터화 비율: 0%")
    print()
    
    # 지역별 검증
    actual_region_stats = db.query(TourSpot.region, func.count(TourSpot.id)).group_by(TourSpot.region).order_by(func.count(TourSpot.id).desc()).all()
    
    print("📊 지역별 저장 결과:")
    for region, count in actual_region_stats:
        print(f"  {region}: {count}개")
    print()
    
    # 유형별 검증 (tags에서 추출)
    print("📊 유형별 분포 확인:")
    attraction_count = db.query(TourSpot).filter(TourSpot.tags.contains('관광지')).count()
    accommodation_count = db.query(TourSpot).filter(TourSpot.tags.contains('숙박시설')).count()  
    restaurant_count = db.query(TourSpot).filter(TourSpot.tags.contains('음식점')).count()
    
    print(f"  관광지: {attraction_count}개")
    print(f"  숙박시설: {accommodation_count}개")
    print(f"  음식점: {restaurant_count}개")
    print()
    
    # 김제시 특별 확인 (문제 해결 검증용)
    kimje_total = db.query(TourSpot).filter(TourSpot.region == '김제시').count()
    kimje_vectorized = db.query(TourSpot).filter(
        TourSpot.region == '김제시',
        TourSpot.pref_vector.isnot(None)
    ).count()
    kimje_attractions = db.query(TourSpot).filter(
        TourSpot.region == '김제시',
        TourSpot.tags.contains('관광지')
    ).count()
    kimje_accommodations = db.query(TourSpot).filter(
        TourSpot.region == '김제시', 
        TourSpot.tags.contains('숙박시설')
    ).count()
    kimje_restaurants = db.query(TourSpot).filter(
        TourSpot.region == '김제시',
        TourSpot.tags.contains('음식점') 
    ).count()
    
    print("🎯 김제시 완전성 검증:")
    print(f"  전체: {kimje_total}개")
    print(f"  벡터화: {kimje_vectorized}개")
    print(f"  관광지: {kimje_attractions}개") 
    print(f"  숙박시설: {kimje_accommodations}개")
    print(f"  음식점: {kimje_restaurants}개")
    print()
    
    # 샘플 데이터 확인
    print("📋 저장된 데이터 샘플:")
    samples = db.query(TourSpot).limit(5).all()
    for spot in samples:
        has_vector = spot.pref_vector is not None
        if has_vector:
            if hasattr(spot.pref_vector, 'shape'):
                vector_len = spot.pref_vector.shape[0]
            elif hasattr(spot.pref_vector, '__len__'):
                try:
                    vector_len = len(spot.pref_vector) 
                except:
                    vector_len = "확인불가"
            else:
                vector_len = "알 수 없음"
        else:
            vector_len = 0
        print(f"  - {spot.name} ({spot.region}) [{spot.tags}] - 벡터: {has_vector} ({vector_len}차원)")
    
    print("\n✅ 데이터 로드 및 검증 완료!")

if __name__ == "__main__":
    load_complete_jeonbuk_data()