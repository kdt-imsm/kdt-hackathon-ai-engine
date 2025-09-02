"""
전북 지역 단순화된 추천 시스템
System_Improvements.md 요구사항에 따른 키워드 기반 추천
"""

import json
import csv
import random
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.utils.jeonbuk_region_mapping import extract_region_from_natural_text
from app.services.detail_loader import fetch_detail_image
from app.embeddings.openai_service import OpenAIService
from app.utils.attraction_scoring import (
    score_and_rank_attractions,
    get_top_attractions_for_cards,
    get_attractions_for_schedule
)

class SimpleRecommendationService:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.openai_service = OpenAIService()
        
    def _load_farms_data(self) -> List[Dict[str, Any]]:
        """dummy_jobs.json에서 농가 데이터 로드"""
        try:
            json_path = self.project_root / "data" / "dummy_jobs.json"
            with open(json_path, 'r', encoding='utf-8') as f:
                farms = json.load(f)
            return farms
        except Exception as e:
            print(f"농가 데이터 로드 실패: {e}")
            return []
    
    def _load_regional_attractions(self, region: str) -> List[Dict[str, Any]]:
        """특정 지역의 관광지 데이터 로드"""
        try:
            csv_path = self.project_root / "data" / f"jeonbuk_{region}_attractions.csv"
            attractions = []
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    attractions.append(dict(row))
            
            return attractions
        except Exception as e:
            print(f"{region} 관광지 데이터 로드 실패: {e}")
            return []
    
    def _filter_farms_by_region(self, farms: List[Dict], target_region: str) -> List[Dict]:
        """지역별 농가 필터링"""
        filtered = []
        for farm in farms:
            if target_region in farm.get("region", ""):
                filtered.append(farm)
        return filtered
    
    def _match_farms_by_job_keywords(self, farms: List[Dict], job_keywords: List[str]) -> List[Dict]:
        """농가 일자리 키워드로 농가 매칭 (키워드 매칭 우선 → 나머지 랜덤)"""
        if not job_keywords:
            random.shuffle(farms)
            return farms[:5]
        
        matching_farms = []
        other_farms = []
        
        for farm in farms:
            farm_tag = farm.get("tag", "").lower()
            matched = any(keyword.lower() in farm_tag or farm_tag in keyword.lower() 
                         for keyword in job_keywords)
            
            if matched:
                matching_farms.append(farm)
            else:
                other_farms.append(farm)
        
        # 키워드 매칭 농가 우선, 나머지는 랜덤
        random.shuffle(matching_farms)
        random.shuffle(other_farms)
        
        return (matching_farms + other_farms)[:5]
    
    def _is_attractive_tourist_spot(self, attraction: Dict) -> bool:
        """실제로 사람들이 가고 싶어하는 매력적인 관광지인지 판단"""
        name = attraction.get('name', '').lower()
        keywords = attraction.get('keywords', '').lower()
        content = f"{name} {keywords}"
        
        # 확실히 피해야 할 키워드 (관광 가치가 없는 곳)
        avoid_keywords = [
            '사무소', '관리소', '행정', '청사', '민원', '수련관',
            '주차장', '휴게소', '정류장', '터미널', '교량', '다리',
            '공장', '사업소', '회사', '연구소', '아파트', '주택',
            '병원', '의원', '약국', '은행', '우체국', '파출소', '소방서'
        ]
        
        # 피해야 할 키워드가 있으면 제외
        if any(avoid in content for avoid in avoid_keywords):
            return False
        
        # 축제는 최우선 추천
        if '축제' in content:
            return True
        
        # 매력적인 관광지 키워드 (부분 매칭으로 유연하게)
        attractive_patterns = [
            # 자연 경관
            '폭포', '계곡', '산', '봉', '호수', '강', '바다', '해변', '섬', '동굴',
            '공원', '생태', '숲', '정원', '꽃', '벚꽃', '단풍', '전망', '경관',
            
            # 문화/역사
            '한옥', '마을', '민속', '전통', '문화재', '유적', '박물관', '미술관',
            '사찰', '절', '궁', '성', '탑', '고택', '서원', '향교',
            
            # 체험/액티비티  
            '체험', '테마', '놀이', '전시', '시장', '거리', '온천', '캠핑',
            '명소', '랜드마크', '촬영지'
        ]
        
        # 관대한 매칭 - 하나라도 있으면 포함
        return any(pattern in content for pattern in attractive_patterns)
    
    def _filter_attractions_with_images(self, attractions: List[Dict]) -> List[Dict]:
        """이미지가 있고 매력적인 관광지만 필터링"""
        # 먼저 매력적인 관광지만 필터링
        attractive_attractions = [attr for attr in attractions if self._is_attractive_tourist_spot(attr)]
        
        # 축제 우선 정렬 (하나만 선택)
        festival_attractions = [attr for attr in attractive_attractions if '축제' in f"{attr.get('name', '')} {attr.get('keywords', '')}".lower()]
        other_attractions = [attr for attr in attractive_attractions if '축제' not in f"{attr.get('name', '')} {attr.get('keywords', '')}".lower()]
        
        # 김제지평선축제가 있으면 우선, 없으면 다른 축제 하나만
        gimje_festival = [attr for attr in festival_attractions if '김제지평선축제' in attr.get('name', '')]
        other_festivals = [attr for attr in festival_attractions if '김제지평선축제' not in attr.get('name', '')]
        
        if gimje_festival:
            selected_festivals = gimje_festival[:1]
        elif other_festivals:
            selected_festivals = other_festivals[:1]
        else:
            selected_festivals = []
        
        # 축제 하나만 앞에 배치
        prioritized_attractions = selected_festivals + other_attractions
        
        filtered = []
        for attraction in prioritized_attractions[:20]:  # API 호출 최적화
            contentid = attraction.get('contentid')
            if contentid:
                image_url = fetch_detail_image(contentid)
                if image_url:
                    attraction['image_url'] = image_url
                    filtered.append(attraction)
                if len(filtered) >= 10:
                    break
        return filtered
    
    def _extract_keywords_from_natural_text(self, text: str) -> List[str]:
        """자연어에서 관광지 관련 키워드 추출"""
        keywords = []
        text_lower = text.lower()
        
        # 체험 관련 키워드
        experience_keywords = ["체험", "배우", "만들", "직접", "참여", "실습"]
        for keyword in experience_keywords:
            if keyword in text_lower:
                keywords.append("체험")
                break
        
        # 힐링/자연 관련 키워드
        nature_keywords = ["힐링", "휴식", "쉬", "산책", "자연", "경치", "풍경", "바람"]
        for keyword in nature_keywords:
            if keyword in text_lower:
                keywords.append("힐링")
                break
        
        # 문화/역사 관련 키워드  
        culture_keywords = ["문화", "역사", "전통", "한옥", "유적", "박물관", "절", "사찰"]
        for keyword in culture_keywords:
            if keyword in text_lower:
                keywords.append("문화")
                break
        
        # 축제 관련 키워드
        if "축제" in text_lower or "행사" in text_lower or "이벤트" in text_lower:
            keywords.append("축제")
        
        return keywords

    def _get_scored_attractions(self, attractions: List[Dict], user_travel_styles: List[str], 
                               user_landscapes: Optional[List[str]] = None) -> List[Dict]:
        """
        사용자 선호도 기반 관광지 스코어링 및 순위 정렬
        상위 20개까지 추출하여 이미지 확인 후 반환
        """
        # 스코어링 및 순위 정렬
        scored_attractions = score_and_rank_attractions(
            attractions, user_travel_styles, user_landscapes
        )
        
        # 김제지평선축제 특별 처리 (항상 최우선)
        gimje_festival = None
        other_attractions = []
        
        for scored_attr in scored_attractions:
            if '김제지평선축제' in scored_attr.name:
                gimje_festival = scored_attr
            else:
                other_attractions.append(scored_attr)
        
        # 김제지평선축제를 맨 앞으로, 나머지는 스코어 순서 유지
        if gimje_festival:
            final_scored = [gimje_festival] + other_attractions[:19]  # 총 20개
        else:
            final_scored = other_attractions[:20]
        
        # 마이너스 점수 필터링 (landscape 불일치로 제외된 관광지 제거)
        positive_scored = [attr for attr in final_scored if attr.score >= 0]
        
        # 점수가 양수인 관광지가 충분하지 않으면 0점 관광지도 포함
        if len(positive_scored) < 20:
            zero_scored = [attr for attr in final_scored if attr.score == 0]
            positive_scored = positive_scored + zero_scored[:20-len(positive_scored)]
        
        # 상위 20개 추출 (이미지 확인용)
        top_20 = positive_scored[:20]
        
        # 이미지가 있는 관광지만 필터링
        filtered_attractions = []
        print(f"🖼️ 이미지 필터링 시작: {len(top_20)}개 관광지 확인")
        
        for i, scored_attr in enumerate(top_20):
            contentid = scored_attr.contentid
            print(f"   {i+1}. {scored_attr.name} (ID: {contentid}) - 이미지 확인중...")
            
            if contentid:
                image_url = fetch_detail_image(contentid)
                if image_url:
                    print(f"      ✅ 이미지 있음")
                    # AttractionScore를 Dict로 변환하고 이미지 URL 추가
                    attr_dict = {
                        'name': scored_attr.name,
                        'region': scored_attr.region,
                        'address_full': scored_attr.address_full,
                        'lat': scored_attr.lat,
                        'lon': scored_attr.lon,
                        'contentid': scored_attr.contentid,
                        'landscape_keywords': scored_attr.landscape_keywords,
                        'travel_style_keywords': scored_attr.travel_style_keywords,
                        'image_url': image_url,
                        '_score': scored_attr.score  # 디버깅용
                    }
                    filtered_attractions.append(attr_dict)
                else:
                    print(f"      ❌ 이미지 없음")
            else:
                print(f"      ❌ ContentID 없음")
        
        print(f"🖼️ 이미지 필터링 완료: {len(filtered_attractions)}개 관광지")
        return filtered_attractions

    def _match_attractions_by_preference(self, attractions: List[Dict], 
                                       travel_keywords: List[str], 
                                       landscape_keywords: List[str],
                                       natural_text: str = "",
                                       simple_natural_words: List[str] = []) -> List[Dict]:
        """선호도 키워드 + 자연어 키워드로 관광지 매칭 (축제 우선, 매력적인 관광지만)"""
        # 먼저 매력적인 관광지만 필터링
        attractive_attractions = [attr for attr in attractions if self._is_attractive_tourist_spot(attr)]
        
        # 김제지평선축제 최우선 (김제 지역일 때)
        gimje_festival = [attr for attr in attractive_attractions if '김제지평선축제' in attr.get('name', '')]
        
        # 기타 축제 (김제지평선축제 제외, 하나만)
        other_festivals = [attr for attr in attractive_attractions if '축제' in f"{attr.get('name', '')} {attr.get('keywords', '')}".lower() and '김제지평선축제' not in attr.get('name', '')]
        festival_attractions = other_festivals[:1] if other_festivals else []  # 축제는 하나만
        
        # 기타 매력적인 관광지 (축제 제외)
        other_attractions = [attr for attr in attractive_attractions if '축제' not in f"{attr.get('name', '')} {attr.get('keywords', '')}".lower()]
        
        # 자연어에서 키워드 추출
        natural_keywords = self._extract_keywords_from_natural_text(natural_text)
        
        # 모든 키워드 통합 (선호도 키워드 + 자연어 키워드 + 간단한 자연어)
        all_keywords = travel_keywords + landscape_keywords + natural_keywords + simple_natural_words
        
        if all_keywords:
            matching = []
            other = []
            
            for attraction in other_attractions:  # 축제는 이미 우선순위
                content = f"{attraction.get('name', '')} {attraction.get('keywords', '')}".lower()
                matched = any(keyword.lower() in content for keyword in all_keywords)
                
                if matched:
                    matching.append(attraction)
                else:
                    other.append(attraction)
            
            random.shuffle(matching)
            random.shuffle(other)
            
            # 김제지평선축제 → 기타 축제 → 키워드 매칭 → 기타 순으로 정렬
            final_list = gimje_festival + festival_attractions + matching + other
        else:
            random.shuffle(other_attractions)
            final_list = gimje_festival + festival_attractions + other_attractions
        
        return final_list[:5]
    
    def get_recommendations(self, natural_request: str, preferences: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        LLM 강화 추천 시스템
        1. LLM으로 자연어에서 상세한 여행 의도 추출
        2. 기존 키워드 매칭과 LLM 결과를 통합하여 향상된 추천
        3. 지역, 농가, 관광지 추천의 정확도 향상
        """
        
        print(f"LLM 기반 자연어 분석 시작: {natural_request}")
        
        # 1. LLM으로 자연어 의도 추출
        extracted_intent = self.openai_service.extract_intent_from_natural_text(natural_request)
        
        # 2. LLM 결과와 기존 선호도 통합
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
        
        # 3. 지역 결정 (LLM 결과 우선, 폴백으로 기존 로직)
        target_region = extracted_intent.get("지역")
        if not target_region:
            target_region = extract_region_from_natural_text(natural_request)
            
        if not target_region:
            return {
                "status": "error",
                "error_code": "INVALID_REGION",
                "message": "전북 지역을 찾을 수 없습니다. 전북 지역명을 포함해 주세요.",
                "available_regions": ["고창군", "군산시", "김제시", "남원시", "무주군", "부안군", 
                                    "순창군", "완주군", "익산시", "임실군", "장수군", "전주시", "정읍시", "진안군"],
                "llm_analysis": {
                    "extracted_intent": extracted_intent,
                    "confidence": extracted_intent.get("신뢰도", 0.0)
                }
            }
        
        print(f"🎯 결정된 대상 지역: {target_region}")
        print(f"🔍 LLM 추출 의도: {extracted_intent}")
        print(f"🚀 향상된 키워드: {enhanced_keywords}")
        print(f"👤 사용자 원본 선호도: {preferences}")
        print(f"🚀 향상된 키워드 타입: {type(enhanced_keywords)}")
        
        # 4. 농가 추천 (LLM 향상 키워드 활용)
        all_farms = self._load_farms_data()
        regional_farms = self._filter_farms_by_region(all_farms, target_region)
        
        # LLM 향상 키워드 + 기존 선호도 통합
        combined_job_keywords = enhanced_keywords.get('job_type_keywords', []) + \
                               enhanced_keywords.get('activity_keywords', []) + \
                               enhanced_keywords.get('seasonal_keywords', [])
        
        recommended_farms = self._match_farms_by_job_keywords(regional_farms, combined_job_keywords)
        
        # 5. 관광지 추천 (새로운 스코어링 시스템 활용)
        regional_attractions = self._load_regional_attractions(target_region)
        
        # 사용자 선호도에서 landscape와 travel_style 추출
        user_travel_styles = preferences.get('travel_style_keywords', [])
        user_landscapes = preferences.get('landscape_keywords', [])  # 복수 landscape 그대로 사용
        
        # LLM 향상 키워드와 통합
        enhanced_travel_styles = enhanced_keywords.get('travel_style_keywords', [])
        final_travel_styles = list(set(user_travel_styles + enhanced_travel_styles))
        
        print(f"🎨 관광지 스코어링 입력:")
        print(f"   - 여행 스타일: {final_travel_styles}")
        print(f"   - 풍경 선호: {user_landscapes}")
        print(f"   - 총 관광지 개수: {len(regional_attractions)}")
        
        # 새로운 스코어링 시스템 적용
        scored_attractions = self._get_scored_attractions(
            regional_attractions, final_travel_styles, user_landscapes
        )
        
        print(f"✅ 스코어링 완료: {len(scored_attractions)}개 관광지 (이미지 있음)")
        
        # 상위 5개의 스코어 출력
        if scored_attractions:
            print(f"🏆 상위 관광지 스코어:")
            for i, attr in enumerate(scored_attractions[:5]):
                print(f"   {i+1}. {attr['name']}: {attr.get('_score', 'N/A')}점 "
                      f"(travel_style: {attr.get('travel_style_keywords', 'None')}, "
                      f"landscape: {attr.get('landscape_keywords', 'None')})")
        
        # 상위 5개를 카드용으로 선택
        recommended_attractions = scored_attractions[:5]
        
        # 4. 프론트엔드 형식으로 변환 (요구사항에 맞는 필드명)
        farm_cards = []
        for i, farm in enumerate(recommended_farms):
            farm_cards.append({
                "farm_id": f"farm_{i}",
                "farm": farm.get("farm", ""),  # 농가명
                "title": farm.get("title", ""),  # 제목
                "address": farm.get("address", ""),  # 주소
                "start_time": farm.get("start_time", "08:00"),  # 시작시간
                "end_time": farm.get("end_time", "17:00"),  # 종료시간
                "photo": f"/public/images/jobs/{farm.get('image', 'demo_image.jpg')}",  # 사진
                # 추가 정보
                "required_people": farm.get("required_people", "")
            })
        
        tour_cards = []
        for i, attraction in enumerate(recommended_attractions):
            # 주소 처리: region 필드와 address_full 필드 확인
            region = attraction.get("region", "")
            address_full = attraction.get("address_full", "")
            addr1 = attraction.get("addr1", "")
            
            # 주소 우선순위: addr1 > "전북 {region}" > address_full > region
            display_address = ""
            if addr1 and addr1 != "전북특별자치도":
                display_address = addr1
            elif region and region != "전북특별자치도":
                display_address = f"전북 {region}"
            elif address_full and address_full != "전북특별자치도":
                display_address = address_full
            else:
                display_address = f"전북 {region}" if region else "주소 정보 없음"
            
            tour_cards.append({
                "tour_id": attraction.get("contentid", f"tour_{i}"),
                "name": attraction.get("name", ""),  # 관광지명
                "address": display_address,  # 주소
                "photo": attraction.get("image_url", "")  # 사진
            })
        
        return {
            "status": "success",
            "data": {
                "farms": farm_cards,
                "tour_spots": tour_cards,
                "target_region": target_region,
                "natural_request": natural_request,
                "preferences": preferences,
                # LLM 분석 결과 추가
                "llm_analysis": {
                    "extracted_intent": extracted_intent,
                    "confidence": extracted_intent.get("신뢰도", 0.0),
                    "enhanced_keywords": enhanced_keywords,
                    "region_source": "llm" if extracted_intent.get("지역") else "fallback"
                },
                # Bubble 접근성 향상을 위한 추가 필드
                "bubble_data": {
                    "total_farms": len(farm_cards),
                    "total_tours": len(tour_cards),
                    "estimated_duration": extracted_intent.get("기간", 3),
                    "season_info": extracted_intent.get("시기", ""),
                    "activity_types": extracted_intent.get("활동_유형", []),
                    "region_name": target_region,
                    "recommendations_ready": len(farm_cards) > 0 and len(tour_cards) > 0
                },
                # 일정 생성용 스코어링된 관광지 전체 목록 (상위 20개)
                "scored_attractions": scored_attractions
            }
        }

# 싱글톤 인스턴스
_service = None

def get_simple_recommendation_service() -> SimpleRecommendationService:
    """SimpleRecommendationService 싱글톤 반환"""
    global _service
    if _service is None:
        _service = SimpleRecommendationService()
    return _service