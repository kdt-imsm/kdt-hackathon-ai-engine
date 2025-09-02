"""
최적화된 벡터 기반 추천 시스템
사전 생성된 벡터 캐시를 활용하여 성능 최적화
"""

import json
import csv
import random
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.utils.jeonbuk_region_mapping import extract_region_from_natural_text
from app.services.detail_loader import fetch_detail_image
from app.embeddings.openai_service import OpenAIService
from app.services.vector_cache_service import get_vector_cache_service
from app.utils.attraction_scoring import (
    score_and_rank_attractions,
    get_top_attractions_for_cards,
    get_attractions_for_schedule
)

class OptimizedVectorRecommendationService:
    """최적화된 벡터 기반 추천 서비스"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.openai_service = OpenAIService()
        self.vector_cache = get_vector_cache_service()
        
        # 서비스 시작시 벡터 캐시 로드
        self.vector_cache.load_vectors()
        
    def _load_farms_data(self) -> List[Dict[str, Any]]:
        """dummy_jobs.json에서 농가 데이터 로드 (기존과 동일)"""
        try:
            json_path = self.project_root / "data" / "dummy_jobs.json"
            with open(json_path, 'r', encoding='utf-8') as f:
                farms = json.load(f)
            return farms
        except Exception as e:
            print(f"농가 데이터 로드 실패: {e}")
            return []
    
    def _filter_farms_by_region(self, farms: List[Dict], region: str) -> List[Dict]:
        """지역별 농가 필터링 (기존과 동일)"""
        return [farm for farm in farms if farm.get("region") == region]
    
    def _match_farms_by_job_keywords(self, farms: List[Dict], job_keywords: List[str]) -> List[Dict]:
        """농가 키워드 매칭 (기존과 동일, 농가는 벡터 사용 안함)"""
        if not job_keywords:
            return random.sample(farms, min(3, len(farms)))
        
        matched_farms = []
        for farm in farms:
            farm_title = farm.get("title", "").lower()
            farm_tag = farm.get("tag", "").lower()
            farm_text = f"{farm_title} {farm_tag}"
            
            # 키워드 매칭
            for keyword in job_keywords:
                if keyword.lower() in farm_text:
                    matched_farms.append(farm)
                    break
        
        if not matched_farms:
            return random.sample(farms, min(3, len(farms)))
        
        return matched_farms[:10]
    
    def _get_optimized_vector_attractions(self, region: str, user_travel_styles: List[str], 
                                        user_landscapes: Optional[List[str]] = None) -> List[Dict]:
        """
        최적화된 벡터 기반 관광지 추천
        사전 생성된 벡터 캐시 사용으로 API 호출 최소화
        """
        print(f"🚀 최적화된 벡터 기반 관광지 추천 시작")
        print(f"   - 대상 지역: {region}")
        print(f"   - 사용자 여행 스타일: {user_travel_styles}")
        print(f"   - 사용자 풍경 선호: {user_landscapes}")
        
        # 1. 사용자 선호도 벡터 생성 (API 호출 1번만)
        user_keywords = user_travel_styles + (user_landscapes if user_landscapes else [])
        user_preference_text = " ".join(user_keywords)
        print(f"   - 사용자 선호도 텍스트: '{user_preference_text}'")
        
        user_vector = self.openai_service.get_embedding(user_preference_text)
        
        # 2. 캐시된 벡터로 유사도 계산 (API 호출 0번)
        similar_attractions = self.vector_cache.find_similar_attractions(
            user_vector, region=region, top_k=50
        )
        
        print(f"🎯 캐시에서 {len(similar_attractions)}개 관광지 유사도 계산 완료")
        
        if not similar_attractions:
            print(f"⚠️  {region} 지역의 관광지를 찾을 수 없습니다.")
            return []
        
        # 3. 유사도 점수와 함께 결과 구성
        attraction_results = []
        
        for attraction_data, similarity_score in similar_attractions:
            # 김제지평선축제 특별 처리
            if '김제지평선축제' in attraction_data.get('name', ''):
                similarity_score = 1.0  # 최고 점수 보장
            
            # 관광지 정보 구성
            attraction_dict = {
                'name': attraction_data.get('name'),
                'region': attraction_data.get('region'),
                'contentid': attraction_data.get('contentid'),
                'lat': attraction_data.get('lat'),
                'lon': attraction_data.get('lon'),
                'address_full': attraction_data.get('address_full'),
                'landscape_keywords': attraction_data.get('landscape_keywords'),
                'travel_style_keywords': attraction_data.get('travel_style_keywords'),
                '_vector_score': similarity_score,
                '_attraction_text': attraction_data.get('text', '')
            }
            
            attraction_results.append(attraction_dict)
        
        # 4. 점수순 정렬 (이미 정렬되어 있지만 김제지평선축제 처리 때문에 재정렬)
        attraction_results.sort(key=lambda x: x['_vector_score'], reverse=True)
        
        # 5. 상위 점수 출력
        print(f"🏆 최적화된 벡터 기반 상위 관광지 점수:")
        for i, attr in enumerate(attraction_results[:5]):
            print(f"   {i+1}. {attr['name']}: {attr['_vector_score']:.3f}")
        
        # 6. 이미지 필터링
        print(f"🖼️  이미지 필터링 시작: {len(attraction_results)}개 관광지 확인")
        
        filtered_attractions = []
        for i, attraction in enumerate(attraction_results):
            if len(filtered_attractions) >= 20:  # 상위 20개까지만
                break
                
            contentid = attraction.get('contentid')
            if contentid:
                print(f"   {i+1}. {attraction['name']} (ID: {contentid}) - 이미지 확인중...")
                
                image_url = fetch_detail_image(contentid)
                if image_url:
                    print(f"      ✅ 이미지 있음")
                    attraction['image_url'] = image_url
                    filtered_attractions.append(attraction)
                else:
                    print(f"      ❌ 이미지 없음")
            else:
                print(f"   {i+1}. {attraction['name']}: ContentID 없음")
        
        print(f"🖼️  이미지 필터링 완료: {len(filtered_attractions)}개 관광지")
        
        return filtered_attractions
    
    def get_recommendations(self, natural_request: str, preferences: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        최적화된 추천 시스템 메인 함수
        """
        
        print(f"🚀 최적화된 벡터 추천 시스템 시작: {natural_request}")
        print(f"벡터 캐시 상태: {self.vector_cache.get_cache_info()}")
        
        # 1. LLM으로 자연어 의도 추출 (기존과 동일)
        extracted_intent = self.openai_service.extract_intent_from_natural_text(natural_request)
        
        # 2. LLM 결과와 기존 선호도 통합 (기존과 동일)
        try:
            enhanced_keywords = self.openai_service.enhance_keywords_with_context(extracted_intent, preferences)
            if not enhanced_keywords:
                enhanced_keywords = {
                    'travel_style_keywords': preferences.get('travel_style_keywords', []),
                    'landscape_keywords': preferences.get('landscape_keywords', []),
                    'job_type_keywords': preferences.get('job_type_keywords', []),
                    'activity_keywords': [],
                    'seasonal_keywords': []
                }
        except Exception as e:
            print(f"❌ enhance_keywords_with_context 오류: {e}")
            enhanced_keywords = {
                'travel_style_keywords': preferences.get('travel_style_keywords', []),
                'landscape_keywords': preferences.get('landscape_keywords', []),
                'job_type_keywords': preferences.get('job_type_keywords', []),
                'activity_keywords': [],
                'seasonal_keywords': []
            }
        
        # 3. 지역 결정 (기존과 동일)
        target_region = extracted_intent.get("지역")
        if not target_region:
            target_region = extract_region_from_natural_text(natural_request)
            
        if not target_region:
            return {
                "status": "error",
                "error_code": "INVALID_REGION",
                "message": "전북 지역을 찾을 수 없습니다. 전북 지역명을 포함해 주세요.",
                "available_regions": ["고창군", "군산시", "김제시", "남원시", "무주군", "부안군", 
                                    "순창군", "완주군", "익산시", "임실군", "장수군", "전주시", "정읍시", "진안군"]
            }
        
        print(f"🎯 결정된 대상 지역: {target_region}")
        
        # 4. 농가 추천 (기존 키워드 방식 유지)
        all_farms = self._load_farms_data()
        regional_farms = self._filter_farms_by_region(all_farms, target_region)
        
        combined_job_keywords = enhanced_keywords.get('job_type_keywords', []) + \
                               enhanced_keywords.get('activity_keywords', []) + \
                               enhanced_keywords.get('seasonal_keywords', [])
        
        recommended_farms = self._match_farms_by_job_keywords(regional_farms, combined_job_keywords)
        
        # 5. ✨ 최적화된 벡터 기반 관광지 추천 ✨
        user_travel_styles = preferences.get('travel_style_keywords', [])
        user_landscapes = preferences.get('landscape_keywords', [])
        
        enhanced_travel_styles = enhanced_keywords.get('travel_style_keywords', [])
        final_travel_styles = list(set(user_travel_styles + enhanced_travel_styles))
        
        # 캐시 기반 벡터 검색 사용
        scored_attractions = self._get_optimized_vector_attractions(
            target_region, final_travel_styles, user_landscapes
        )
        
        print(f"✅ 최적화된 벡터 추천 완료: {len(scored_attractions)}개 관광지")
        
        # 상위 5개를 카드용으로 선택
        recommended_attractions = scored_attractions[:5]
        
        # 6. 프론트엔드 형식으로 변환 (기존과 동일)
        farm_cards = []
        for i, farm in enumerate(recommended_farms):
            farm_cards.append({
                "farm_id": f"farm_{i}",
                "farm": farm.get("farm", ""),
                "title": farm.get("title", ""),
                "address": farm.get("address", ""),
                "start_time": farm.get("start_time", "08:00"),
                "end_time": farm.get("end_time", "17:00"),
                "photo": f"/public/images/jobs/{farm.get('image', 'demo_image.jpg')}",
                "required_people": farm.get("required_people", "")
            })
        
        tour_cards = []
        for i, attraction in enumerate(recommended_attractions):
            region = attraction.get("region", "")
            address_full = attraction.get("address_full", "")
            addr1 = attraction.get("addr1", "")
            
            display_address = ""
            if addr1 and addr1 != "전북특별자치도":
                display_address = addr1
            elif region:
                display_address = f"전북 {region}"
            elif address_full:
                display_address = address_full
            else:
                display_address = region
            
            tour_cards.append({
                "tour_id": f"tour_{i}",
                "name": attraction.get("name", ""),
                "address": display_address,
                "photo": attraction.get("image_url", "/public/images/tours/demo_image.jpg"),
                "lat": attraction.get("lat", ""),
                "lon": attraction.get("lon", ""),
                "contentid": attraction.get("contentid", ""),
                "_vector_score": attraction.get("_vector_score", 0.0)  # 디버깅용
            })
        
        # 7. 결과 반환
        return {
            "status": "success", 
            "data": {
                "recommended_farms": farm_cards,
                "recommended_attractions": tour_cards,
                "target_region": target_region,
                "natural_request": natural_request,
                "preferences": preferences,
                "llm_analysis": {
                    "extracted_intent": extracted_intent,
                    "confidence": extracted_intent.get("신뢰도", 0.0),
                    "enhanced_keywords": enhanced_keywords,
                    "region_source": "llm" if extracted_intent.get("지역") else "fallback"
                },
                "performance_info": {
                    "vector_cache_used": True,
                    "api_calls_saved": len(scored_attractions),  # 절약된 API 호출 수
                    "cache_status": self.vector_cache.get_cache_info()
                },
                "scored_attractions": scored_attractions
            }
        }

# 싱글톤 인스턴스
_service = None

def get_optimized_vector_recommendation_service() -> OptimizedVectorRecommendationService:
    """OptimizedVectorRecommendationService 싱글톤 반환"""
    global _service
    if _service is None:
        _service = OptimizedVectorRecommendationService()
    return _service