"""
전북특별자치도 지역 매핑 시스템
System_Improvements.md 요구사항에 따른 14개 시군 + 읍면동 매핑
"""

from typing import Optional, List, Dict

# 전북특별자치도 14개 시군과 하위 읍면동 매핑
JEONBUK_REGIONS = {
    "고창군": [
        "고창읍", "고수면", "공음면", "대산면", "무장면", "부안면",
        "상하면", "성내면", "성송면", "신림면", "심원면",
        "아산면", "안남면", "해리면", "흥덕면"
    ],
    "군산시": [
        "나운동", "나포면", "대야면", "미성동", "옥구읍", "옥산면",
        "옥서면", "임피면", "회현면", "개정동", "소룡동", "월명동"
    ],
    "김제시": [
        "검산동", "교동", "금산면", "만경읍", "백구면", "백산면",
        "봉남면", "부량면", "성덕면", "신풍동", "용지면",
        "죽산면", "청하면", "황산면"
    ],
    "남원시": [
        "금동", "도통동", "왕정동", "향교동", "운봉읍", "산내면",
        "주천면", "송동면", "주생면", "이백면", "대산면",
        "인월면", "아영면", "동충동"
    ],
    "무주군": [
        "무주읍", "안성면", "부남면", "설천면", "적상면"
    ],
    "부안군": [
        "부안읍", "계화면", "동진면", "변산면", "보안면", "상서면",
        "위도면", "주산면", "줄포면", "진서면", "하서면", "행안면"
    ],
    "순창군": [
        "순창읍", "구림면", "금과면", "동계면", "복흥면",
        "쌍치면", "유등면", "인계면", "적성면", "팔덕면"
    ],
    "완주군": [
        "삼례읍", "봉동읍", "용진읍", "상관면", "구이면", "소양면",
        "이서면", "고산면", "비봉면", "운주면", "화산면", "경천면"
    ],
    "익산시": [
        "중앙동", "남중동", "삼성동", "평화동", "영등동",
        "팔봉동", "춘포면", "왕궁면", "삼기면", "용동면", "용안면",
        "망성면", "함열읍", "웅포면", "황등면"
    ],
    "임실군": [
        "임실읍", "강진면", "덕치면", "삼계면", "성수면",
        "오수면", "운암면", "신평면", "청웅면", "지사면"
    ],
    "장수군": [
        "장수읍", "산서면", "번암면", "계남면", "계북면",
        "천천면", "장계면"
    ],
    "전주시": [
        "덕진구", "완산구"  # 구 단위까지만 반영
    ],
    "정읍시": [
        "수성동", "연지동", "농소동", "북면", "산외면",
        "소성면", "신태인읍", "영원면", "옹동면", "칠보면",
        "태인면", "흥덕면"
    ],
    "진안군": [
        "진안읍", "용담면", "동향면", "상전면", "백운면",
        "성수면", "안천면", "마령면", "부귀면"
    ]
}

# 별칭 처리 (사용자가 "순창" 입력 → "순창군"으로 매핑)
JEONBUK_ALIASES = {
    "고창": "고창군",
    "군산": "군산시",
    "김제": "김제시",
    "남원": "남원시",
    "무주": "무주군",
    "부안": "부안군",
    "순창": "순창군",
    "완주": "완주군",
    "익산": "익산시",
    "임실": "임실군",
    "장수": "장수군",
    "전주": "전주시",
    "정읍": "정읍시",
    "진안": "진안군"
}

def normalize_jeonbuk_region(user_input: str) -> Optional[str]:
    """
    사용자 입력을 전북 표준 지역명으로 변환
    
    Args:
        user_input: 사용자가 입력한 지역명
        
    Returns:
        표준 지역명 또는 None (전북 지역이 아닌 경우)
    """
    if not user_input:
        return None
        
    user_input = user_input.strip()
    
    # 1. 정확한 시군명으로 입력된 경우
    if user_input in JEONBUK_REGIONS:
        return user_input
    
    # 2. 별칭으로 입력된 경우 ("고창" → "고창군")
    if user_input in JEONBUK_ALIASES:
        return JEONBUK_ALIASES[user_input]
    
    # 3. 읍면동으로 입력된 경우 ("고수면" → "고창군")
    for region, subregions in JEONBUK_REGIONS.items():
        if user_input in subregions:
            return region
    
    # 4. 부분 문자열 매칭 ("전북 김제" → "김제시", "김제시 금산면" → "김제시")
    for region in JEONBUK_REGIONS.keys():
        region_base = region.replace('군', '').replace('시', '')
        if region_base in user_input or user_input in region:
            return region
    
    for alias, region in JEONBUK_ALIASES.items():
        if alias in user_input or user_input in alias:
            return region
    
    return None

def is_jeonbuk_region(region_text: str) -> bool:
    """전북 지역인지 확인"""
    return normalize_jeonbuk_region(region_text) is not None

def get_all_jeonbuk_regions() -> List[str]:
    """전북 모든 시군 리스트 반환"""
    return list(JEONBUK_REGIONS.keys())

def get_subregions(region: str) -> List[str]:
    """특정 시군의 하위 읍면동 리스트 반환"""
    return JEONBUK_REGIONS.get(region, [])

def extract_region_from_natural_text(text: str) -> Optional[str]:
    """
    자연어 텍스트에서 전북 지역명 추출
    
    예: "9월에 김제에서 사과 수확하고 싶어" → "김제시"
    """
    if not text:
        return None
    
    text = text.lower()
    
    # 모든 가능한 지역명과 별칭에 대해 매칭 시도
    for region in JEONBUK_REGIONS.keys():
        region_base = region.replace('군', '').replace('시', '')
        if region_base in text:
            return region
    
    for alias in JEONBUK_ALIASES.keys():
        if alias in text:
            return JEONBUK_ALIASES[alias]
    
    # 읍면동 매칭
    for region, subregions in JEONBUK_REGIONS.items():
        for subregion in subregions:
            if subregion.replace('면', '').replace('읍', '').replace('동', '') in text:
                return region
    
    return None

def get_region_info(region: str) -> Dict[str, any]:
    """지역 정보 반환"""
    normalized = normalize_jeonbuk_region(region)
    if not normalized:
        return {}
    
    return {
        "region": normalized,
        "subregions": get_subregions(normalized),
        "is_city": normalized.endswith('시'),
        "is_county": normalized.endswith('군')
    }

# 전북 특별자치도 지역 검증
def validate_jeonbuk_request(user_input: str) -> Dict[str, any]:
    """
    사용자 입력이 전북 지역 요청인지 검증하고 정보 반환
    
    Returns:
        {
            "is_valid": bool,
            "region": str or None,
            "message": str,
            "available_regions": List[str]
        }
    """
    region = extract_region_from_natural_text(user_input)
    
    if region:
        return {
            "is_valid": True,
            "region": region,
            "message": f"전북 {region} 지역으로 인식되었습니다.",
            "available_regions": get_all_jeonbuk_regions()
        }
    else:
        return {
            "is_valid": False,
            "region": None,
            "message": "전북 지역을 찾을 수 없습니다. 전북 지역명을 포함해 주세요.",
            "available_regions": get_all_jeonbuk_regions()
        }