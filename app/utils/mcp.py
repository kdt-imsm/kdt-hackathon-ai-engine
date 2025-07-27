"""
mcp.py
~~~~~~
선택 콘텐츠 + 슬롯 + 예산 → MCP(Model Context Protocol) 포맷 빌더.
"""

import json
from datetime import datetime

def build_mcp(slots, selections, budget: int | None = None) -> str:
    """
    :param slots: UserSlots
    :param selections: 추천된 콘텐츠 중 사용자가 선택한 list[dict]
    :return: str (MCP JSON 문자열)
    """
    payload = {
        "meta": {
            "generated_at": datetime.utcnow().isoformat(),
            "version": "1.0"
        },
        "slots": slots.model_dump(),
        "selections": selections,
        "constraints": {
            "budget": budget
        }
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
