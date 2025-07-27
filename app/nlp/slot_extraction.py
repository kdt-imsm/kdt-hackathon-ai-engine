"""
slot_extraction.py
~~~~~~~~~~~~~~~~~~
사용자 자연어 입력 → GPT-4o-mini → Structured JSON 슬롯 반환.
"""

import openai
from pydantic import BaseModel, Field
from app.config import get_settings
from app.utils.caching import get_cache, set_cache
from app.schemas import UserSlots

settings = get_settings()
client = openai.Client(api_key=settings.openai_api_key)


class UserSlots(BaseModel):
    """GPT 반환 JSON 구조 정의."""
    start_date: str = Field(..., description="여행 시작일(YYYY-MM-DD)")
    end_date: str = Field(..., description="여행 종료일(YYYY-MM-DD)")
    region: str | None = Field(None, description="희망 지역(시/군 단위)")
    activities: list[str] = Field(default_factory=list, description="희망 활동 tag")


def extract_slots(user_sentence: str) -> UserSlots:
    """
    :param user_sentence: 사용자가 입력한 한국어 자연어 문장
    :return: UserSlots pydantic 객체
    """
    cached = get_cache(f"slots::{user_sentence}")
    if cached:
        return cached  # 중복 호출 방지

    system_prompt = (
        "You are a travel planner AI. "
        "Output only valid JSON that matches the schema."
    )
    function_schema = {
        "name": "fill_slots",
        "description": "Extract structured slots from Korean user query",
        "parameters": UserSlots.model_json_schema()
    }

    resp = client.chat.completions.create(
        model=settings.slot_model,
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": user_sentence}],
        tools=[{"type": "function", "function": function_schema}],
        tool_choice="auto"
    )
    # tools_call → arguments
    args = resp.choices[0].message.tool_calls[0].function.arguments
    slots = UserSlots.model_validate_json(args)

    set_cache(f"slots::{user_sentence}", slots)
    return slots
