"""
단순화된 스케줄링 시스템
System_Improvements.md 요구사항에 따른 규칙 기반 일정 생성
"""

import re
import csv
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from app.embeddings.openai_service import OpenAIService
from app.services.detail_loader import fetch_detail_image
from app.utils.attraction_scoring import get_attractions_for_schedule

class SimpleSchedulingService:
    def __init__(self):
        self.openai_service = OpenAIService()
        self.project_root = Path(__file__).parent.parent.parent
    
    def _extract_duration_from_request(self, request: str) -> int:
        """자연어에서 기간 추출 (최대 10일, 한글 숫자 지원)"""
        
        # 한글 숫자 매핑
        korean_numbers = {
            '하루': 1, '이틀': 2, '사흘': 3, '나흘': 4, '닷새': 5,
            '엿새': 6, '이레': 7, '여드레': 8, '아흐레': 9, '열흘': 10,
            '일주일': 7, '이주일': 14, '한주': 7, '두주': 14
        }
        
        # 한글 숫자 표현 확인
        for korean, days in korean_numbers.items():
            if korean in request:
                print(f"🔍 한글 기간 감지: '{korean}' → {days}일")
                return min(days, 10)
        
        # "2주" = 14일 → 10일로 제한
        if "주" in request:
            weeks_match = re.search(r'(\d+)주', request)
            if weeks_match:
                weeks = int(weeks_match.group(1))
                duration = weeks * 7
                print(f"🔍 주 단위 기간 감지: {weeks}주 → {duration}일")
                return min(duration, 10)
        
        # "5일", "3박", "10일" 등
        duration_match = re.search(r'(\d+)(?:일|박)', request)
        if duration_match:
            days = int(duration_match.group(1))
            print(f"🔍 일/박 단위 기간 감지: {days}일")
            return min(days, 10)
        
        # "정도", "쯤" 등과 함께 사용되는 숫자 패턴
        # "10일 정도", "5일쯤" 등
        approx_match = re.search(r'(\d+)일?\s*(?:정도|쯤|가량|즈음)', request)
        if approx_match:
            days = int(approx_match.group(1))
            print(f"🔍 대략적 기간 감지: {days}일 정도")
            return min(days, 10)
        
        print("🔍 기간 정보 없음 → 기본값 3일")
        return 3  # 기본값
    
    def _convert_korean_date_to_calendar_format(self, korean_date: str) -> str:
        """한국어 날짜(10월 1일 (화))를 캘린더 형식(mm/dd/yyyy hh:mm xx)으로 변환"""
        import re
        
        if not korean_date:
            return "01/01/2025 9:00 am"
        
        try:
            # "10월 1일 (화)" 형태에서 월과 일 추출
            match = re.search(r'(\d+)월\s*(\d+)일', korean_date)
            if match:
                month = int(match.group(1))
                day = int(match.group(2))
                
                # 2025년으로 고정, 시간은 9:00 am으로 고정
                return f"{month:02d}/{day:02d}/2025 9:00 am"
            else:
                # 파싱 실패시 기본값
                return "01/01/2025 9:00 am"
                
        except Exception as e:
            print(f"날짜 변환 오류: {e}")
            return "01/01/2025 9:00 am"
    
    def _extract_start_date_from_request(self, request: str, region: str = None) -> tuple[str, datetime]:
        """자연어에서 시작 날짜 추출 (2025년 기준, 9월 4일 이후)"""
        base_date = datetime(2025, 9, 4)  # 오늘을 2025년 9월 4일로 가정
        
        # 김제 지역이고 10월 요청이면 김제지평선축제 고려 (10월 8-12일)
        if region and "김제" in region and "10월" in request:
            if "초" in request:
                start_date = datetime(2025, 10, 1)  # 축제 기간을 포함하도록
            elif "말" in request:
                start_date = datetime(2025, 10, 25)
            else:
                start_date = datetime(2025, 10, 1)  # 기본적으로 10월 1일부터
        elif "9월" in request:
            if "초" in request:
                start_date = datetime(2025, 9, 5)  # 9월 4일 이후
            elif "말" in request:
                start_date = datetime(2025, 9, 25)
            else:
                start_date = datetime(2025, 9, 15)
        elif "10월" in request:
            if "초" in request:
                start_date = datetime(2025, 10, 1)
            elif "말" in request:
                start_date = datetime(2025, 10, 25)
            else:
                start_date = datetime(2025, 10, 15)
        elif "11월" in request:
            start_date = datetime(2025, 11, 1)
        elif "12월" in request:
            start_date = datetime(2025, 12, 1)
        else:
            start_date = datetime(2025, 9, 5)  # 기본값
        
        # 9월 4일 이전이면 9월 5일로 조정
        if start_date <= base_date:
            start_date = datetime(2025, 9, 5)
        
        formatted_date = start_date.strftime("%Y년 %m월 %d일")
        return formatted_date, start_date
    
    def _load_regional_accommodations(self, region: str) -> List[Dict[str, Any]]:
        """특정 지역의 숙박 데이터 로드"""
        try:
            csv_path = self.project_root / "data" / f"jeonbuk_{region}_accommodations.csv"
            accommodations = []
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    accommodations.append(dict(row))
            
            print(f"✅ {region} 숙박 데이터 로드: {len(accommodations)}개")
            return accommodations
        except Exception as e:
            print(f"❌ {region} 숙박 데이터 로드 실패: {e}")
            return []
    
    def _load_regional_restaurants(self, region: str) -> List[Dict[str, Any]]:
        """특정 지역의 음식점 데이터 로드"""
        try:
            csv_path = self.project_root / "data" / f"jeonbuk_{region}_restaurants.csv"
            restaurants = []
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    restaurants.append(dict(row))
            
            print(f"✅ {region} 음식점 데이터 로드: {len(restaurants)}개")
            return restaurants
        except Exception as e:
            print(f"❌ {region} 음식점 데이터 로드 실패: {e}")
            return []
    
    def _get_accommodation_cards(self, accommodations: List[Dict], limit: int = 5) -> List[Dict[str, Any]]:
        """숙박 데이터를 카드 형식으로 변환"""
        random.shuffle(accommodations)
        cards = []
        
        for i, accommodation in enumerate(accommodations[:limit * 3]):  # API 호출 최적화
            contentid = accommodation.get('contentid')
            
            # 주소 처리
            region = accommodation.get("region", "")
            address_full = accommodation.get("address_full", "")
            display_address = f"전북 {region}" if region and region != "전북특별자치도" else address_full
            
            if contentid:
                image_url = fetch_detail_image(contentid)
                if image_url:
                    cards.append({
                        "id": contentid,
                        "name": accommodation.get("name", ""),
                        "address": display_address,
                        "photo": image_url
                    })
                if len(cards) >= limit:
                    break
        
        # 이미지가 없는 경우에도 기본 데이터 추가
        if len(cards) < limit:
            for accommodation in accommodations[:limit]:
                if not any(card["id"] == accommodation.get('contentid') for card in cards):
                    region = accommodation.get("region", "")
                    address_full = accommodation.get("address_full", "")
                    display_address = f"전북 {region}" if region and region != "전북특별자치도" else address_full
                    
                    cards.append({
                        "id": accommodation.get('contentid', f'acc_{len(cards)}'),
                        "name": accommodation.get("name", ""),
                        "address": display_address,
                        "photo": ""
                    })
                if len(cards) >= limit:
                    break
        
        return cards
    
    def _get_restaurant_cards(self, restaurants: List[Dict], limit: int = 5) -> List[Dict[str, Any]]:
        """음식점 데이터를 카드 형식으로 변환"""
        random.shuffle(restaurants)
        cards = []
        
        for i, restaurant in enumerate(restaurants[:limit * 3]):  # API 호출 최적화
            contentid = restaurant.get('contentid')
            
            # 주소 처리
            region = restaurant.get("region", "")
            address_full = restaurant.get("address_full", "")
            display_address = f"전북 {region}" if region and region != "전북특별자치도" else address_full
            
            if contentid:
                image_url = fetch_detail_image(contentid)
                if image_url:
                    cards.append({
                        "id": contentid,
                        "name": restaurant.get("name", ""),
                        "address": display_address,
                        "photo": image_url
                    })
                if len(cards) >= limit:
                    break
        
        # 이미지가 없는 경우에도 기본 데이터 추가
        if len(cards) < limit:
            for restaurant in restaurants[:limit]:
                if not any(card["id"] == restaurant.get('contentid') for card in cards):
                    region = restaurant.get("region", "")
                    address_full = restaurant.get("address_full", "")
                    display_address = f"전북 {region}" if region and region != "전북특별자치도" else address_full
                    
                    cards.append({
                        "id": restaurant.get('contentid', f'rest_{len(cards)}'),
                        "name": restaurant.get("name", ""),
                        "address": display_address,
                        "photo": ""
                    })
                if len(cards) >= limit:
                    break
        
        return cards
    
    def _get_additional_attractions(self, region: str, selected_tours: List[Dict], 
                                  preferences: Dict, needed_count: int) -> List[Dict[str, Any]]:
        """선택된 관광지 외에 추가 관광지 찾기"""
        if not region or needed_count <= 0:
            return []
        
        try:
            csv_path = self.project_root / "data" / f"jeonbuk_{region}_attractions.csv"
            all_attractions = []
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    all_attractions.append(dict(row))
            
            # 이미 선택된 관광지 ID 목록
            selected_ids = set(tour.get("tour_id", "") for tour in selected_tours)
            
            # 선택되지 않은 관광지만 필터링
            available_attractions = [
                attr for attr in all_attractions 
                if attr.get("contentid", "") not in selected_ids
            ]
            
            # 매력적인 관광지만 필터링
            attractive_attractions = []
            for attraction in available_attractions:
                name = attraction.get('name', '').lower()
                keywords = attraction.get('keywords', '').lower()
                content = f"{name} {keywords}"
                
                # 피해야 할 키워드
                avoid_keywords = [
                    '사무소', '관리소', '행정', '청사', '민원', '수련관',
                    '주차장', '휴게소', '정류장', '터미널', '교량', '다리',
                    '공장', '사업소', '회사', '연구소', '아파트', '주택',
                    '병원', '의원', '약국', '은행', '우체국', '파출소', '소방서'
                ]
                
                if any(avoid in content for avoid in avoid_keywords):
                    continue
                
                # 매력적인 관광지 패턴
                attractive_patterns = [
                    '폭포', '계곡', '산', '봉', '호수', '강', '바다', '해변', '섬', '동굴',
                    '공원', '생태', '숲', '정원', '꽃', '벚꽃', '단풍', '전망', '경관',
                    '한옥', '마을', '민속', '전통', '문화재', '유적', '박물관', '미술관',
                    '사찰', '절', '궁', '성', '탑', '고택', '서원', '향교',
                    '체험', '테마', '놀이', '전시', '시장', '거리', '온천', '캠핑',
                    '명소', '랜드마크', '촬영지', '축제'
                ]
                
                if any(pattern in content for pattern in attractive_patterns):
                    attractive_attractions.append(attraction)
            
            # 사용자 선호도 기반 매칭
            travel_keywords = preferences.get('travel_style_keywords', [])
            landscape_keywords = preferences.get('landscape_keywords', [])
            simple_natural_words = preferences.get('simple_natural_words', [])
            all_keywords = travel_keywords + landscape_keywords + simple_natural_words
            
            if all_keywords:
                preference_matching = []
                preference_other = []
                
                for attraction in attractive_attractions:
                    content = f"{attraction.get('name', '')} {attraction.get('keywords', '')}".lower()
                    matched = any(keyword.lower() in content for keyword in all_keywords)
                    
                    if matched:
                        preference_matching.append(attraction)
                    else:
                        preference_other.append(attraction)
                
                random.shuffle(preference_matching)
                random.shuffle(preference_other)
                available_attractions = preference_matching + preference_other
            else:
                random.shuffle(attractive_attractions)
                available_attractions = attractive_attractions
            
            # 이미지가 있는 것 우선
            result = []
            for attraction in available_attractions[:needed_count * 3]:
                contentid = attraction.get('contentid')
                if contentid:
                    image_url = fetch_detail_image(contentid)
                    if image_url:
                        attraction['image_url'] = image_url
                        result.append(attraction)
                    if len(result) >= needed_count:
                        break
            
            # 이미지가 없어도 필요한 개수 채우기
            if len(result) < needed_count:
                for attraction in available_attractions[:needed_count]:
                    if attraction not in result:
                        result.append(attraction)
                    if len(result) >= needed_count:
                        break
            
            return result[:needed_count]
            
        except Exception as e:
            print(f"❌ {region} 추가 관광지 로드 실패: {e}")
            return []
    
    def generate_schedule(self, 
                         natural_request: str,
                         selected_farm: Dict[str, Any],
                         selected_tours: List[Dict[str, Any]],
                         preferences: Dict[str, Any],
                         region: str = None,
                         scored_attractions: List[Dict[str, Any]] = None,
                         recommended_tour_ids: List[str] = None) -> Dict[str, Any]:
        """
        LLM 강화 일정 생성 시스템
        
        규칙:
        - 5-6일: 첫째날/마지막날 제외하고 농가 배치, 첫째날/마지막날에 관광지
        - 7일 이상: 첫째날/마지막하루전날/마지막날 제외하고 농가 배치
                  첫째날(관광지1개), 마지막하루전날(관광지2개), 마지막날(관광지1개)
        """
        
        print(f"🧠 LLM 기반 일정 생성 시작: {natural_request}")
        print(f"📋 전달받은 선택된 농가 데이터: {selected_farm}")
        print(f"📋 전달받은 선택된 관광지 데이터: {selected_tours}")
        
        # LLM으로 자연어 의도 추출 (기간 정보 포함)
        extracted_intent = self.openai_service.extract_intent_from_natural_text(natural_request)
        
        # 기간 결정 (LLM 우선, 폴백으로 기존 로직)
        llm_duration = extracted_intent.get("기간")
        if llm_duration and isinstance(llm_duration, (int, float)) and llm_duration > 0:
            duration = min(int(llm_duration), 10)  # 최대 10일 제한
            print(f"🎯 LLM에서 기간 추출: {duration}일 (원본: {extracted_intent.get('기간_텍스트', llm_duration)})")
        else:
            duration = self._extract_duration_from_request(natural_request)
            print(f"🔄 기존 로직으로 기간 추출: {duration}일")
        
        start_date_str, start_date_obj = self._extract_start_date_from_request(natural_request, region)
        
        print(f"📅 최종 일정 정보: {duration}일, 시작일: {start_date_str}")
        
        # 지역 추출 (농가 주소에서 추출 또는 매개변수 사용)
        if not region and selected_farm:
            farm_address = selected_farm.get("location", "")
            # 간단한 지역 추출 로직
            for r in ["김제시", "전주시", "군산시", "익산시", "정읍시", "남원시", "고창군", "부안군", "임실군", "순창군", "진안군", "무주군", "장수군", "완주군"]:
                if r in farm_address:
                    region = r
                    break
        
        # 필요한 관광지 개수 계산 - 20개 관광지를 충분히 활용
        total_tour_slots = 0
        if duration <= 6:
            total_tour_slots = 8  # 충분한 관광지 확보 (2개 필요하지만 여유분 포함)
        else:
            total_tour_slots = 15  # 충분한 관광지 확보 (4개 필요하지만 여유분 포함)
        
        # 새로운 스코어링 시스템을 활용한 추가 관광지 선택
        all_tours_for_schedule = selected_tours.copy()
        if len(selected_tours) < total_tour_slots:
            additional_needed = total_tour_slots - len(selected_tours)
            
            if scored_attractions:
                print(f"🎯 스코어링된 관광지 활용: {len(scored_attractions)}개 중에서 추가 선택")
                
                # 사용자가 선택한 관광지 ID 추출
                selected_tour_ids = {tour.get("tour_id") for tour in selected_tours}
                
                # 추천되었지만 선택되지 않은 관광지 ID 추출
                recommended_but_not_selected = set(recommended_tour_ids or []) - selected_tour_ids
                
                # scored_attractions를 AttractionScore 형태로 변환
                from app.utils.attraction_scoring import AttractionScore
                attraction_scores = []
                for attr in scored_attractions:
                    score_obj = AttractionScore(
                        name=attr['name'],
                        region=attr['region'],
                        address_full=attr['address_full'],
                        lat=attr['lat'],
                        lon=attr['lon'],
                        contentid=attr['contentid'],
                        landscape_keywords=attr.get('landscape_keywords'),
                        travel_style_keywords=attr.get('travel_style_keywords'),
                        score=attr.get('_score', 0.0),
                        travel_style_matches=0,  # 재계산 불필요
                        landscape_match=False    # 재계산 불필요
                    )
                    attraction_scores.append(score_obj)
                
                # 김제 지역이면 김제지평선축제 우선 처리
                if selected_farm and "김제" in selected_farm.get("location", ""):
                    gimje_festival_attr = None
                    other_attrs = []
                    
                    for attr in attraction_scores:
                        if '김제지평선축제' in attr.name:
                            gimje_festival_attr = attr
                        else:
                            other_attrs.append(attr)
                    
                    # 김제지평선축제가 선택되지 않았고 추가가 필요하면 최우선 추가
                    if (gimje_festival_attr and 
                        gimje_festival_attr.contentid not in selected_tour_ids and 
                        additional_needed > 0):
                        
                        display_address = f"전북 {gimje_festival_attr.region}" if gimje_festival_attr.region else "주소 정보 없음"
                        all_tours_for_schedule.append({
                            "tour_id": gimje_festival_attr.contentid,
                            "name": gimje_festival_attr.name,
                            "address": display_address,
                            "photo": next((sa.get("image_url", "") for sa in scored_attractions if sa["contentid"] == gimje_festival_attr.contentid), "")
                        })
                        additional_needed -= 1
                        print(f"🏆 김제지평선축제 우선 추가됨")
                    
                    # 나머지 필요한 관광지 선택
                    if additional_needed > 0:
                        selected_attractions = get_attractions_for_schedule(
                            other_attrs,  # 김제지평선축제 제외
                            selected_tour_ids | {gimje_festival_attr.contentid} if gimje_festival_attr else selected_tour_ids,
                            recommended_but_not_selected,
                            total_needed=additional_needed
                        )
                        
                        # 추가 관광지를 일정용 포맷으로 변환
                        for attr in selected_attractions:
                            if attr.contentid not in selected_tour_ids:
                                display_address = f"전북 {attr.region}" if attr.region else "주소 정보 없음"
                                
                                all_tours_for_schedule.append({
                                    "tour_id": attr.contentid,
                                    "name": attr.name,
                                    "address": display_address,
                                    "photo": next((sa.get("image_url", "") for sa in scored_attractions if sa["contentid"] == attr.contentid), "")
                                })
                else:
                    # 김제가 아닌 지역: 기존 로직
                    selected_attractions = get_attractions_for_schedule(
                        attraction_scores,
                        selected_tour_ids,
                        recommended_but_not_selected,
                        total_needed=total_tour_slots
                    )
                    
                    # 추가 관광지를 일정용 포맷으로 변환
                    for attr in selected_attractions:
                        if attr.contentid not in selected_tour_ids:
                            display_address = f"전북 {attr.region}" if attr.region else "주소 정보 없음"
                            
                            all_tours_for_schedule.append({
                                "tour_id": attr.contentid,
                                "name": attr.name,
                                "address": display_address,
                                "photo": next((sa.get("image_url", "") for sa in scored_attractions if sa["contentid"] == attr.contentid), "")
                            })
                        
                        if len(all_tours_for_schedule) >= total_tour_slots:
                            break
                
                print(f"✅ 총 {len(all_tours_for_schedule)}개 관광지 확정")
            
            # 폴백: 기존 로직 사용 (scored_attractions가 없는 경우)
            elif region and len(all_tours_for_schedule) < total_tour_slots:
                print(f"⚠️ 스코어링 데이터 없음, 기존 로직 사용")
                additional_tours = self._get_additional_attractions(region, selected_tours, preferences, additional_needed)
                
                for tour in additional_tours:
                    region_name = tour.get("region", "")
                    address_full = tour.get("address_full", "")
                    addr1 = tour.get("addr1", "")
                    
                    display_address = ""
                    if addr1 and addr1 != "전북특별자치도":
                        display_address = addr1
                    elif region_name and region_name != "전북특별자치도":
                        display_address = f"전북 {region_name}"
                    elif address_full and address_full != "전북특별자치도":
                        display_address = address_full
                    else:
                        display_address = f"전북 {region_name}" if region_name else "주소 정보 없음"
                    
                    all_tours_for_schedule.append({
                        "tour_id": tour.get("contentid", f"additional_{len(all_tours_for_schedule)}"),
                        "name": tour.get("name", ""),
                        "address": display_address,
                        "photo": tour.get("image_url", "")
                    })
        
        # 속도 최적화를 위해 AI Agent 비활성화하고 바로 규칙 기반 일정 생성 사용
        print("⚡ 속도 최적화: 규칙 기반 일정 생성 사용")
        return self._generate_rule_based_schedule(duration, start_date_str, start_date_obj, selected_farm, all_tours_for_schedule, region)
    
    def generate_travel_summary(self, 
                               itinerary_data: List[Dict], 
                               natural_request: str,
                               user_preferences: Dict[str, Any],
                               region: str) -> Dict[str, Any]:
        """
        확정된 일정을 바탕으로 매력적인 일여행 요약 생성
        
        Args:
            itinerary_data: 확정된 일정 데이터
            natural_request: 사용자의 원본 자연어 요청
            user_preferences: 사용자 선호도 (간단 자연어 포함)
            region: 여행 지역
        
        Returns:
            AI가 생성한 매력적인 여행 요약
        """
        
        print(f"🎨 일여행 요약 생성 시작: {region} {len(itinerary_data)}일 일정")
        
        # 사용자 선호 키워드 추출
        user_keywords = user_preferences.get('simple_natural_words', [])
        travel_styles = user_preferences.get('travel_style_keywords', [])
        landscape_prefs = user_preferences.get('landscape_keywords', [])
        
        # 일정에서 주요 정보 추출
        farm_activities = []
        tourist_spots = []
        
        for day in itinerary_data:
            if day.get('schedule_type') == '농가':
                farm_activities.append({
                    'day': day.get('day'),
                    'name': day.get('name'),
                    'date': day.get('date')
                })
            elif day.get('schedule_type') == '관광지':
                tourist_spots.append({
                    'day': day.get('day'),
                    'name': day.get('name'),
                    'date': day.get('date')
                })
        
        system_prompt = f"""
당신은 농촌 일여행 전문 여행 에디터입니다. 
확정된 일정을 바탕으로 사용자가 설레고 기대되는 매력적인 여행 요약을 작성해주세요.

## 작성 가이드라인
1. **친근하고 설레게 하는 톤앤매너** 사용
2. **구체적인 체험 포인트**와 **특별한 매력** 강조  
3. **사용자 선호도**를 자연스럽게 반영
4. **이모지 활용**으로 시각적 매력도 향상
5. **실용적인 팁**도 포함 (포토스팟, 추천 시간대 등)

## 출력 형식
- 제목: 지역명 + 매력적인 카피
- 본문: 3-4개 섹션으로 구성
- 길이: 200-300자 내외 (너무 길지 않게)
- 마무리: 격려와 기대감 조성
"""
        
        user_prompt = f"""
## 확정된 {region} 일여행 정보

**사용자 요청**: "{natural_request}"
**선호 키워드**: {user_keywords}
**여행 스타일**: {travel_styles}
**선호 풍경**: {landscape_prefs}

**농가 체험 활동**:
{farm_activities}

**관광지 방문**:
{tourist_spots}

위 정보를 바탕으로 사용자가 정말 기대되고 설레는 일여행 요약을 작성해주세요!
"""
        
        try:
            response = self.openai_service.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,  # 창의적인 표현을 위해 조금 높게
                max_tokens=800
            )
            
            summary_text = response.choices[0].message.content
            
            return {
                "status": "success",
                "data": {
                    "summary": summary_text,
                    "region": region,
                    "total_days": len(set(day.get('day') for day in itinerary_data)),
                    "highlights": {
                        "farm_count": len(farm_activities),
                        "tourist_count": len(tourist_spots),
                        "user_keywords": user_keywords
                    }
                }
            }
            
        except Exception as e:
            print(f"❌ 일여행 요약 생성 실패: {e}")
            return {
                "status": "error",
                "message": "여행 요약 생성 중 오류가 발생했습니다.",
                "error": str(e)
            }
    
    def _build_system_prompt(self, duration: int) -> str:
        """AI 일정 생성 시스템 프롬프트"""
        return f"""
당신은 전북 농촌 일여행 일정 생성 전문 AI입니다.

## 필수 규칙 (반드시 준수)

1. **기간**: {duration}일 일정 생성
2. **농가 배치 규칙**:
   - 5-6일: 첫째날, 마지막날 제외하고 농가 일정 배치
   - 7일 이상: 첫째날, 마지막 하루 전날, 마지막날 제외하고 농가 일정 배치
3. **관광지 배치 및 시간**:
   - 5-6일: 첫째날(15:00), 마지막날(10:00)
   - 7일 이상: 첫째날(15:00), 마지막하루전날(10:00, 15:00 2개), 마지막날(10:00)
4. **농가 시간**: 선택된 농가의 start_time, end_time 사용
5. **관광지 중복 금지**: 동일한 관광지를 여러 번 배치하지 마세요
6. **중요**: 농가 데이터의 work_date 필드는 무시하고, 위 규칙에 따라 농가 일정을 배치하세요
7. **김제지평선축제 특별 배치 (매우 중요!)**: 
   - 김제 지역이고 관광지 목록에 "김제지평선축제"가 있는 경우
   - 7일 이상 일정에서 반드시 마지막하루전날(duration-1일차) 15:00에 배치해야 함
   - 마지막날(duration일차)이 아닌 마지막하루전날(duration-1일차)에 배치
   - 다른 관광지보다 절대적 우선권을 가짐

## 출력 형식 (JSON)
```json
{{
  "itinerary": [
    {{
      "day": 1,
      "date": "9월 1일 (일)",
      "schedule_type": "관광지",
      "name": "장소명",
      "start_time": "15:00",
      "address": "주소"
    }}
  ]
}}
```
"""
    
    def _build_user_prompt(self, natural_request: str, selected_farm: Dict, 
                          selected_tours: List[Dict], preferences: Dict, 
                          duration: int, start_date_str: str, start_date_obj: datetime) -> str:
        """사용자 프롬프트 구성"""
        
        import json
        
        # 날짜별 일정 생성
        schedule_dates = []
        for i in range(duration):
            current_date = start_date_obj + timedelta(days=i)
            day_name = ["월", "화", "수", "목", "금", "토", "일"][current_date.weekday()]
            schedule_dates.append({
                "day": i + 1,
                "date": current_date.strftime(f"%m월 %d일 ({day_name})")
            })
        
        # 농가 배치 규칙에 따른 농가 날짜 결정
        if duration <= 6:
            farm_days = list(range(2, duration))  # 2일차~(마지막-1)일차
        else:
            farm_days = list(range(2, duration - 1))  # 2일차~(마지막-2)일차
        
        # 필요한 관광지 개수 계산 - 20개 관광지를 충분히 활용
        total_tour_slots = 0
        if duration <= 6:
            total_tour_slots = 8  # 충분한 관광지 확보 (2개 필요하지만 여유분 포함)
        else:
            total_tour_slots = 15  # 충분한 관광지 확보 (4개 필요하지만 여유분 포함)
        
        # 간단 자연어(pref_etc) 추출
        user_preferences_text = preferences.get('simple_natural_words', [])
        
        return f"""
## 일정 생성 요청
- 자연어 요청: "{natural_request}"
- 기간: {duration}일
- 시작날짜: {start_date_str}
- 사용자 선호 키워드: {user_preferences_text}
- 전체 사용자 선호도: {preferences}

## 날짜 정보
{json.dumps(schedule_dates, ensure_ascii=False, indent=2)}

## 농가 배치 규칙 (중요!)
- 농가 일정 배치 날짜: {farm_days}일차 (즉, {[schedule_dates[day-1]["date"] for day in farm_days if day <= len(schedule_dates)]})
- 농가가 없는 날짜: 관광지 배치

## 선택된 농가 (work_date 필드 무시!)
{json.dumps({k: v for k, v in selected_farm.items() if k != "work_date"}, ensure_ascii=False, indent=2)}

## 선택된 관광지들
{json.dumps(selected_tours, ensure_ascii=False, indent=2)}

위 정보를 바탕으로 {duration}일 농촌 일여행 일정을 생성해주세요.

**절대 준수 사항:**
1. 농가 데이터의 work_date 필드는 완전히 무시하고 절대 참고하지 마세요
2. 농가 일정은 반드시 {farm_days}일차에만 배치하세요
3. 농가 일정이 있는 날에는 관광지를 배치하지 마세요
4. 각 일정의 date 필드는 위 날짜 정보를 정확히 사용하세요
5. 사용자가 선택한 관광지는 반드시 포함하세요
6. 동일한 관광지를 중복 배치하지 마세요
7. 관광지 배치 개수: {total_tour_slots}개 (5-6일: 2개, 7일이상: 4개)
8. **김제지평선축제 필수 규칙**: 김제 지역이고 7일 이상 일정이며 김제지평선축제가 관광지 목록에 있다면, 반드시 마지막하루전날(duration-1일차) 15:00에 배치해야 함. 마지막날(duration일차)이 아닌 마지막하루전날임을 명심하세요.
9. 농가 이름은 선택된 농가의 "farm" 필드를, 관광지 이름은 "name" 필드를 정확히 사용하세요
"""
    
    def _format_itinerary_as_text(self, itinerary: List[Dict[str, Any]]) -> str:
        """일정 데이터를 읽기 쉬운 텍스트로 변환"""
        if not itinerary:
            return "일정이 생성되지 않았습니다."
        
        formatted_lines = []
        formatted_lines.append("🌾 전북 농촌 일여행 맞춤형 일정\n")
        
        for item in itinerary:
            day = item.get('day', '?')
            date = item.get('date', '날짜 미정')
            schedule_type = item.get('schedule_type', '활동')
            name = item.get('name', '장소명')
            start_time = item.get('start_time', '시간 미정')
            address = item.get('address', '주소 미정')
            
            emoji = "🚜" if schedule_type == "농가" else "🏞️"
            display_type = "농가" if schedule_type == "농가" else "관광"
            
            formatted_lines.append(f"【{day}일차 - {date}】")
            formatted_lines.append(f"{emoji} {display_type}: {name}")
            formatted_lines.append(f"⏰ 시간: {start_time}")
            formatted_lines.append(f"📍 주소: {address}")
            formatted_lines.append("")  # 빈 줄
        
        return "\n".join(formatted_lines)

    def _format_bubble_friendly_schedule(self, itinerary: List[Dict[str, Any]], duration: int) -> Dict[str, Any]:
        """Bubble 친화적인 일정 구조로 변환"""
        
        # 농가 배치 규칙 확인
        if duration <= 6:
            farm_days = list(range(2, duration))  # 2일차~(마지막-1)일차
            tour_days = [1, duration]  # 첫째날, 마지막날
        else:
            farm_days = list(range(2, duration - 1))  # 2일차~(마지막-2)일차
            tour_days = [1, duration - 1, duration]  # 첫째날, 마지막하루전날, 마지막날
        
        bubble_schedule = {
            "individual_days": [],  # 개별 일자별 상세 정보
            "grouped_schedule": [],  # Bubble 표시용 그룹화된 일정
            "calendar_events": [],   # 캘린더용 구조화된 데이터 (새로 추가)
            "farm_period": None,     # 농가 일정 기간
            "tour_days": []         # 관광지 일정 날들
        }
        
        # 개별 일자별 상세 정보 (기존 형태 유지)
        bubble_schedule["individual_days"] = itinerary
        
        # 캘린더용 이벤트 데이터 생성
        calendar_events = []
        for item in itinerary:
            # 한국어 날짜를 datetime 객체로 변환
            calendar_date = self._convert_korean_date_to_calendar_format(item.get('date', ''))
            activity_name = item.get('name', '알 수 없는 활동')
            
            calendar_events.append({
                "date": calendar_date,  # mm/dd/yyyy hh:mm xx 형식
                "activity": activity_name,  # 농가 이름 or 관광지 이름
                "day": item.get('day', 1),
                "type": item.get('schedule_type', '활동')
            })
        
        bubble_schedule["calendar_events"] = calendar_events
        
        # 농가 일정 그룹화
        if farm_days:
            farm_info = next((item for item in itinerary if item.get('schedule_type') == '농가'), None)
            if farm_info:
                start_day = min(farm_days)
                end_day = max(farm_days)
                start_date = next((item.get('date', '') for item in itinerary if item.get('day') == start_day), '')
                end_date = next((item.get('date', '') for item in itinerary if item.get('day') == end_day), '')
                
                bubble_schedule["farm_period"] = {
                    "type": "farm_period",
                    "start_day": start_day,
                    "end_day": end_day,
                    "start_date": start_date,
                    "end_date": end_date,
                    "duration_days": len(farm_days),
                    "farm_name": farm_info.get('name', ''),
                    "farm_address": farm_info.get('address', ''),
                    "work_time": f"{farm_info.get('start_time', '08:00')}-{farm_info.get('end_time', '17:00')}",
                    "description": f"Day {start_day}~{end_day}: {farm_info.get('name', '')} 농가 일정"
                }
        
        # 관광지 일정들 
        tour_items = [item for item in itinerary if item.get('schedule_type') == '관광지']
        for tour_item in tour_items:
            bubble_schedule["tour_days"].append({
                "type": "tour",
                "day": tour_item.get('day'),
                "date": tour_item.get('date', ''),
                "tour_name": tour_item.get('name', ''),
                "tour_address": tour_item.get('address', ''),
                "start_time": tour_item.get('start_time', ''),
                "description": f"Day {tour_item.get('day')}: {tour_item.get('name', '')} 관광"
            })
        
        # 그룹화된 일정 (Bubble 표시용)
        grouped_items = []
        
        # 첫째날 관광지
        first_day_tour = next((item for item in tour_items if item.get('day') == 1), None)
        if first_day_tour:
            grouped_items.append({
                "order": 1,
                "type": "tour",
                "title": f"Day 1: 도착 및 관광",
                "subtitle": first_day_tour.get('name', ''),
                "date": first_day_tour.get('date', ''),
                "start_time": first_day_tour.get('start_time', ''),
                "description": f"{first_day_tour.get('date', '')} {first_day_tour.get('start_time', '')}",
                "details": first_day_tour
            })
        
        # 농가 일정 (묶어서 표시)
        if bubble_schedule["farm_period"]:
            farm_period = bubble_schedule["farm_period"]
            grouped_items.append({
                "order": 2,
                "type": "farm_period",
                "title": f"Day {farm_period['start_day']}~{farm_period['end_day']}: 농가 체험",
                "subtitle": farm_period['farm_name'],
                "description": f"{farm_period['duration_days']}일간 농가 일정 ({farm_period['work_time']})",
                "details": farm_period
            })
        
        # 마지막 하루 전날 관광지들 (7일 이상일 때)
        if duration >= 7:
            second_last_day_tours = [item for item in tour_items if item.get('day') == duration - 1]
            if second_last_day_tours:
                tour_names = [tour.get('name', '') for tour in second_last_day_tours]
                grouped_items.append({
                    "order": 3,
                    "type": "tour_multiple",
                    "title": f"Day {duration-1}: 관광지 투어",
                    "subtitle": " & ".join(tour_names),
                    "description": f"{len(second_last_day_tours)}개 관광지",
                    "details": second_last_day_tours
                })
        
        # 마지막날 관광지
        last_day_tour = next((item for item in tour_items if item.get('day') == duration), None)
        if last_day_tour:
            grouped_items.append({
                "order": 4,
                "type": "tour",
                "title": f"Day {duration}: 마무리 관광",
                "subtitle": last_day_tour.get('name', ''),
                "date": last_day_tour.get('date', ''),
                "start_time": last_day_tour.get('start_time', ''),
                "description": f"{last_day_tour.get('date', '')} {last_day_tour.get('start_time', '')}",
                "details": last_day_tour
            })
        
        bubble_schedule["grouped_schedule"] = grouped_items
        
        return bubble_schedule
    
    def _validate_schedule_rules(self, itinerary: List[Dict[str, Any]], duration: int, selected_farm: Dict) -> bool:
        """AI 생성된 일정이 배치 규칙을 준수하는지 검증"""
        try:
            # 농가 배치 날짜 규칙 확인
            if duration <= 6:
                expected_farm_days = list(range(2, duration))  # 2일차~(마지막-1)일차
                expected_tour_days = [1, duration]  # 첫째날, 마지막날
            else:
                expected_farm_days = list(range(2, duration - 1))  # 2일차~(마지막-2)일차
                expected_tour_days = [1, duration - 1, duration]  # 첫째날, 마지막하루전날, 마지막날
            
            farm_days_actual = []
            tour_days_actual = []
            
            for item in itinerary:
                day = item.get('day', 0)
                schedule_type = item.get('schedule_type', '')
                
                if schedule_type == "농가":
                    farm_days_actual.append(day)
                elif schedule_type == "관광지":
                    tour_days_actual.append(day)
            
            # 농가 배치 규칙 검증
            if set(farm_days_actual) != set(expected_farm_days):
                print(f"농가 배치 규칙 위반: 예상 {expected_farm_days}, 실제 {farm_days_actual}")
                return False
            
            # 관광지 배치 기본 규칙 검증
            if not all(day in expected_tour_days for day in tour_days_actual):
                print(f"관광지 배치 규칙 위반: 예상 {expected_tour_days}, 실제 {tour_days_actual}")
                return False
            
            # 7일 이상일 때 마지막하루전날 관광지 2개 규칙 검증
            if duration >= 7:
                second_last_day_tours = [item for item in itinerary if item.get('day') == duration - 1 and item.get('schedule_type') == '관광지']
                if len(second_last_day_tours) != 2:
                    print(f"마지막하루전날 관광지 2개 규칙 위반: {len(second_last_day_tours)}개")
                    return False
                    
                # 김제 지역에서 김제지평선축제 배치 규칙 확인
                if selected_farm and "김제" in selected_farm.get("location", ""):
                    # 전체 일정에서 김제지평선축제가 있는지 확인
                    gimje_festival_available = any('김제지평선축제' in item.get('name', '') for item in itinerary)
                    
                    if gimje_festival_available:
                        # 김제지평선축제가 마지막하루전날 15:00에 배치되었는지 확인
                        gimje_festival_correct = False
                        for item in second_last_day_tours:
                            if '김제지평선축제' in item.get('name', '') and item.get('start_time') == '15:00':
                                gimje_festival_correct = True
                                break
                        
                        # 김제지평선축제가 마지막날에 배치되었는지도 확인 (이는 규칙 위반)
                        last_day_tours = [item for item in itinerary if item.get('day') == duration and item.get('schedule_type') == '관광지']
                        gimje_on_last_day = any('김제지평선축제' in item.get('name', '') for item in last_day_tours)
                        
                        if not gimje_festival_correct:
                            print(f"김제지평선축제 배치 규칙 위반: 마지막하루전날 15:00에 배치되어야 함 (현재 배치: {[item.get('name', '') + ' ' + item.get('start_time', '') for item in second_last_day_tours]})")
                            return False
                        
                        if gimje_on_last_day:
                            print(f"김제지평선축제 배치 규칙 위반: 마지막날이 아닌 마지막하루전날에 배치되어야 함")
                            return False
            
            return True
            
        except Exception as e:
            print(f"일정 검증 중 오류: {e}")
            return False
    
    def _generate_rule_based_schedule(self, duration: int, start_date_str: str, start_date_obj: datetime,
                                    selected_farm: Dict, all_tours_for_schedule: List[Dict], region: str = None) -> Dict[str, Any]:
        """규칙 기반 폴백 일정 생성"""
        
        itinerary = []
        
        # 농가 배치 결정 (정확한 규칙 적용)
        if duration <= 6:
            farm_days = list(range(2, duration))  # 2일차~(마지막-1)일차
        else:
            farm_days = list(range(2, duration - 1))  # 2일차~(마지막-2)일차
        
        # 관광지 배치 계획 (중복 방지, 김제지평선축제 특별 배치)
        tour_schedule = {}
        tour_index = 0
        
        # 김제지평선축제 특별 처리 (마지막 하루 전날 15:00에 배치)
        gimje_festival = None
        other_tours = []
        
        print(f"🔍 전체 일정용 관광지 목록 ({len(all_tours_for_schedule)}개):")
        for i, tour in enumerate(all_tours_for_schedule):
            # 중첩 구조 처리
            tour_data = tour.get("raw") or tour
            tour_name = (tour_data.get('name') or 
                        tour_data.get('tour_name') or 
                        tour_data.get('title') or
                        tour.get('title', ''))
            print(f"   {i+1}. {tour_name}")
            if '김제지평선축제' in tour_name:
                if gimje_festival is None:  # 첫 번째 김제지평선축제만 사용
                    gimje_festival = tour
                    print(f"🏆 김제지평선축제 발견!")
                else:
                    print(f"🔄 김제지평선축제 중복 제거")
            else:
                other_tours.append(tour)
        
        # 첫째날 관광지
        if other_tours and tour_index < len(other_tours):
            tour_schedule[1] = [{"tour": other_tours[tour_index], "time": "15:00"}]
            tour_index += 1
        elif gimje_festival and duration <= 6:  # 7일 미만이고 다른 관광지가 없을 때만 축제 사용
            tour_schedule[1] = [{"tour": gimje_festival, "time": "15:00"}]
            gimje_festival = None  # 사용했으므로 제거
        
        # 마지막 하루 전날 관광지 (7일 이상일 때만)
        if duration >= 7:
            tours_for_second_last = []
            
            # 첫 번째 일정 (10:00)
            if other_tours and tour_index < len(other_tours):
                tours_for_second_last.append({"tour": other_tours[tour_index], "time": "10:00"})
                tour_index += 1
            
            # 두 번째 일정 (15:00) - 김제지평선축제 우선
            print(f"🔍 김제지평선축제 배치 조건 확인:")
            print(f"   selected_farm: {bool(selected_farm)}")
            print(f"   김제 주소 포함: {'김제' in selected_farm.get('location', '') if selected_farm else False}")
            print(f"   gimje_festival: {bool(gimje_festival)}")
            
            if selected_farm and "김제" in selected_farm.get("location", "") and gimje_festival:
                print(f"🏆 김제지평선축제를 마지막하루전날 15:00에 배치")
                tours_for_second_last.append({"tour": gimje_festival, "time": "15:00"})
                gimje_festival = None  # 사용했으므로 제거
            elif other_tours and tour_index < len(other_tours):
                print(f"🔄 일반 관광지를 마지막하루전날 15:00에 배치: {other_tours[tour_index].get('name', '이름없음')}")
                tours_for_second_last.append({"tour": other_tours[tour_index], "time": "15:00"})
                tour_index += 1
                if selected_farm and "김제" in selected_farm.get("location", ""):
                    print(f"⚠️ 김제 지역이지만 김제지평선축제가 없거나 이미 사용됨")
            
            if tours_for_second_last:
                tour_schedule[duration - 1] = tours_for_second_last
        
        # 마지막날 관광지
        print(f"🔍 마지막날 관광지 배치 확인: other_tours={len(other_tours)}개, tour_index={tour_index}")
        if other_tours and tour_index < len(other_tours):
            print(f"🏁 마지막날 관광지 배치: {other_tours[tour_index].get('name', '이름없음')}")
            tour_schedule[duration] = [{"tour": other_tours[tour_index], "time": "10:00"}]
            tour_index += 1
        else:
            # 관광지가 부족한 경우 추가 관광지 찾기
            print(f"🔍 마지막날 관광지 부족, 추가 관광지 검색 중...")
            additional_tours = self._get_additional_attractions(region, [], {}, 1)
            if additional_tours:
                print(f"🏁 추가 관광지 배치: {additional_tours[0].get('name', '이름없음')}")
                tour_schedule[duration] = [{"tour": additional_tours[0], "time": "10:00"}]
            else:
                print(f"❌ 추가 관광지를 찾을 수 없어 마지막날 일정 누락")
        
        # 일정 생성
        for day in range(1, duration + 1):
            current_date = start_date_obj + timedelta(days=day-1)
            day_name = ["월", "화", "수", "목", "금", "토", "일"][current_date.weekday()]
            formatted_date = current_date.strftime(f"%m월 %d일 ({day_name})")
            
            if day in farm_days and selected_farm:
                # 농가 일정 (work_date 완전 무시)
                print(f"🚜 농가 데이터 확인: {selected_farm}")
                
                # 중첩된 구조 확인 (raw 필드가 있는 경우)
                farm_data = selected_farm.get("raw") or selected_farm
                print(f"🚜 실제 농가 데이터: {farm_data}")
                
                # 다양한 필드명에서 농가명 추출 시도
                farm_name = (farm_data.get("farm") or 
                           farm_data.get("name") or 
                           farm_data.get("title") or 
                           farm_data.get("farm_name") or
                           selected_farm.get("title") or  # 최상위 레벨도 확인
                           "농가명 미정")
                
                farm_address = (farm_data.get("address") or 
                              farm_data.get("addr1") or 
                              farm_data.get("location") or
                              selected_farm.get("location") or  # 최상위 레벨도 확인
                              "주소 미정")
                
                print(f"🚜 농가 일정 생성: {farm_name} at {farm_address}")
                
                itinerary.append({
                    "day": day,
                    "date": formatted_date,
                    "schedule_type": "농가",
                    "name": farm_name,
                    "start_time": selected_farm.get("start_time", "08:00"),
                    "address": farm_address
                })
            elif day in tour_schedule:
                # 관광지 일정 (중복 방지)
                for tour_info in tour_schedule[day]:
                    tour = tour_info["tour"]
                    start_time = tour_info["time"]
                    
                    # 관광지 데이터의 중첩 구조 처리
                    tour_data = tour.get("raw") or tour
                    
                    # 관광지 이름과 주소 추출 (여러 필드명 지원)
                    tour_name = (tour_data.get("name") or 
                               tour_data.get("tour_name") or 
                               tour_data.get("title") or
                               tour.get("title", ""))  # 최상위 레벨도 확인
                               
                    tour_address = (tour_data.get("address") or 
                                  tour_data.get("address_full") or
                                  tour.get("location", ""))  # 최상위 레벨도 확인
                    
                    if not tour_name:  # 이름이 여전히 없으면 더 자세히 확인
                        print(f"⚠️ 관광지 이름 없음: {tour}")
                        tour_name = "관광지명 미정"
                    
                    print(f"🏞️ 관광지 일정 생성: {tour_name} at {tour_address}")
                    
                    itinerary.append({
                        "day": day,
                        "date": formatted_date,
                        "schedule_type": "관광지",
                        "name": tour_name,
                        "start_time": start_time,
                        "address": tour_address
                    })
        
        print(f"🎯 규칙 기반 일정 생성 완료: 총 {len(itinerary)}개 일정, 예상 일수 {duration}일")
        for item in itinerary:
            print(f"   Day {item.get('day')}: {item.get('schedule_type')} - {item.get('name')}")
        
        schedule_text = self._format_itinerary_as_text(itinerary)
        bubble_schedule = self._format_bubble_friendly_schedule(itinerary, duration)
        
        # 숙박, 음식점 데이터 추가
        accommodations = []
        restaurants = []
        if region:
            regional_accommodations = self._load_regional_accommodations(region)
            regional_restaurants = self._load_regional_restaurants(region)
            accommodations = self._get_accommodation_cards(regional_accommodations, 5)
            restaurants = self._get_restaurant_cards(regional_restaurants, 5)
        
        return {
            "status": "success",
            "data": {
                "itinerary_id": f"schedule_rule_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "total_days": duration,
                "days": duration,
                "itinerary": itinerary,  # 기존 형태 (호환성 유지)
                "schedule_text": schedule_text,
                "bubble_schedule": bubble_schedule,  # Bubble 친화적 구조
                "accommodations": accommodations,
                "restaurants": restaurants,
                "region": region,
                # Bubble 접근성 향상을 위한 추가 필드
                "summary": {
                    "duration": duration,
                    "farm_days_count": len([item for item in itinerary if item.get('schedule_type') == '농가']),
                    "tour_days_count": len([item for item in itinerary if item.get('schedule_type') == '관광지']),
                    "region": region
                }
            }
        }
    
    def process_feedback(self, itinerary_id: str, feedback: str, 
                        original_schedule: Dict[str, Any]) -> Dict[str, Any]:
        """사용자 피드백을 반영한 일정 수정"""
        
        feedback_prompt = f"""
기존 일정을 다음 피드백에 따라 수정해주세요:
피드백: "{feedback}"

기존 일정:
{original_schedule}

수정 시 주의사항:
1. 농가 일정이 있는 날에는 관광지를 배치하지 마세요
2. 기존 농가 약속은 최대한 보호해주세요
3. 피드백 내용만 반영해서 최소한으로 수정해주세요

수정된 일정을 JSON 형식으로 반환해주세요.
"""
        
        try:
            response = self.openai_service.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "일정 수정 전문 AI입니다."},
                    {"role": "user", "content": feedback_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            
            itinerary_data = result.get("itinerary", [])
            schedule_text = self._format_itinerary_as_text(itinerary_data)
            bubble_schedule = self._format_bubble_friendly_schedule(itinerary_data, len(itinerary_data))
            
            return {
                "status": "success",
                "data": {
                    "itinerary_id": itinerary_id,
                    "total_days": len(itinerary_data),
                    "days": len(itinerary_data),
                    "itinerary": itinerary_data,  # 기존 형태 (호환성 유지)
                    "schedule_text": schedule_text,
                    "bubble_schedule": bubble_schedule,  # Bubble 친화적 구조
                    "changes_made": [f"'{feedback}' 피드백이 반영되었습니다."],
                    # Bubble 접근성 향상을 위한 추가 필드
                    "summary": {
                        "duration": len(itinerary_data),
                        "farm_days_count": len([item for item in itinerary_data if item.get('schedule_type') == '농가']),
                        "tour_days_count": len([item for item in itinerary_data if item.get('schedule_type') == '관광지']),
                        "feedback_applied": True
                    }
                }
            }
            
        except Exception as e:
            print(f"❌ 피드백 처리 실패: {e}")
            return {
                "status": "error",
                "error_code": "FEEDBACK_FAILED",
                "message": "피드백 처리 중 오류가 발생했습니다."
            }

# 싱글톤 인스턴스
_scheduling_service = None

def get_simple_scheduling_service() -> SimpleSchedulingService:
    """SimpleSchedulingService 싱글톤 반환"""
    global _scheduling_service
    if _scheduling_service is None:
        _scheduling_service = SimpleSchedulingService()
    return _scheduling_service