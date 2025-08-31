#!/usr/bin/env python3
"""
전북 지역 관광 데이터 필터링 스크립트
System_Improvements.md 요구사항에 따라 전북 지역 데이터만 남기고 나머지 제거
"""

import pandas as pd
import os
from pathlib import Path

# 프로젝트 루트 디렉토리
PROJECT_ROOT = Path(__file__).parent.parent

def filter_jeonbuk_data():
    """전북 지역 관광 데이터만 필터링하여 저장"""
    
    data_dir = PROJECT_ROOT / "data"
    
    # TourAPI CSV 파일들
    tour_files = [
        "tour_api_attractions.csv",
        "tour_api_courses.csv", 
        "tour_api_cultural.csv",
        "tour_api_festivals.csv",
        "tour_api_leisure.csv",
        "tour_api_shopping.csv"
    ]
    
    total_before = 0
    total_after = 0
    
    for filename in tour_files:
        filepath = data_dir / filename
        
        if not filepath.exists():
            print(f"❌ 파일이 존재하지 않습니다: {filename}")
            continue
        
        print(f"\n🔍 처리 중: {filename}")
        
        # CSV 읽기
        df = pd.read_csv(filepath)
        before_count = len(df)
        total_before += before_count
        
        # 전북 지역만 필터링 (전북, 전라북도, 전북특별자치도 모두 포함)
        jeonbuk_df = df[
            df['region'].str.contains('전북|전라북도', na=False)
        ].copy()
        
        after_count = len(jeonbuk_df)
        total_after += after_count
        
        print(f"  • 전체: {before_count:,}개")
        print(f"  • 전북: {after_count:,}개")
        print(f"  • 제거: {before_count - after_count:,}개")
        
        # 필터링된 데이터 저장
        if after_count > 0:
            jeonbuk_df.to_csv(filepath, index=False)
            print(f"  ✅ 저장 완료")
        else:
            print(f"  ⚠️ 전북 데이터가 없습니다.")
    
    print(f"\n📊 전체 요약:")
    print(f"  • 전체 데이터: {total_before:,}개")
    print(f"  • 전북 데이터: {total_after:,}개") 
    print(f"  • 제거된 데이터: {total_before - total_after:,}개")
    print(f"  • 남은 비율: {(total_after/total_before)*100:.1f}%")

def check_jeonbuk_regions():
    """전북 지역별 데이터 분포 확인"""
    
    print("\n🗺️ 전북 지역별 관광지 분포:")
    
    data_dir = PROJECT_ROOT / "data"
    tour_files = [
        "tour_api_attractions.csv",
        "tour_api_courses.csv", 
        "tour_api_cultural.csv",
        "tour_api_festivals.csv",
        "tour_api_leisure.csv",
        "tour_api_shopping.csv"
    ]
    
    all_data = []
    
    for filename in tour_files:
        filepath = data_dir / filename
        if filepath.exists():
            df = pd.read_csv(filepath)
            df['file_type'] = filename.replace('tour_api_', '').replace('.csv', '')
            all_data.append(df)
    
    if not all_data:
        print("❌ 처리할 데이터가 없습니다.")
        return
    
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # 전북 지역별 카운트
    jeonbuk_data = combined_df[
        combined_df['region'].str.contains('전북|전라북도', na=False)
    ]
    
    print(f"\n전북 전체 관광지: {len(jeonbuk_data):,}개")
    
    # 각 파일별 개수
    by_type = jeonbuk_data.groupby('file_type').size().sort_values(ascending=False)
    print("\n📋 카테고리별 분포:")
    for category, count in by_type.items():
        print(f"  • {category}: {count:,}개")

if __name__ == "__main__":
    print("🌾 전북 관광 데이터 필터링 시작")
    print("=" * 50)
    
    # 전북 데이터만 필터링
    filter_jeonbuk_data()
    
    # 지역별 분포 확인
    check_jeonbuk_regions()
    
    print("\n✅ 필터링 완료!")
    print("\n📝 다음 단계:")
    print("  1. 이미지가 없는 관광지 데이터 제거")
    print("  2. 관광지로서 가치가 없는 데이터 수동 검토")
    print("  3. 데이터베이스 업데이트")