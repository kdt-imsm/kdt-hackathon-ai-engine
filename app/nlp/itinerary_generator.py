"""
itinerary_generator.py
~~~~~~~~~~~~~~~~~~~~~~
MCP → GPT-4o → 다중 일정(JSON) 생성.
"""

import openai
from app.config import get_settings
from app.utils.caching import get_cache, set_cache

settings = get_settings()
client = openai.Client(api_key=settings.openai_api_key)


def generate_itinerary(mcp_json: str) -> dict:
    """
    :param mcp_json: MCP 포맷 문자열
    :return: 일정 JSON(dict) {day1: [...], day2: [...]} 등
    """
    cached = get_cache(f"iti::{hash(mcp_json)}")
    if cached:
        return cached

    sys_prompt = (
        "You are an expert rural job & travel planner. "
        "Return ONLY valid JSON with daily schedule array."
    )
    resp = client.chat.completions.create(
        model=settings.itinerary_model,
        messages=[{"role": "system", "content": sys_prompt},
                  {"role": "user", "content": mcp_json}],
        temperature=0.2,
        max_tokens=1024
    )
    schedule_json = resp.choices[0].message.content
    set_cache(f"iti::{hash(mcp_json)}", schedule_json)
    return schedule_json
