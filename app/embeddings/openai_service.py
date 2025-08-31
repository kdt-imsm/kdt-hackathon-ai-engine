"""
OpenAI 서비스 (단순화)
일정 생성 및 피드백 처리용
"""

from openai import OpenAI
from app.config import get_settings

class OpenAIService:
    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)