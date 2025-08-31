"""
OpenAI 서비스 (단순화)
일정 생성, 피드백 처리, 자연어 의도 추출용
"""

import json
from typing import Dict, Any, List
from openai import OpenAI
from app.config import get_settings

class OpenAIService:
    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
    
    def extract_intent_from_natural_text(self, natural_request: str) -> Dict[str, Any]:
        """
        자연어에서 여행 의도를 정교하게 추출합니다.
        
        Args:
            natural_request: 사용자의 자연어 입력
            
        Returns:
            추출된 의도 정보 딕셔너리
        """
        
        system_prompt = """
당신은 전북 농촌 관광 전문 자연어 분석 AI입니다.
사용자의 자연어 요청에서 여행 의도를 정확하게 추출해야 합니다.

## 전북 지역 정보 (정확한 매핑 필수)
- 시: 전주시, 군산시, 익산시, 정읍시, 남원시, 김제시
- 군: 완주군, 진안군, 무주군, 장수군, 임실군, 순창군, 고창군, 부안군

## 추출 정보
1. **지역**: 위 목록에서 정확한 행정구역명으로 매핑
2. **시기**: 구체적인 월/계절 정보
3. **기간**: 일수 정확 추출 (한글 숫자 포함: 하루, 이틀, 열흘 등)
4. **활동_유형**: 구체적인 체험 활동
5. **농업_관심사**: 관심있는 작물/농업 분야
6. **여행_스타일**: 체험형/힐링형/관광형 등
7. **선호_환경**: 자연환경 선호도
8. **추가_키워드**: 기타 중요한 키워드들

## 기간 추출 규칙
- 한글 숫자: "열흘" → 10일, "이틀" → 2일, "일주일" → 7일
- 아라비아 숫자: "10일", "3박", "2주" 등
- 대략 표현: "10일 정도", "일주일쯤" 등
- 최대 10일까지만 허용

## 출력 형식 (JSON)
```json
{
  "지역": "김제시",
  "시기": "10월 초",
  "기간": 10,
  "기간_텍스트": "열흘",
  "활동_유형": ["과수원 체험", "농업 체험"],
  "농업_관심사": ["과일", "사과", "배", "수확체험"],
  "여행_스타일": ["체험형", "힐링"],
  "선호_환경": ["자연", "조용한 환경"],
  "추가_키워드": ["축제", "휴식"],
  "신뢰도": 0.9
}
```
"""
        
        user_prompt = f"""
다음 자연어 요청을 분석해 주세요:
"{natural_request}"

전북 지역의 농촌 관광 맥락에서 사용자의 의도를 정확히 파악하고,
위에서 제시한 JSON 형식으로 결과를 반환해 주세요.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            result = json.loads(response.choices[0].message.content)
            print(f"LLM 의도 추출 결과: {result}")
            return result
            
        except Exception as e:
            print(f"❌ 자연어 의도 추출 실패: {e}")
            # 폴백: 기본값 반환
            return {
                "지역": None,
                "시기": None,
                "기간": 3,
                "기간_텍스트": "기본값",
                "활동_유형": [],
                "농업_관심사": [],
                "여행_스타일": [],
                "선호_환경": [],
                "추가_키워드": [],
                "신뢰도": 0.0,
                "error": str(e)
            }
    
    def enhance_keywords_with_context(self, extracted_intent: Dict[str, Any], 
                                    user_preferences: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        LLM 추출 결과와 사용자 선호도를 결합하여 향상된 키워드 세트 생성
        
        Args:
            extracted_intent: LLM이 추출한 의도 정보
            user_preferences: 사용자가 선택한 선호도
            
        Returns:
            향상된 키워드 딕셔너리
        """
        
        enhanced_keywords = {
            "job_type_keywords": [],
            "travel_style_keywords": [],
            "landscape_keywords": [],
            "activity_keywords": [],
            "seasonal_keywords": []
        }
        
        # 1. 기존 사용자 선호도 통합
        enhanced_keywords["job_type_keywords"].extend(user_preferences.get("job_type_keywords", []))
        enhanced_keywords["travel_style_keywords"].extend(user_preferences.get("travel_style_keywords", []))
        enhanced_keywords["landscape_keywords"].extend(user_preferences.get("landscape_keywords", []))
        
        # 2. LLM 추출 결과 통합
        enhanced_keywords["job_type_keywords"].extend(extracted_intent.get("농업_관심사", []))
        enhanced_keywords["travel_style_keywords"].extend(extracted_intent.get("여행_스타일", []))
        enhanced_keywords["landscape_keywords"].extend(extracted_intent.get("선호_환경", []))
        enhanced_keywords["activity_keywords"].extend(extracted_intent.get("활동_유형", []))
        
        # 3. 시기별 키워드 추가
        시기 = extracted_intent.get("시기", "")
        if 시기:
            if "9월" in 시기 or "가을" in 시기:
                enhanced_keywords["seasonal_keywords"].extend(["수확", "단풍", "서늘한", "가을"])
            elif "10월" in 시기:
                enhanced_keywords["seasonal_keywords"].extend(["수확", "단풍", "축제", "가을"])
            elif "봄" in 시기:
                enhanced_keywords["seasonal_keywords"].extend(["봄꽃", "신록", "따뜻한"])
        
        # 4. 중복 제거 및 정리
        for key in enhanced_keywords:
            enhanced_keywords[key] = list(set(enhanced_keywords[key]))
        
        print(f"🔍 향상된 키워드 세트: {enhanced_keywords}")
        return enhanced_keywords