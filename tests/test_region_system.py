#!/usr/bin/env python3
"""
지역 기반 추천 시스템 테스트
"""

import requests
import json

# 테스트할 서버 URL
BASE_URL = "http://localhost:8000"

def test_region_recommendation():
    """전북 고창 지역 추천 테스트"""
    
    print("🧪 지역 기반 추천 시스템 테스트 시작")
    print("=" * 50)
    
    # 테스트 케이스 1: 전북 고창 지역 명시
    test_query = "전북 고창에서 농업 체험하고 관광지도 구경하고 싶어요. 예산은 20만원 정도예요."
    
    print(f"📝 테스트 쿼리: {test_query}")
    print("\n1️⃣ 슬롯 추출 및 미리보기 테스트...")
    
    # /slots 엔드포인트 테스트
    try:
        response = requests.post(
            f"{BASE_URL}/slots",
            json={"query": test_query},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ 슬롯 추출 성공!")
            print(f"   📍 추출된 지역: {data['slots']['region_pref']}")
            print(f"   🏷️ 활동 태그: {data['slots']['activity_tags']}")
            print(f"   💰 예산: {data['slots']['budget_krw']}")
            
            # 일거리 미리보기 분석
            jobs = data['jobs_preview']
            print(f"\n📊 일거리 미리보기 ({len(jobs)}개):")
            job_regions = {}
            for job in jobs[:5]:
                print(f"   • {job['farm_name']} - 태그: {job['tags']}")
            
            # 관광지 미리보기 분석
            tours = data['tours_preview']
            print(f"\n📊 관광지 미리보기 ({len(tours)}개):")
            for tour in tours[:5]:
                print(f"   • {tour['title']} - {tour['overview']}")
            
            print("\n2️⃣ 최종 추천 테스트...")
            
            # /recommend 엔드포인트 테스트
            recommend_response = requests.post(
                f"{BASE_URL}/recommend",
                json={
                    "query": test_query,
                    "budget": 200000,
                    "selected_jobs": [],
                    "selected_tours": []
                },
                timeout=30
            )
            
            if recommend_response.status_code == 200:
                itineraries = recommend_response.json()
                print(f"✅ 최종 추천 성공! ({len(itineraries)}개 일정)")
                
                for i, itinerary in enumerate(itineraries[:2], 1):
                    print(f"\n📅 일정 {i}:")
                    print(f"   📅 날짜: {itinerary['date']}")
                    print(f"   📋 활동: {len(itinerary['activities'])}개")
                    for activity in itinerary['activities'][:3]:
                        print(f"      • {activity['type']}: {activity['name']} (비용: {activity['cost']}원)")
                
                print("\n🎊 지역 기반 추천 시스템 테스트 완료!")
                return True
            else:
                print(f"❌ 최종 추천 실패: {recommend_response.status_code}")
                print(f"응답: {recommend_response.text}")
                return False
                
        else:
            print(f"❌ 슬롯 추출 실패: {response.status_code}")
            print(f"응답: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 네트워크 오류: {e}")
        return False
    except Exception as e:
        print(f"❌ 테스트 오류: {e}")
        return False

if __name__ == "__main__":
    test_region_recommendation()