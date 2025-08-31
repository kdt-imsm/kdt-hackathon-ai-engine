"""
app/utils/keyword_search.py
==========================
한국관광공사 TourAPI searchKeyword2 엔드포인트 호출 및 결과 처리 서비스
"""

from __future__ import annotations
import httpx
import time
from typing import List, Dict, Set
from dataclasses import dataclass

from app.config import get_settings


@dataclass
class KeywordSearchResult:
    """키워드 검색 결과 데이터 클래스"""
    contentid: str
    title: str
    keywords: List[str]  # 검색된 키워드들
    relevance_score: float = 1.0


class KeywordSearchService:
    """한국관광공사 TourAPI 키워드 검색 서비스"""
    
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.tour_base_url.rstrip("/")
        self.service_key = settings.tour_api_key
        self.client = httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            verify=False  # SSL 검증 비활성화로 SSL 에러 해결
        )
    
    def search_by_keyword(self, keyword: str, max_results: int = 50) -> List[KeywordSearchResult]:
        """단일 키워드로 관광지 검색"""
        params = {
            "serviceKey": self.service_key,
            "MobileOS": "ETC",
            "MobileApp": "ruralplanner",
            "keyword": keyword,
            "pageNo": 1,
            "numOfRows": min(max_results, 100),  # API 최대 100개
            "_type": "json"
        }
        
        url = f"{self.base_url}/searchKeyword2"
        
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            body = data["response"]["body"]
            
            items_field = body.get("items")
            if not items_field:
                return []
                
            if isinstance(items_field, dict):
                raw_items = items_field.get("item", [])
                items = raw_items if isinstance(raw_items, list) else [raw_items]
            elif isinstance(items_field, list):
                items = items_field
            else:
                return []
            
            results = []
            for item in items:
                if item.get("contentid") and item.get("title"):
                    results.append(KeywordSearchResult(
                        contentid=str(item["contentid"]),
                        title=item["title"],
                        keywords=[keyword]
                    ))
            
            return results
            
        except Exception as e:
            print(f"⚠️ 키워드 검색 실패 (keyword: {keyword}): {e}")
            return []
    
    def search_multiple_keywords(self, keywords: List[str], max_per_keyword: int = 30) -> Dict[str, List[KeywordSearchResult]]:
        """다중 키워드 검색 (API 호출 제한 고려하여 간격 조절)"""
        results = {}
        
        for i, keyword in enumerate(keywords):
            print(f"🔍 키워드 검색 진행: {keyword} ({i+1}/{len(keywords)})")
            results[keyword] = self.search_by_keyword(keyword, max_per_keyword)
            
            # API 호출 간격 조절 (과부하 방지)
            if i < len(keywords) - 1:
                time.sleep(0.2)
        
        return results
    
    def extract_contentids_by_keywords(self, keywords: List[str]) -> Dict[str, Set[str]]:
        """키워드별로 매칭되는 contentid 집합 반환"""
        search_results = self.search_multiple_keywords(keywords)
        
        contentid_mapping = {}
        for keyword, results in search_results.items():
            contentid_mapping[keyword] = {r.contentid for r in results}
        
        return contentid_mapping
    
    def find_keywords_for_contentid(self, contentid: str, candidate_keywords: List[str]) -> List[str]:
        """특정 contentid에 매칭되는 키워드들 찾기"""
        matched_keywords = []
        
        for keyword in candidate_keywords:
            results = self.search_by_keyword(keyword, max_results=100)
            if any(r.contentid == contentid for r in results):
                matched_keywords.append(keyword)
            time.sleep(0.1)  # API 호출 간격
        
        return matched_keywords
    
    def __del__(self):
        """리소스 정리"""
        if hasattr(self, 'client'):
            self.client.close()


# 전역 인스턴스 (싱글턴 패턴)
_keyword_service = None

def get_keyword_service() -> KeywordSearchService:
    """키워드 검색 서비스 싱글턴 인스턴스 반환"""
    global _keyword_service
    if _keyword_service is None:
        _keyword_service = KeywordSearchService()
    return _keyword_service