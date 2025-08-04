"""
app/utils/mcp.py
================
MCP(**Model Context Protocol**) 포맷 문자열 빌더

• **MCP란?**  LLM 프롬프트 컨텍스트를 *일관된 JSON 스키마*로 묶어주는 규약입니다.
  사용자 *슬롯(Slots)*, *선택 콘텐츠(Selections)*, *제약 조건(Constraints)* 등을
  하나의 JSON 페이로드에 포함시켜 GPT-4o 등의 모델 입력에 활용합니다.
  

구성 필드
---------
meta
    • generated_at : ISO-8601 UTC 타임스탬프
    • version      : 프로토콜 버전(문자열)
slots
    FastAPI `/slots` 단계에서 추출한 Pydantic 객체 → `.model_dump()` 딕션너리
selections
    사용자가 선택한 Job / Tour 카드의 요약 정보(list[dict]).
constraints
    예산·거리 등 추가 제약조건. 현재는 `budget` 하나만 포함.

함수
-----
`build_mcp(slots, selections, budget=None) -> str`
    입력 객체를 직렬화하여 *pretty-printed* JSON 문자열을 반환합니다.

Example
~~~~~~~
```python
mcp_str = build_mcp(slots=slots_obj, selections=[job_dict, tour_dict], budget=200000)
```
"""

import json
from datetime import datetime


def build_mcp(slots, selections, budget: int | None = None) -> str:
    """슬롯 + 선택 콘텐츠 → MCP(JSON) 문자열로 변환.

    Parameters
    ----------
    slots : Pydantic BaseModel
        `app.schemas.SlotsResponse.slots` 와 동일한 형식의 객체.
    selections : list[dict]
        사용자 선택 카드(Job/Tour)의 미리보기 딕션너리 모음.
    budget : int | None, optional
        총 여행 예산(₩). 미지정 시 ``null`` 로 직렬화.

    Returns
    -------
    str
        예쁘게 들여쓰기된(pretty) MCP JSON 문자열.
    """
    payload = {
        "meta": {
            "generated_at": datetime.utcnow().isoformat(),  # 생성 시각(UTC)
            "version": "1.0",
        },
        "slots": slots.model_dump(),
        "selections": selections,
        "constraints": {
            "budget": budget,
        },
    }
    # ensure_ascii=False -> 한글 등 비ASCII도 그대로, indent=2 -> 가독성
    return json.dumps(payload, ensure_ascii=False, indent=2)
