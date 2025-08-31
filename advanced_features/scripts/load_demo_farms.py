"""
scripts/load_demo_farms.py
==========================
data2/demo_data_jobs.csv 농가 데이터를 DemoFarm 테이블에 로드하는 스크립트

System_Improvements.md 요구사항:
- 농가 데이터는 data2/demo_data_jobs.csv만 사용
- 전북 지역만 대상
- region_mapping.py를 사용하여 지역 정규화
"""

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.database import SessionLocal, engine
from app.db.models import Base, DemoFarm
from app.utils.region_mapping import normalize_region_name
from app.embeddings.embedding_service import embed_texts
import re


def extract_region_from_address(address: str) -> str:
    """주소에서 전북 지역명 추출"""
    # "전북 고창군" → "고창군" 추출
    match = re.search(r'전북\s+(\w+)', address)
    if match:
        region = match.group(1)
        return normalize_region_name(region)
    return None


def load_demo_farms():
    """demo_data_jobs.csv에서 농가 데이터 로드 (벡터 임베딩 포함)"""
    print("🚜 Demo 농가 데이터 로딩 시작...")
    
    # 테이블 생성
    Base.metadata.create_all(bind=engine)
    
    # CSV 데이터 읽기
    df = pd.read_csv('data2/demo_data_jobs.csv')
    
    with SessionLocal() as db:
        # 기존 데이터 삭제
        db.query(DemoFarm).delete()
        db.commit()
        
        loaded_count = 0
        
        # 벡터화를 위한 텍스트 수집
        farm_texts = []
        farms_data = []
        
        for _, row in df.iterrows():
            # 지역 정규화
            region = extract_region_from_address(row['address'])
            
            if not region:
                print(f"⚠️  지역을 추출할 수 없는 주소: {row['address']}")
                continue
            
            # 농가 정보를 텍스트로 결합 (벡터화용) - address 사용
            farm_text = f"{row['farm_name']} {row['tag']} {row['address']} 농업체험 농가"
            farm_texts.append(farm_text)
            
            # 농가 데이터 저장
            farms_data.append({
                'farm_name': row['farm_name'],
                'required_workers': int(row['required_workers']),
                'address': row['address'],
                'detail_address': row['detail_address'],
                'start_time': row['start_time'],
                'end_time': row['end_time'],
                'tag': row['tag'],
                'image_name': row['image_name'],
                'region': region
            })
        
        print(f"📊 {len(farm_texts)}개 농가 텍스트 벡터화 중...")
        
        # 농가 텍스트들을 일괄 벡터화
        try:
            farm_vectors = embed_texts(farm_texts)
            print(f"✅ 벡터화 완료: {len(farm_vectors)}개")
        except Exception as e:
            print(f"❌ 벡터화 실패: {e}")
            farm_vectors = []
        
        # 농가 데이터와 벡터를 DB에 저장
        for i, farm_data in enumerate(farms_data):
            farm_vector = farm_vectors[i] if i < len(farm_vectors) else None
            
            farm = DemoFarm(
                **farm_data,
                pref_vector=farm_vector
            )
            
            db.add(farm)
            loaded_count += 1
        
        db.commit()
        
        print(f"✅ {loaded_count}개 농가 데이터 로드 완료 (벡터 임베딩 포함)")
        
        # 지역별 통계
        region_stats = db.query(DemoFarm.region, func.count(DemoFarm.id)).group_by(DemoFarm.region).all()
        print("\n📊 지역별 농가 통계:")
        for region, count in region_stats:
            print(f"  {region}: {count}개")


if __name__ == "__main__":
    load_demo_farms()