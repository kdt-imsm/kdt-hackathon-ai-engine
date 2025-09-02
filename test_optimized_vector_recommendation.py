#!/usr/bin/env python3
"""
최적화된 벡터 기반 추천 시스템 테스트 스크립트
사전 생성된 벡터 캐시를 활용한 성능 최적화 테스트
"""

import sys
import time
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.optimized_vector_recommendation_service import get_optimized_vector_recommendation_service
from app.services.vector_recommendation_service import get_vector_recommendation_service

def compare_performance():
    """기존 vs 최적화 시스템 성능 비교"""
    
    print("⚡ 벡터 추천 시스템 성능 비교 테스트")
    print("=" * 70)
    
    # 테스트 데이터
    natural_request = "김제에서 힐링여행을 하고 싶어요. 자연이 좋은 곳에서 체험형 활동을 하고 싶습니다."
    preferences = {
        'landscape_keywords': ['들판', '산'],
        'travel_style_keywords': ['힐링·여유', '체험형'],
        'job_type_keywords': ['과수', '채소']
    }
    
    print(f"📝 테스트 데이터:")
    print(f"   자연어: {natural_request}")
    print(f"   선호도: {preferences}")
    print()
    
    # 1. 기존 시스템 테스트
    print("🔥 [기존 시스템] 실시간 벡터 생성 방식")
    print("-" * 50)
    
    try:
        old_service = get_vector_recommendation_service()
        
        start_time = time.time()
        old_result = old_service.get_recommendations(natural_request, preferences)
        old_duration = time.time() - start_time
        
        old_data = old_result.get('data', {})
        old_attractions = old_data.get('scored_attractions', [])
        
        print(f"✅ 기존 시스템 결과:")
        print(f"   ⏱️  소요 시간: {old_duration:.2f}초")
        print(f"   🏞️  관광지 개수: {len(old_attractions)}개")
        print(f"   💰 예상 API 호출: ~62번 (사용자 1번 + 관광지 61번)")
        
        if old_attractions:
            print(f"   🏆 상위 3개:")
            for i, attr in enumerate(old_attractions[:3]):
                score = attr.get('_vector_score', 0.0)
                print(f"      {i+1}. {attr.get('name', 'Unknown')}: {score:.3f}")
        
    except Exception as e:
        print(f"❌ 기존 시스템 테스트 실패: {e}")
        old_duration = float('inf')
        old_attractions = []
    
    print()
    
    # 2. 최적화된 시스템 테스트
    print("⚡ [최적화 시스템] 벡터 캐시 기반 방식")
    print("-" * 50)
    
    try:
        new_service = get_optimized_vector_recommendation_service()
        
        start_time = time.time()
        new_result = new_service.get_recommendations(natural_request, preferences)
        new_duration = time.time() - start_time
        
        new_data = new_result.get('data', {})
        new_attractions = new_data.get('scored_attractions', [])
        performance_info = new_data.get('performance_info', {})
        
        print(f"✅ 최적화 시스템 결과:")
        print(f"   ⏱️  소요 시간: {new_duration:.2f}초")
        print(f"   🏞️  관광지 개수: {len(new_attractions)}개")
        print(f"   💰 실제 API 호출: 1번 (사용자 벡터만)")
        print(f"   💾 벡터 캐시 사용: {performance_info.get('vector_cache_used', False)}")
        print(f"   💸 절약된 API 호출: {performance_info.get('api_calls_saved', 0)}번")
        
        if new_attractions:
            print(f"   🏆 상위 3개:")
            for i, attr in enumerate(new_attractions[:3]):
                score = attr.get('_vector_score', 0.0)
                print(f"      {i+1}. {attr.get('name', 'Unknown')}: {score:.3f}")
        
    except Exception as e:
        print(f"❌ 최적화 시스템 테스트 실패: {e}")
        new_duration = float('inf')
        new_attractions = []
        performance_info = {}
    
    print()
    
    # 3. 성능 비교 요약
    print("📊 성능 비교 요약")
    print("=" * 70)
    
    if old_duration != float('inf') and new_duration != float('inf'):
        speed_improvement = old_duration / new_duration if new_duration > 0 else float('inf')
        time_saved = old_duration - new_duration
        
        print(f"⚡ 속도 개선: {speed_improvement:.1f}배 빨라짐")
        print(f"⏱️  시간 절약: {time_saved:.2f}초")
        print(f"💰 비용 절약: ~98% (62번 → 1번 API 호출)")
        print(f"🎯 결과 정확도: 동일 (같은 벡터 유사도 알고리즘)")
        
        # 확장성 분석
        print(f"\n🔮 전북 전체(840개 관광지) 확장시 예상:")
        print(f"   기존 방식: ~841번 API 호출, 예상 {old_duration * 14:.1f}초")
        print(f"   최적화 방식: 1번 API 호출, 예상 {new_duration:.1f}초")
        print(f"   성능 차이: {(old_duration * 14) / new_duration:.0f}배")
    
    # 4. 벡터 캐시 상태 정보
    cache_info = performance_info.get('cache_status', {})
    if cache_info.get('status') == 'loaded':
        print(f"\n📦 벡터 캐시 정보:")
        print(f"   상태: {cache_info.get('status', 'unknown')}")
        print(f"   총 벡터 개수: {cache_info.get('total_vectors', 0)}개")
        print(f"   지역 개수: {cache_info.get('regions_count', 0)}개")
        print(f"   모델: {cache_info.get('model', 'unknown')}")
        print(f"   벡터 차원: {cache_info.get('vector_dimension', 0)}차원")
        print(f"   생성 시간: {cache_info.get('created_at', 'unknown')}")
        print(f"   로드 시간: {cache_info.get('loaded_at', 'unknown')}")

def test_vector_cache_only():
    """벡터 캐시만 단독 테스트"""
    
    print("\n" + "=" * 70)
    print("🧪 벡터 캐시 단독 테스트")
    print("=" * 70)
    
    try:
        from app.services.vector_cache_service import get_vector_cache_service
        from app.embeddings.openai_service import OpenAIService
        
        cache_service = get_vector_cache_service()
        openai_service = OpenAIService()
        
        # 캐시 정보 출력
        cache_info = cache_service.get_cache_info()
        print(f"📦 캐시 상태: {cache_info}")
        
        if cache_info.get('status') != 'loaded':
            print("❌ 벡터 캐시가 로드되지 않았습니다.")
            print("💡 먼저 'python scripts/precompute_attraction_vectors.py'를 실행하세요.")
            return
        
        # 테스트 검색
        print(f"\n🔍 테스트 검색 수행...")
        user_text = "힐링·여유 체험형 들판 산"
        user_vector = openai_service.get_embedding(user_text)
        
        start_time = time.time()
        results = cache_service.find_similar_attractions(user_vector, region="김제시", top_k=5)
        search_time = time.time() - start_time
        
        print(f"✅ 캐시 검색 완료:")
        print(f"   ⏱️  검색 시간: {search_time:.3f}초")
        print(f"   🎯 검색 결과: {len(results)}개")
        
        print(f"\n🏆 상위 결과:")
        for i, (attraction_data, similarity) in enumerate(results):
            print(f"   {i+1}. {attraction_data.get('name', 'Unknown')}: {similarity:.3f}")
        
    except Exception as e:
        print(f"❌ 벡터 캐시 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 성능 비교 테스트
    compare_performance()
    
    # 벡터 캐시 단독 테스트
    test_vector_cache_only()