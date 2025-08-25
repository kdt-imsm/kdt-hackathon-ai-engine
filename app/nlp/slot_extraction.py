"""
app/nlp/slot_extraction.py
==========================
GPT 기반 **슬롯 추출(Slot Extraction)** 유틸리티

* 역할
  - 사용자의 자연어 문장(한국어)을 GPT-4o-mini 등에 전달하여
    여행/일정 관련 구조화 슬롯(JSON)을 추출합니다.
  - 동일한 입력에 대해 중복 호출을 방지하기 위해 `app.utils.caching`의
    LRU+TTL 캐시를 활용합니다.

슬롯 스키마 예시
----------------
```
{
  "start_date": "2025-09-01",
  "end_date": "2025-09-03",
  "region_pref": ["전북 고창"],
  "activity_tags": ["조개잡이", "해변"],
  "budget_krw": 200000,
  ...
}
```

함수
-----
``extract_slots(user_sentence: str) -> dict``
    자연어 → 슬롯 딕셔너리. 내부적으로 OpenAI Function Calling을 사용
"""

import openai, functools, json
from app.config import get_settings
from app.utils.caching import get_cache, set_cache
from app.utils.location import normalize_region_names

# ─────────────────────────────────────────────────────────────
# OpenAI 클라이언트 초기화 ------------------------------------
# ─────────────────────────────────────────────────────────────
settings = get_settings()
client = openai.Client(api_key=settings.openai_api_key)  # 공식 snake_case SDK


def extract_slots(user_sentence: str) -> dict:
    """자연어 문장에서 여행 슬롯을 추출해 dict 로 반환.

    Parameters
    ----------
    user_sentence : str
        사용자가 입력한 한국어 자연어 문장.

    Returns
    -------
    dict
        슬롯(JSON) 형태의 딕셔너리.
    """
    # 1) 캐시 체크 ---------------------------------------------------------
    cache_key = f"slots::{user_sentence}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    # 2) 시스템 프롬프트 강화 - 지역명 추출 정확도 향상 ----------------------
    system_prompt = """
You are a travel planner AI specialized in Korean travel planning.
Extract structured slots from user query with high accuracy.

CRITICAL: For region_pref field:
- ONLY extract regions that are EXPLICITLY mentioned by the user
- If NO region is mentioned, return empty array []
- Do NOT infer, assume, or add any regions that are not explicitly stated
- Valid region examples when mentioned: "제주도", "서울", "부산", "경기도", "강원도", "전라북도", "전라남도", "경상북도", "경상남도", "충청북도", "충청남도"
- Keep exact format as mentioned by user

CRITICAL: For activity_tags field:
- Extract ALL activity-related keywords including natural environments, activities, experiences, festivals, and specific attractions
- COMPREHENSIVE keyword categories to extract:
  * Natural environments: "바다", "산", "강", "호수", "계곡", "섬", "해변", "숲", "공원"
  * Activities: "체험", "관광", "등산", "트레킹", "낚시", "수영", "서핑", "스키", "캠핑"
  * Cultural: "문화", "축제", "페스티벌", "전시", "박물관", "미술관", "사찰", "궁궐", "한옥"
  * Recreational: "휴양", "힐링", "스파", "온천", "놀이공원", "테마파크", "동물원", "수족관"
  * Agricultural: "농업", "농장", "목장", "과수원", "포도원", "딸기", "사과", "배", "쌀"
  * Local specialties: "맛집", "특산물", "전통시장", "야시장", "카페", "맥주", "와인"
  * Seasonal: "벚꽃", "단풍", "눈", "겨울", "여름", "봄", "가을"
- Extract specific activity verbs as nouns: "보다" → "관광", "먹다" → "맛집", "즐기다" → "체험"
- Be comprehensive in extracting relevant keywords for better recommendation matching

Answer with valid JSON matching the slot schema.
"""
    function_schema = {
        "name": "fill_slots",
        "description": "Extract structured slots from Korean travel query",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date":        {"type": "string", "format": "date", "description": "여행 시작 날짜 (YYYY-MM-DD)"},
                "end_date":          {"type": "string", "format": "date", "description": "여행 종료 날짜 (YYYY-MM-DD)"},
                "region_pref":       {"type": "array",  "items": {"type": "string"}, "description": "사용자가 명시적으로 언급한 지역만 추출. 언급되지 않으면 빈 배열 []"},
                "activity_tags":     {"type": "array",  "items": {"type": "string"}, "description": "활동, 체험, 관광지, 자연환경 태그 (예: ['농업체험', '관광', '바다', '산', '문화', '체험', '휴양'])"},
                "budget_krw":        {"type": "integer", "description": "예산 (원, 0이면 미지정)"},
                "transport_mode":    {"type": "string"},
                "accommodation_need":{"type": "boolean"},
                "physical_intensity":{"type": "string"},
                "group_size":        {"type": "integer"},
                "special_notes":     {"type": "string"}
            },
            "required": [
                "start_date", "end_date", "region_pref", "activity_tags", "budget_krw"
            ],
        },
    }

    # 3) GPT Function Calling ---------------------------------------------
    resp = client.chat.completions.create(
        model=settings.slot_model,  # ex) gpt-4o-mini
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_sentence},
        ],
        tools=[{"type": "function", "function": function_schema}],
        tool_choice="required",  # 함수 호출 강제
    )

    # 4) 응답 파싱 ---------------------------------------------------------
    message = resp.choices[0].message
    
    # tool_calls가 None이거나 빈 리스트인 경우 처리
    if not message.tool_calls:
        # GPT가 함수를 호출하지 않은 경우, 기본 슬롯 반환
        print(f"경고: GPT가 함수를 호출하지 않았습니다. 응답: {message.content}")
        slots_dict = {
            "start_date": "2025-08-02",
            "end_date": "2025-08-03", 
            "region_pref": [],  # 빈 배열로 수정
            "activity_tags": ["농업체험"],
            "budget_krw": 100000,
            "transport_mode": "자동차",
            "accommodation_need": False,
            "physical_intensity": "보통",
            "group_size": 2,
            "special_notes": "슬롯 추출 실패로 기본값 사용"
        }
    else:
        raw_args = message.tool_calls[0].function.arguments
        slots_dict = json.loads(raw_args)  # JSON string → dict

    # 5) 지역명 정규화 및 확장 처리 ------------------------------------------
    if "region_pref" in slots_dict and slots_dict["region_pref"]:
        original_regions = slots_dict["region_pref"]
        print(f"🔄 지역명 정규화 전: {original_regions}")
        
        # 각 지역명에 대해 정규화 및 확장
        normalized_regions = []
        for region in original_regions:
            # 원본 지역명 유지
            normalized_regions.append(region)
            
            # 시도명 추출 및 추가 (시/군/구에서 자동 추론 포함)
            from app.utils.location import extract_sido, COMPREHENSIVE_REGION_MAPPING
            sido = extract_sido(region)
            if sido and sido != region and sido not in normalized_regions:
                normalized_regions.append(sido)
                print(f"🔄 '{region}'에서 시도 '{sido}' 추출됨")
            
            # 시/군/구인 경우 전체 지역명도 추가 (예: "단양" → "충북 단양")
            if sido and ' ' not in region:  # 공백이 없는 단일 지역명인 경우
                full_region = f"{sido} {region}"
                if full_region not in normalized_regions:
                    normalized_regions.append(full_region)
                    print(f"🔄 전체 지역명 '{full_region}' 추가됨")
            
            # 포괄적 매핑에서 관련 지역들 추가
            if region in COMPREHENSIVE_REGION_MAPPING:
                for mapped_region in COMPREHENSIVE_REGION_MAPPING[region][:3]:  # 최대 3개까지만
                    if mapped_region not in normalized_regions:
                        normalized_regions.append(mapped_region)
        
        # 중복 제거
        slots_dict["region_pref"] = list(dict.fromkeys(normalized_regions))
        print(f"🔄 지역명 정규화 후: {slots_dict['region_pref']}")

    # 6) 캐시에 저장 후 반환 ------------------------------------------------
    set_cache(cache_key, slots_dict)
    return slots_dict
