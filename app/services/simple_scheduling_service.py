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

class SimpleSchedulingService:
    def __init__(self):
        self.openai_service = OpenAIService()
        self.project_root = Path(__file__).parent.parent.parent
    
    def _extract_duration_from_request(self, request: str) -> int:
        """자연어에서 기간 추출 (최대 10일)"""
        # "2주" = 14일 → 10일로 제한
        if "주" in request:
            weeks_match = re.search(r'(\d+)주', request)
            if weeks_match:
                weeks = int(weeks_match.group(1))
                return min(weeks * 7, 10)
        
        # "5일", "3박" 등
        duration_match = re.search(r'(\d+)(?:일|박)', request)
        if duration_match:
            return min(int(duration_match.group(1)), 10)
        
        return 3  # 기본값
    
    def _extract_start_date_from_request(self, request: str, region: str = None) -> tuple[str, datetime]:
        """자연어에서 시작 날짜 추출 (2025년 기준, 9월 4일 이후)"""
        base_date = datetime(2025, 9, 4)  # 오늘을 2025년 9월 4일로 가정
        
        # 김제 지역이고 10월 요청이면 김제지평선축제 고려 (10월 8-12일)
        if region == "김제시" and "10월" in request:
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
                         region: str = None) -> Dict[str, Any]:
        """
        System_Improvements.md 규칙에 따른 일정 생성
        
        규칙:
        - 5-6일: 첫째날/마지막날 제외하고 농가 배치, 첫째날/마지막날에 관광지
        - 7일 이상: 첫째날/마지막하루전날/마지막날 제외하고 농가 배치
                  첫째날(관광지1개), 마지막하루전날(관광지2개), 마지막날(관광지1개)
        """
        
        duration = self._extract_duration_from_request(natural_request)
        start_date_str, start_date_obj = self._extract_start_date_from_request(natural_request, region)
        
        # 지역 추출 (농가 주소에서 추출 또는 매개변수 사용)
        if not region and selected_farm:
            farm_address = selected_farm.get("address", "")
            # 간단한 지역 추출 로직
            for r in ["김제시", "전주시", "군산시", "익산시", "정읍시", "남원시", "고창군", "부안군", "임실군", "순창군", "진안군", "무주군", "장수군", "완주군"]:
                if r in farm_address:
                    region = r
                    break
        
        # 필요한 관광지 개수 계산
        total_tour_slots = 0
        if duration <= 6:
            total_tour_slots = 2  # 첫째날 + 마지막날
        else:
            total_tour_slots = 4  # 첫째날(1개) + 마지막하루전날(2개) + 마지막날(1개)
        
        # 추가 관광지 필요 시 로드 (카드 추천과는 다른 관광지들)
        all_tours_for_schedule = selected_tours.copy()
        if len(selected_tours) < total_tour_slots and region:
            additional_needed = total_tour_slots - len(selected_tours)
            
            # 기존 카드 추천에서 제외된 관광지들을 가져오기 위해
            # 전체 지역 데이터에서 이미 카드로 제시된 것들과 사용자가 선택한 것들을 제외
            additional_tours = self._get_additional_attractions(region, selected_tours, preferences, additional_needed)
            
            # 추가 관광지를 선택된 관광지와 동일한 형식으로 변환
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
        
        # AI 일정 생성 프롬프트
        system_prompt = self._build_system_prompt(duration)
        user_prompt = self._build_user_prompt(
            natural_request, selected_farm, all_tours_for_schedule, preferences, duration, start_date_str, start_date_obj
        )
        
        try:
            response = self.openai_service.client.chat.completions.create(
                model="gpt-4o-mini",  # 비용 최적화
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            
            itinerary_data = result.get("itinerary", [])
            
            # AI 결과 검증: 일정 배치 규칙이 제대로 지켜졌는지 확인
            if not self._validate_schedule_rules(itinerary_data, duration, selected_farm):
                print("❌ AI 일정이 규칙을 위반함 - 규칙 기반으로 폴백")
                return self._generate_rule_based_schedule(duration, start_date_str, start_date_obj, selected_farm, all_tours_for_schedule, region)
            
            schedule_text = self._format_itinerary_as_text(itinerary_data)
            
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
                    "itinerary_id": f"schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "total_days": duration,
                    "days": duration,
                    "itinerary": itinerary_data,
                    "schedule_text": schedule_text,
                    "accommodations": accommodations,
                    "restaurants": restaurants,
                    "region": region
                }
            }
            
        except Exception as e:
            print(f"❌ AI 일정 생성 실패: {e}")
            # 폴백: 규칙 기반 일정 생성
            return self._generate_rule_based_schedule(duration, start_date_str, start_date_obj, selected_farm, all_tours_for_schedule, region)
    
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
7. **김제지평선축제 특별 배치**: 김제 지역의 경우 김제지평선축제는 7일 이상 일정에서 마지막하루전날 15:00에 우선 배치

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
        
        # 필요한 관광지 개수 계산
        total_tour_slots = 0
        if duration <= 6:
            total_tour_slots = 2  # 첫째날 + 마지막날
        else:
            total_tour_slots = 4  # 첫째날(1개) + 마지막하루전날(2개) + 마지막날(1개)
        
        return f"""
## 일정 생성 요청
- 자연어 요청: "{natural_request}"
- 기간: {duration}일
- 시작날짜: {start_date_str}
- 사용자 선호도: {preferences}

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
            
            formatted_lines.append(f"【{day}일차 - {date}】")
            formatted_lines.append(f"{emoji} {schedule_type}: {name}")
            formatted_lines.append(f"⏰ 시간: {start_time}")
            formatted_lines.append(f"📍 주소: {address}")
            formatted_lines.append("")  # 빈 줄
        
        return "\n".join(formatted_lines)
    
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
            
            return True
            
        except Exception as e:
            print(f"일정 검증 중 오류: {e}")
            return False
    
    def _generate_rule_based_schedule(self, duration: int, start_date_str: str, start_date_obj: datetime,
                                    selected_farm: Dict, selected_tours: List[Dict], region: str = None) -> Dict[str, Any]:
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
        for tour in selected_tours:
            if '김제지평선축제' in tour.get('name', ''):
                gimje_festival = tour
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
            if region == "김제시" and gimje_festival:
                tours_for_second_last.append({"tour": gimje_festival, "time": "15:00"})
                gimje_festival = None  # 사용했으므로 제거
            elif other_tours and tour_index < len(other_tours):
                tours_for_second_last.append({"tour": other_tours[tour_index], "time": "15:00"})
                tour_index += 1
            
            if tours_for_second_last:
                tour_schedule[duration - 1] = tours_for_second_last
        
        # 마지막날 관광지
        if other_tours and tour_index < len(other_tours):
            tour_schedule[duration] = [{"tour": other_tours[tour_index], "time": "10:00"}]
            tour_index += 1
        elif gimje_festival:  # 아직 배치되지 않은 김제지평선축제가 있다면
            tour_schedule[duration] = [{"tour": gimje_festival, "time": "10:00"}]
        
        # 일정 생성
        for day in range(1, duration + 1):
            current_date = start_date_obj + timedelta(days=day-1)
            day_name = ["월", "화", "수", "목", "금", "토", "일"][current_date.weekday()]
            formatted_date = current_date.strftime(f"%m월 %d일 ({day_name})")
            
            if day in farm_days and selected_farm:
                # 농가 일정 (work_date 완전 무시)
                itinerary.append({
                    "day": day,
                    "date": formatted_date,
                    "schedule_type": "농가",
                    "name": selected_farm.get("farm", ""),
                    "start_time": selected_farm.get("start_time", "08:00"),
                    "address": selected_farm.get("address", "")
                })
            elif day in tour_schedule:
                # 관광지 일정 (중복 방지)
                for tour_info in tour_schedule[day]:
                    tour = tour_info["tour"]
                    start_time = tour_info["time"]
                    
                    itinerary.append({
                        "day": day,
                        "date": formatted_date,
                        "schedule_type": "관광지",
                        "name": tour.get("name", tour.get("tour_name", "관광지")),
                        "start_time": start_time,
                        "address": tour.get("address", "")
                    })
        
        schedule_text = self._format_itinerary_as_text(itinerary)
        
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
                "itinerary": itinerary,
                "schedule_text": schedule_text,
                "accommodations": accommodations,
                "restaurants": restaurants,
                "region": region
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
            
            return {
                "status": "success",
                "data": {
                    "itinerary_id": itinerary_id,
                    "total_days": len(itinerary_data),
                    "days": len(itinerary_data),
                    "itinerary": itinerary_data,
                    "schedule_text": schedule_text,
                    "changes_made": [f"'{feedback}' 피드백이 반영되었습니다."]
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