#!/usr/bin/env python3
"""
지역별 추천 품질 테스트
"""

import subprocess
import json

def run_slots_test(query):
    """슬롯 API 테스트"""
    cmd = [
        'curl', '-X', 'POST', 'http://localhost:8000/slots',
        '-H', 'Content-Type: application/json',
        '-d', json.dumps({"query": query}),
        '--silent', '--max-time', '30'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return {"error": f"API 오류: {result.stderr}"}
    except Exception as e:
        return {"error": str(e)}

def analyze_regional_match(response, expected_region):
    """지역 매칭 분석"""
    if "error" in response:
        return {"error": response["error"]}
    
    slots = response.get("slots", {})
    jobs = response.get("jobs_preview", [])
    tours = response.get("tours_preview", [])
    
    # 슬롯에서 추출된 지역
    extracted_regions = slots.get("region_pref", [])
    
    # 지역 키워드 매칭
    region_keywords = {
        "제주": ["제주", "서귀포", "감귤", "귤", "한라산"],
        "강원": ["강원", "평창", "춘천", "강릉", "속초", "감자"],
        "전북": ["전북", "전라북도", "고창", "전주", "정읍"],
        "경남": ["경남", "경상남도", "창원", "부산", "김해"],
        "충북": ["충북", "충청북도", "청주", "제천"]
    }
    
    keywords = region_keywords.get(expected_region, [expected_region])
    
    # 지역 매칭 점수 계산
    region_match_score = 0
    job_matches = 0
    tour_matches = 0
    
    # 슬롯 지역 매칭
    for region in extracted_regions:
        if any(keyword in region for keyword in keywords):
            region_match_score += 1
    
    # 일거리 지역 추정 (태그 기반)
    for job in jobs:
        job_text = f"{job.get('farm_name', '')} {' '.join(job.get('tags', []))}"
        if any(keyword in job_text for keyword in keywords):
            job_matches += 1
    
    # 관광지 지역 추정
    for tour in tours:
        tour_text = f"{tour.get('title', '')} {tour.get('overview', '')}"
        if any(keyword in tour_text for keyword in keywords):
            tour_matches += 1
    
    return {
        "슬롯_지역": extracted_regions,
        "활동_태그": slots.get("activity_tags", []),
        "지역_매칭_점수": region_match_score,
        "일거리_지역_매칭": job_matches,
        "관광지_지역_매칭": tour_matches,
        "일거리_매칭_비율": job_matches / len(jobs) if jobs else 0,
        "관광지_매칭_비율": tour_matches / len(tours) if tours else 0,
        "일거리_샘플": jobs[:3],
        "관광지_샘플": tours[:3]
    }

def regional_test():
    print("🗺️ 지역별 추천 품질 테스트")
    print("=" * 60)
    
    test_cases = [
        ("제주도에서 귤따기 체험하고 해변 관광하고 싶어요", "제주"),
        ("강원도 평창에서 감자캐기 하고 휴양림도 가고 싶어요", "강원"),
        ("경남 창원 근처에서 스마트팜 체험하고 싶어요", "경남"),
        ("충북에서 조용한 농촌 체험하고 싶어요", "충북")
    ]
    
    results = []
    
    for i, (query, expected_region) in enumerate(test_cases, 1):
        print(f"\n📝 테스트 {i}: {expected_region} 지역")
        print(f"   쿼리: {query}")
        print("   처리 중...")
        
        response = run_slots_test(query)
        analysis = analyze_regional_match(response, expected_region)
        
        if "error" not in analysis:
            print(f"   ✅ 성공")
            print(f"   📍 추출 지역: {analysis['슬롯_지역']}")
            print(f"   🎯 활동 태그: {analysis['활동_태그']}")
            print(f"   📊 일거리 매칭: {analysis['일거리_지역_매칭']}/10 ({analysis['일거리_매칭_비율']:.1%})")
            print(f"   📊 관광지 매칭: {analysis['관광지_지역_매칭']}/10 ({analysis['관광지_매칭_비율']:.1%})")
            
            # 샘플 출력
            print("   💼 일거리 샘플:")
            for j, job in enumerate(analysis['일거리_샘플'], 1):
                print(f"      {j}. {job['farm_name']}")
            
            print("   🏞️ 관광지 샘플:")
            for j, tour in enumerate(analysis['관광지_샘플'], 1):
                print(f"      {j}. {tour['title']}")
                
        else:
            print(f"   ❌ 실패: {analysis['error']}")
        
        results.append((expected_region, analysis))
    
    # 전체 결과 분석
    print(f"\n📊 지역별 테스트 종합 결과")
    print("-" * 40)
    
    successful_tests = [r for r in results if "error" not in r[1]]
    if successful_tests:
        avg_job_ratio = sum(r[1]['일거리_매칭_비율'] for r in successful_tests) / len(successful_tests)
        avg_tour_ratio = sum(r[1]['관광지_매칭_비율'] for r in successful_tests) / len(successful_tests)
        
        print(f"성공률: {len(successful_tests)}/{len(results)} ({len(successful_tests)/len(results):.1%})")
        print(f"평균 일거리 지역 매칭: {avg_job_ratio:.1%}")
        print(f"평균 관광지 지역 매칭: {avg_tour_ratio:.1%}")
        
        # 품질 평가
        print(f"\n🎯 품질 평가:")
        if avg_job_ratio >= 0.5:
            print("✅ 일거리 지역 연동 우수")
        elif avg_job_ratio >= 0.3:
            print("⚠️ 일거리 지역 연동 보통")
        else:
            print("❌ 일거리 지역 연동 개선 필요")
            
        if avg_tour_ratio >= 0.5:
            print("✅ 관광지 지역 연동 우수")
        elif avg_tour_ratio >= 0.3:
            print("⚠️ 관광지 지역 연동 보통")
        else:
            print("❌ 관광지 지역 연동 개선 필요")
    else:
        print("❌ 모든 테스트 실패")

if __name__ == "__main__":
    regional_test()