"""
app/nlp/itinerary_generator.py
==============================
MCP(Model Context Protocol)
→ GPT-4o 호출을 통해 **다중‑일정 JSON**을 생성하는 헬퍼 모듈

프로세스
--------
1. 프론트엔드/백엔드에서 구성한 **MCP JSON 문자열**을 입력으로 받습니다.
2. 동일 요청 중복 방지를 위해 `app.utils.caching`(LRU+TTL) 캐시를 먼저 조회.
3. 캐시 미스일 경우 GPT-4o 모델(`settings.itinerary_model`)에 시스템 프롬프트와
   MCP를 전달해 *daily schedule*을 생성합니다.
4. 결과(JSON 문자열)를 캐시에 저장 후 호출자에게 반환합니다.

함수
-----
``generate_itinerary(mcp_json: str) -> dict``
    • 입력: MCP 포맷 문자열
    • 출력: 파싱 가능한 일정 JSON(dict)

Example
~~~~~~~
```python
schedule = generate_itinerary(mcp_str)
print(schedule["day1"])
```
"""

import openai
from app.config import get_settings
from app.utils.caching import get_cache, set_cache

# ─────────────────────────────────────────────────────────────
# OpenAI 클라이언트 초기화 ------------------------------------
# ─────────────────────────────────────────────────────────────
settings = get_settings()
client = openai.Client(api_key=settings.openai_api_key)


def generate_itinerary(mcp_json: str) -> dict:
    """MCP → GPT → 일정 JSON 생성.

    Parameters
    ----------
    mcp_json : str
        MCP(Model Context Protocol) 포맷의 입력 문자열.

    Returns
    -------
    dict
        GPT-4o가 생성한 일정(JSON) 딕셔너리. 예::

            {
              "day1": ["08:00 조개잡이", "13:00 해변 관광", ...],
              "day2": [...]
            }
    """
    # 1) 캐시 확인 ---------------------------------------------------------
    cache_key = f"iti::{hash(mcp_json)}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    # 2) GPT 시스템 프롬프트 ------------------------------------------------
    sys_prompt = (
        "You are an expert rural job & travel planner. "
        "Return ONLY valid JSON with daily schedule array."
    )

    # 3) GPT 호출 ----------------------------------------------------------
    resp = client.chat.completions.create(
        model=settings.itinerary_model,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": mcp_json},
        ],
        temperature=0.2,
        max_tokens=1024,
    )

    # 4) 결과 파싱 및 캐시 --------------------------------------------------
    schedule_json = resp.choices[0].message.content  # GPT 응답(JSON string)
    set_cache(cache_key, schedule_json)
    return schedule_json
