#!/usr/bin/env python3
"""
추천 시스템 일관성 테스트
"""

import subprocess
import json
import time
from datetime import datetime

def run_api_test(query):
    """API 테스트 실행 및 결과 파싱"""
    cmd = [
        'curl', '-X', 'POST', 'http://localhost:8000/slots',
        '-H', 'Content-Type: application/json',
        '-d', json.dumps({"query": query}),
        '--connect-timeout', '10',
        '--max-time', '30',
        '--silent'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return {"error": f"HTTP 오류: {result.stderr}"}
    except subprocess.TimeoutExpired:
        return {"error": "타임아웃"}
    except json.JSONDecodeError:
        return {"error": "JSON 파싱 오류"}
    except Exception as e:
        return {"error": str(e)}

def analyze_response(response):
    """응답 분석"""
    if "error" in response:
        return response
    
    slots = response.get("slots", {})
    jobs = response.get("jobs_preview", [])
    tours = response.get("tours_preview", [])
    
    # 지역 분석
    region_pref = slots.get("region_pref", [])
    job_regions = {}
    tour_regions = {}
    
    # 일거리 지역 분포 (실제로는 region 정보가 preview에 없으므로 추정)
    jeonbuk_keywords = ["전북", "전라북도", "고창", "정읍", "전주"]
    jeonbuk_jobs = 0
    jeonbuk_tours = 0
    
    for job in jobs:
        # 태그나 이름으로 지역 추정
        job_text = f"{job.get('farm_name', '')} {job.get('tags', [])}"
        if any(keyword in str(job_text) for keyword in jeonbuk_keywords):
            jeonbuk_jobs += 1
    
    for tour in tours:
        tour_text = f"{tour.get('title', '')} {tour.get('overview', '')}"
        if any(keyword in str(tour_text) for keyword in jeonbuk_keywords):
            jeonbuk_tours += 1
    
    return {
        "슬롯_지역": region_pref,
        "활동_태그": slots.get("activity_tags", []),
        "예산": slots.get("budget_krw", 0),
        "일거리_총개수": len(jobs),
        "관광지_총개수": len(tours),
        "전북관련_일거리": jeonbuk_jobs,
        "전북관련_관광지": jeonbuk_tours,
        "전북_일거리_비율": jeonbuk_jobs / len(jobs) if jobs else 0,
        "전북_관광지_비율": jeonbuk_tours / len(tours) if tours else 0
    }

def test_consistency():
    print("🧪 추천 시스템 일관성 테스트")
    print("=" * 60)
    
    query = "전북 고창에서 농업 체험하고 관광지도 구경하고 싶어요. 예산은 20만원 정도예요."
    print(f"테스트 쿼리: {query}")
    print()
    
    results = []
    
    for i in range(3):
        print(f"📝 테스트 {i+1}/3 실행 중...")
        start_time = time.time()
        
        response = run_api_test(query)
        analysis = analyze_response(response)
        
        end_time = time.time()
        response_time = end_time - start_time
        
        analysis["응답시간"] = round(response_time, 2)
        results.append(analysis)
        
        if "error" not in analysis:
            print(f"   ✅ 성공 - 응답시간: {response_time:.2f}초")
        else:
            print(f"   ❌ 실패: {analysis['error']}")
        
        time.sleep(1)  # 서버 부하 방지
    
    # 결과 분석
    print("\n📊 일관성 분석 결과")
    print("-" * 40)
    
    if all("error" not in result for result in results):
        # 슬롯 추출 일관성
        regions = [str(r["슬롯_지역"]) for r in results]
        activities = [str(r["활동_태그"]) for r in results]
        budgets = [r["예산"] for r in results]
        
        print(f"슬롯 지역: {regions}")
        print(f"슬롯 일관성: {'✅ 일관됨' if len(set(regions)) == 1 else '❌ 불일치'}")
        
        print(f"활동 태그: {activities}")
        print(f"활동 일관성: {'✅ 일관됨' if len(set(activities)) == 1 else '❌ 불일치'}")
        
        print(f"예산: {budgets}")
        print(f"예산 일관성: {'✅ 일관됨' if len(set(budgets)) == 1 else '❌ 불일치'}")
        
        # 추천 결과 일관성
        job_counts = [r["일거리_총개수"] for r in results]
        tour_counts = [r["관광지_총개수"] for r in results]
        jeonbuk_ratios = [r["전북_일거리_비율"] for r in results]
        
        print(f"\n일거리 개수: {job_counts}")
        print(f"관광지 개수: {tour_counts}")
        print(f"전북 일거리 비율: {[f'{r:.2f}' for r in jeonbuk_ratios]}")
        
        # 평균 성능 지표
        avg_response_time = sum(r["응답시간"] for r in results) / len(results)
        avg_jeonbuk_ratio = sum(jeonbuk_ratios) / len(jeonbuk_ratios)
        
        print(f"\n🎯 성능 지표")
        print(f"평균 응답시간: {avg_response_time:.2f}초")
        print(f"평균 지역 정확도: {avg_jeonbuk_ratio:.2%}")
        print(f"완성도: {len([r for r in results if r['일거리_총개수'] >= 10])}/3")
        
        # 결과 해석
        print(f"\n📋 결과 해석")
        if avg_jeonbuk_ratio >= 0.5:
            print("✅ 지역 연동 우수 (50% 이상)")
        else:
            print("⚠️ 지역 연동 개선 필요")
            
        if avg_response_time <= 10:
            print("✅ 응답 속도 양호")
        else:
            print("⚠️ 응답 속도 개선 필요")
            
    else:
        print("❌ 테스트 실패로 일관성 분석 불가")
        for i, result in enumerate(results):
            if "error" in result:
                print(f"   테스트 {i+1}: {result['error']}")

if __name__ == "__main__":
    test_consistency()