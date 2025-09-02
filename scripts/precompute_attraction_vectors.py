#!/usr/bin/env python3
"""
관광지 벡터 사전 생성 스크립트
모든 관광지 데이터를 벡터화하여 JSON 파일로 저장
"""

import sys
import json
import csv
from pathlib import Path
from typing import List, Dict, Any
import time

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.embeddings.openai_service import OpenAIService

def load_all_attractions_data() -> List[Dict[str, Any]]:
    """전북 모든 지역의 관광지 데이터 로드"""
    
    data_dir = project_root / "data"
    all_attractions = []
    
    # 전북 14개 시군
    regions = [
        "고창군", "군산시", "김제시", "남원시", "무주군", "부안군",
        "순창군", "완주군", "익산시", "임실군", "장수군", "전주시", "정읍시", "진안군"
    ]
    
    for region in regions:
        csv_file = data_dir / f"jeonbuk_{region}_attractions.csv"
        
        if csv_file.exists():
            print(f"📂 {region} 관광지 데이터 로드 중...")
            
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                region_attractions = []
                
                for row in reader:
                    attraction = dict(row)
                    attraction['region'] = region  # 지역 정보 명시적 추가
                    region_attractions.append(attraction)
                
                print(f"   ✅ {len(region_attractions)}개 관광지 로드")
                all_attractions.extend(region_attractions)
        else:
            print(f"   ❌ {csv_file} 파일이 존재하지 않습니다.")
    
    print(f"\n📊 전체 관광지 수: {len(all_attractions)}개")
    return all_attractions

def create_attraction_text(attraction: Dict[str, Any]) -> str:
    """관광지 정보를 벡터화용 텍스트로 변환"""
    
    text_parts = []
    
    # 기본 정보
    if attraction.get('name'):
        text_parts.append(attraction['name'])
    
    # 키워드 정보
    if attraction.get('landscape_keywords'):
        text_parts.append(attraction['landscape_keywords'])
    
    if attraction.get('travel_style_keywords'):
        text_parts.append(attraction['travel_style_keywords'])
    
    # tags가 있다면 추가 (향후 확장용)
    if attraction.get('tags'):
        text_parts.append(attraction['tags'])
    
    return " ".join(filter(None, text_parts))

def precompute_vectors_batch(attractions: List[Dict[str, Any]], batch_size: int = 100) -> Dict[str, Any]:
    """관광지 벡터를 배치로 생성하여 저장"""
    
    print(f"🔍 벡터 생성 시작 (배치 크기: {batch_size})")
    
    openai_service = OpenAIService()
    vectors_data = {
        "metadata": {
            "total_attractions": len(attractions),
            "vector_dimension": 1536,
            "model": "text-embedding-3-small",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "vectors": {}
    }
    
    # 배치별로 처리
    for i in range(0, len(attractions), batch_size):
        batch = attractions[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(attractions) + batch_size - 1) // batch_size
        
        print(f"\n📦 배치 {batch_num}/{total_batches} 처리 중 ({len(batch)}개 관광지)")
        
        for j, attraction in enumerate(batch):
            try:
                # 관광지 고유 키 생성 (지역_이름_contentid)
                attraction_key = f"{attraction['region']}_{attraction['name']}_{attraction.get('contentid', 'no_id')}"
                
                # 벡터화용 텍스트 생성
                attraction_text = create_attraction_text(attraction)
                
                # 벡터 생성
                vector = openai_service.get_embedding(attraction_text)
                
                # 결과 저장
                vectors_data["vectors"][attraction_key] = {
                    "name": attraction['name'],
                    "region": attraction['region'],
                    "contentid": attraction.get('contentid'),
                    "text": attraction_text,
                    "vector": vector,
                    "landscape_keywords": attraction.get('landscape_keywords'),
                    "travel_style_keywords": attraction.get('travel_style_keywords'),
                    "lat": attraction.get('lat'),
                    "lon": attraction.get('lon'),
                    "address_full": attraction.get('address_full')
                }
                
                print(f"   ✅ {j+1:2d}. {attraction['name']} (벡터 크기: {len(vector)})")
                
                # API 호출 제한 고려한 지연
                time.sleep(0.1)
                
            except Exception as e:
                print(f"   ❌ {j+1:2d}. {attraction['name']}: 벡터 생성 실패 - {e}")
                continue
    
    print(f"\n✅ 벡터 생성 완료: {len(vectors_data['vectors'])}개")
    return vectors_data

def save_vectors_to_file(vectors_data: Dict[str, Any], output_path: Path):
    """벡터 데이터를 JSON 파일로 저장"""
    
    print(f"💾 벡터 데이터 저장 중: {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(vectors_data, f, ensure_ascii=False, indent=2)
    
    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"✅ 저장 완료: {file_size_mb:.2f}MB")

def main():
    """메인 실행 함수"""
    
    print("🚀 관광지 벡터 사전 생성 시작")
    print("=" * 60)
    
    # 1. 관광지 데이터 로드
    attractions = load_all_attractions_data()
    
    if not attractions:
        print("❌ 로드할 관광지 데이터가 없습니다.")
        return
    
    # 2. 벡터 생성
    vectors_data = precompute_vectors_batch(attractions, batch_size=50)
    
    # 3. 파일로 저장
    output_path = project_root / "data" / "attraction_vectors.json"
    save_vectors_to_file(vectors_data, output_path)
    
    print("\n🎉 관광지 벡터 사전 생성 완료!")
    print(f"📍 파일 위치: {output_path}")
    print(f"📊 총 벡터 개수: {len(vectors_data['vectors'])}개")

if __name__ == "__main__":
    main()