#!/usr/bin/env python3
"""
벡터 기반 추천 시스템 테스트 스크립트
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.vector_recommendation_service import get_vector_recommendation_service

def test_vector_recommendation():
    """벡터 기반 관광지 추천 테스트"""
    
    print("🧪 벡터 기반 관광지 추천 시스템 테스트")
    print("=" * 60)
    
    # 서비스 인스턴스 생성
    service = get_vector_recommendation_service()
    
    # 테스트 데이터
    natural_request = "김제에서 힐링여행을 하고 싶어요. 자연이 좋은 곳에서 체험형 활동을 하고 싶습니다."
    preferences = {
        'landscape_keywords': ['들판', '산'],
        'travel_style_keywords': ['힐링·여유', '체험형'],
        'job_type_keywords': ['과수', '채소']
    }
    
    print(f"📝 테스트 입력:")
    print(f"   자연어: {natural_request}")
    print(f"   선호도: {preferences}")
    print()
    
    try:
        # 추천 실행
        result = service.get_recommendations(natural_request, preferences)
        
        print("✅ 추천 결과:")
        print(f"   상태: {result.get('status', 'N/A')}")
        data = result.get('data', {})
        print(f"   지역: {data.get('target_region', 'N/A')}")
        
        # 농가 추천 결과
        farms = data.get('recommended_farms', [])
        print(f"\n🚜 농가 추천 ({len(farms)}개):")
        for i, farm in enumerate(farms[:3]):  # 상위 3개만 출력
            print(f"   {i+1}. {farm.get('title', 'Unknown')}")
        
        # 관광지 추천 결과  
        attractions = data.get('recommended_attractions', [])
        print(f"\n🏞️  관광지 추천 ({len(attractions)}개):")
        for i, attr in enumerate(attractions):
            score = attr.get('_vector_score', 0.0)
            print(f"   {i+1}. {attr.get('name', 'Unknown')} (벡터 점수: {score:.3f})")
        
        # 스코어링된 전체 관광지 (벡터 점수 확인용)
        scored_attractions = data.get('scored_attractions', [])
        print(f"\n📊 벡터 스코어링 결과 (상위 5개):")
        for i, attr in enumerate(scored_attractions[:5]):
            score = attr.get('_vector_score', 0.0)
            print(f"   {i+1}. {attr.get('name', 'Unknown')}: {score:.3f}")
        
        print(f"\n📊 LLM 분석 결과:")
        llm_analysis = data.get('llm_analysis', {})
        print(f"   추출된 의도: {llm_analysis.get('extracted_intent', {})}")
        print(f"   신뢰도: {llm_analysis.get('confidence', 0.0)}")
        print(f"   향상된 키워드: {llm_analysis.get('enhanced_keywords', {})}")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_vector_recommendation()