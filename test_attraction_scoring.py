#!/usr/bin/env python3
"""
관광지 추천 로직 테스트 스크립트
"""

import json
import requests
from typing import Dict, List

def test_recommendation_api(natural_request: str, preferences: Dict, test_name: str):
    """추천 API 테스트"""
    print(f"\n{'='*60}")
    print(f"테스트: {test_name}")
    print(f"{'='*60}")
    print(f"자연어 요청: {natural_request}")
    print(f"선호도: {preferences}")
    
    url = "http://localhost:8000/recommendations"
    payload = {
        "natural_request": natural_request,
        "preferences": preferences
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("status") == "success":
            tour_spots = data.get("data", {}).get("tour_spots", [])
            scored_attractions = data.get("data", {}).get("scored_attractions", [])
            
            print(f"\n✅ 추천된 관광지 카드 (상위 5개):")
            for i, tour in enumerate(tour_spots, 1):
                print(f"   {i}. {tour['name']} ({tour['address']})")
            
            print(f"\n📊 스코어링된 관광지 (상위 10개):")
            for i, attr in enumerate(scored_attractions[:10], 1):
                score = attr.get('_score', 'N/A')
                travel_style = attr.get('travel_style_keywords', 'None')
                landscape = attr.get('landscape_keywords', 'None')
                print(f"   {i}. {attr['name']} - 점수: {score}")
                print(f"      travel_style: {travel_style}, landscape: {landscape}")
        else:
            print(f"❌ API 오류: {data.get('message', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ 요청 실패: {e}")

def main():
    # 테스트 1: travel_style과 landscape가 모두 일치하는 경우
    test_recommendation_api(
        "김제에서 10월에 3일간 여행하고 싶어요",
        {
            "travel_style_keywords": ["농촌 체험", "축제"],
            "landscape_keywords": ["산"],
            "job_type_keywords": ["수확"]
        },
        "테스트 1: 산 선호 + 농촌체험/축제"
    )
    
    # 테스트 2: landscape가 다른 경우 (바다 선호인데 김제는 평야/산 지역)
    test_recommendation_api(
        "김제에서 10월에 3일간 여행하고 싶어요",
        {
            "travel_style_keywords": ["농촌 체험", "축제"],
            "landscape_keywords": ["바다"],
            "job_type_keywords": ["수확"]
        },
        "테스트 2: 바다 선호 (김제와 불일치)"
    )
    
    # 테스트 3: travel_style만 있고 landscape 없는 경우
    test_recommendation_api(
        "김제에서 10월에 3일간 여행하고 싶어요",
        {
            "travel_style_keywords": ["농촌 체험", "역사 문화"],
            "landscape_keywords": [],
            "job_type_keywords": ["수확"]
        },
        "테스트 3: landscape 선호 없음"
    )
    
    # 테스트 4: 여러 travel_style 매칭
    test_recommendation_api(
        "김제에서 10월에 3일간 여행하고 싶어요",
        {
            "travel_style_keywords": ["농촌 체험", "역사 문화", "축제", "힐링"],
            "landscape_keywords": ["평야"],
            "job_type_keywords": ["수확"]
        },
        "테스트 4: 다양한 travel_style + 평야"
    )
    
    # 테스트 5: landscape가 없는 관광지들 테스트
    test_recommendation_api(
        "김제에서 10월에 3일간 여행하고 싶어요",
        {
            "travel_style_keywords": ["체험형"],
            "landscape_keywords": ["산"],
            "job_type_keywords": ["수확"]
        },
        "테스트 5: 산 선호 - landscape 없는 관광지 포함 확인"
    )

if __name__ == "__main__":
    main()