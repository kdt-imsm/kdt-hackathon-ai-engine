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

class SimpleRecommendationService:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        
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
        단순화된 추천 시스템
        1. 자연어에서 전북 지역 추출
        2. 해당 지역 농가 데이터 필터링 + 키워드 매칭으로 5개 추천
        3. 해당 지역 관광지 데이터 + 이미지 필터링 + 키워드 매칭으로 5개 추천
        """
        
        # 1. 전북 지역 추출
        target_region = extract_region_from_natural_text(natural_request)
        if not target_region:
            return {
                "status": "error",
                "error_code": "INVALID_REGION",
                "message": "전북 지역을 찾을 수 없습니다. 전북 지역명을 포함해 주세요.",
                "available_regions": ["고창군", "군산시", "김제시", "남원시", "무주군", "부안군", 
                                    "순창군", "완주군", "익산시", "임실군", "장수군", "전주시", "정읍시", "진안군"]
            }
        
        # 2. 농가 추천 (지역 필터링 → 키워드 매칭)
        all_farms = self._load_farms_data()
        regional_farms = self._filter_farms_by_region(all_farms, target_region)
        job_keywords = preferences.get('job_type_keywords', [])
        recommended_farms = self._match_farms_by_job_keywords(regional_farms, job_keywords)
        
        # 3. 관광지 추천 (지역 데이터 → 이미지 필터링 → 키워드 매칭)
        regional_attractions = self._load_regional_attractions(target_region)
        attractions_with_images = self._filter_attractions_with_images(regional_attractions)
        travel_keywords = preferences.get('travel_style_keywords', [])
        landscape_keywords = preferences.get('landscape_keywords', [])
        simple_natural_words = preferences.get('simple_natural_words', [])
        recommended_attractions = self._match_attractions_by_preference(
            attractions_with_images, travel_keywords, landscape_keywords, natural_request, simple_natural_words)
        
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
                "tag": farm.get("tag", ""),
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
                "preferences": preferences
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