"""
관광지 스코어링 유틸리티

사용자 선호도 기반 관광지 점수 계산
- travel_style_keywords 우선 (가중치 높음)
- landscape_keywords는 다를 때만 제외, 일치 시 보너스 점수
"""

from typing import List, Dict, Optional, Set
import pandas as pd
from dataclasses import dataclass


@dataclass
class AttractionScore:
    """관광지 점수 정보"""
    name: str
    region: str
    address_full: str
    lat: float
    lon: float
    contentid: str
    landscape_keywords: Optional[str]
    travel_style_keywords: Optional[str]
    score: float
    travel_style_matches: int
    landscape_match: bool
    has_image: bool = True  # 이미지 존재 여부


def parse_keywords(keyword_str: Optional[str]) -> Set[str]:
    """키워드 문자열을 세트로 파싱"""
    if not keyword_str or pd.isna(keyword_str):
        return set()
    return set(k.strip() for k in keyword_str.split(';') if k.strip())


def calculate_attraction_score(
    attraction: Dict,
    user_travel_styles: Set[str],
    user_landscapes: Optional[List[str]]  # 복수 landscape 지원으로 변경
) -> AttractionScore:
    """
    관광지 점수 계산
    
    점수 계산 로직:
    1. travel_style_keywords 매칭 (각 매칭당 10점)
    2. landscape_keywords가 사용자 선택과 전혀 일치하지 않으면 제외 (-1000점)
    3. landscape_keywords가 일치하면 작은 보너스 (1점) - 동점 처리용
    4. landscape_keywords가 없으면 페널티 없음 (0점) - 많은 데이터가 landscape 없음
    """
    # 관광지 키워드 파싱
    travel_styles = parse_keywords(attraction.get('travel_style_keywords'))
    landscape = attraction.get('landscape_keywords')
    if pd.isna(landscape):
        landscape = None
    
    # travel_style 매칭 계산
    travel_style_matches = len(user_travel_styles & travel_styles)
    travel_style_score = travel_style_matches * 10
    
    # landscape 매칭 계산 (복수 선택 지원)
    landscape_score = 0
    landscape_match = False
    
    if user_landscapes and landscape:
        # 사용자가 선택한 landscape 중 하나라도 일치하는지 확인
        if landscape in user_landscapes:
            # 일치하는 경우 보너스 (동점 처리용)
            landscape_score = 5
            landscape_match = True
        else:
            # 일치하지 않아도 완전히 제외하지 않고 작은 페널티만
            landscape_score = -2
    # landscape가 없는 경우는 0점 (페널티 없음, 일치하는 것과 동일하게 취급)
    
    total_score = travel_style_score + landscape_score
    
    # 헤더 행 필터링 (lat='lat', lon='lon'인 경우 제외)
    if attraction.get('lat') == 'lat' or attraction.get('lon') == 'lon' or attraction.get('name') == 'name':
        return None  # 헤더 행은 제외
    
    try:
        lat_val = float(attraction['lat']) if attraction['lat'] and attraction['lat'].strip() else 0.0
        lon_val = float(attraction['lon']) if attraction['lon'] and attraction['lon'].strip() else 0.0
    except (ValueError, TypeError) as e:
        print(f"❌ 좌표 변환 오류 - 관광지: {attraction.get('name', 'Unknown')}")
        print(f"   lat: '{attraction.get('lat', 'None')}', lon: '{attraction.get('lon', 'None')}'")
        print(f"   에러: {e}")
        return None  # 좌표 변환 실패 시 제외
    
    return AttractionScore(
        name=attraction['name'],
        region=attraction['region'],
        address_full=attraction['address_full'],
        lat=lat_val,
        lon=lon_val,
        contentid=str(attraction['contentid']),
        landscape_keywords=landscape,
        travel_style_keywords=attraction.get('travel_style_keywords'),
        score=total_score,
        travel_style_matches=travel_style_matches,
        landscape_match=landscape_match
    )


def score_and_rank_attractions(
    attractions: List[Dict],
    user_travel_styles: List[str],
    user_landscapes: Optional[List[str]] = None,  # 복수 landscape 지원으로 변경
    exclude_contentids: Optional[Set[str]] = None
) -> List[AttractionScore]:
    """
    관광지 점수 계산 및 순위 정렬
    
    Args:
        attractions: 관광지 데이터 리스트
        user_travel_styles: 사용자 여행 스타일 선호도
        user_landscapes: 사용자 풍경 선호도 리스트 (복수 선택 가능)
        exclude_contentids: 제외할 contentid 세트
    
    Returns:
        점수순으로 정렬된 AttractionScore 리스트
    """
    user_travel_styles_set = set(user_travel_styles)
    exclude_contentids = exclude_contentids or set()
    
    scored_attractions = []
    for attraction in attractions:
        # 제외 대상 확인
        if str(attraction.get('contentid')) in exclude_contentids:
            continue
            
        score = calculate_attraction_score(
            attraction,
            user_travel_styles_set,
            user_landscapes  # 복수 landscape 전달
        )
        
        # None 반환 시 건너뛰기 (헤더 행이나 좌표 변환 실패)
        if score is None:
            continue
        
        # 김제지평선축제 특별 처리
        is_gimje_festival = '김제지평선축제' in attraction.get('name', '')
        if is_gimje_festival and score.score < 20:
            score.score = 20
        
        # 모든 관광지 포함 (상위 20개를 무조건 추리기 위해)
        scored_attractions.append(score)
    
    # 점수순 정렬 (높은 점수가 먼저)
    scored_attractions.sort(key=lambda x: (-x.score, x.name))
    
    # 디버깅: 상위 10개 관광지의 점수 출력
    if scored_attractions:
        print(f"📊 관광지 스코어링 결과 (상위 {min(10, len(scored_attractions))}개):")
        for i, attr in enumerate(scored_attractions[:10]):
            print(f"   {i+1}. {attr.name}: {attr.score}점 "
                  f"(travel_match: {attr.travel_style_matches}, landscape_match: {attr.landscape_match})")
    
    return scored_attractions


def get_top_attractions_for_cards(
    scored_attractions: List[AttractionScore],
    limit: int = 5,
    require_image: bool = True
) -> List[AttractionScore]:
    """
    카드 표시용 상위 관광지 선택
    
    Args:
        scored_attractions: 점수 계산된 관광지 리스트
        limit: 반환할 최대 개수
        require_image: 이미지 필수 여부
    
    Returns:
        상위 관광지 리스트
    """
    if require_image:
        # 이미지가 있는 관광지만 필터링 (실제 구현 시 이미지 체크 로직 추가 필요)
        valid_attractions = [a for a in scored_attractions if a.has_image]
    else:
        valid_attractions = scored_attractions
    
    return valid_attractions[:limit]


def get_attractions_for_schedule(
    scored_attractions: List[AttractionScore],
    selected_contentids: Set[str],
    recommended_but_not_selected_ids: Set[str],
    total_needed: int = 10
) -> List[AttractionScore]:
    """
    일정 생성용 관광지 선택
    
    1. 사용자가 선택한 관광지는 반드시 포함
    2. 카드로 추천되었지만 선택되지 않은 것은 제외
    3. 나머지는 점수 순위에서 선택
    
    Args:
        scored_attractions: 점수 계산된 관광지 리스트
        selected_contentids: 사용자가 선택한 contentid 세트
        recommended_but_not_selected_ids: 추천되었지만 선택되지 않은 contentid 세트
        total_needed: 필요한 총 관광지 수
    
    Returns:
        일정용 관광지 리스트
    """
    selected = []
    available_for_schedule = []
    
    for attraction in scored_attractions:
        if attraction.contentid in selected_contentids:
            # 사용자가 선택한 것은 반드시 포함
            selected.append(attraction)
        elif attraction.contentid not in recommended_but_not_selected_ids:
            # 추천되었지만 선택되지 않은 것은 제외하고 나머지만 후보로
            available_for_schedule.append(attraction)
    
    # 선택된 것들 + 나머지 상위 순위
    remaining_needed = total_needed - len(selected)
    result = selected + available_for_schedule[:remaining_needed]
    
    return result