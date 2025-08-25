#!/usr/bin/env python3
"""
scripts/bulk_keyword_processor.py
==================================

전체 tour_api.csv 데이터에 대한 빠른 키워드 처리 스크립트

패턴 기반 키워드 추출과 지명 분석을 통해 API 호출 없이도
의미있는 키워드를 대량 생성합니다.

사용법:
python -m scripts.bulk_keyword_processor
"""

import pandas as pd
import re
from pathlib import Path
from typing import List, Set
import json

class BulkKeywordProcessor:
    def __init__(self):
        # 지역별 특징 키워드
        self.region_keywords = {
            '제주': ['화산', '돌담', '오름', '바람', '감귤', '한라산'],
            '부산': ['바다', '해변', '항구', '수영', '해운대', '광안리'],
            '경남': ['바다', '해안', '산', '역사', '전통'],
            '전남': ['갯벌', '바다', '섬', '해안', '전통', '자연'],
            '강원': ['산', '설악산', '스키', '온천', '계곡', '자연'],
            '경북': ['산', '사찰', '역사', '문화', '경주', '전통'],
            '충북': ['호수', '산', '온천', '자연', '휴양'],
            '충남': ['바다', '온천', '역사', '문화', '자연'],
            '전북': ['자연', '산', '전통', '문화', '음식'],
            '경기': ['자연', '공원', '문화', '역사', '휴양'],
            '서울': ['문화', '역사', '공원', '도심', '한강'],
            '인천': ['바다', '공항', '섬', '해안', '국제'],
            '대구': ['문화', '역사', '도심', '산'],
            '대전': ['과학', '문화', '도심', '공원'],
            '울산': ['공업', '바다', '해안', '현대'],
            '광주': ['문화', '예술', '역사', '무등산'],
            '세종': ['도시', '공원', '현대', '계획도시']
        }
        
        # 관광지 유형별 키워드 매핑
        self.attraction_patterns = {
            # 자연 관광지
            '해수욕장|해변|비치': ['바다', '해변', '물놀이', '여름', '해수욕', '모래'],
            '온천|스파': ['온천', '힐링', '휴양', '치유', '온수'],
            '계곡': ['계곡', '물', '자연', '여름', '피서', '청량'],
            '폭포': ['폭포', '자연', '물', '경관', '시원함'],
            '산|봉': ['산', '등산', '하이킹', '자연', '운동', '경치'],
            '호수|저수지': ['호수', '물', '자연', '휴식', '경관'],
            '공원': ['공원', '자연', '산책', '휴식', '녹지', '운동'],
            '수목원|식물원': ['식물', '자연', '교육', '산책', '힐링'],
            '갯벌': ['갯벌', '조개', '바다', '생태', '체험'],
            
            # 문화/역사 관광지
            '사찰|절': ['사찰', '불교', '문화', '역사', '전통', '종교'],
            '박물관': ['박물관', '문화', '교육', '역사', '전시'],
            '미술관': ['미술관', '예술', '문화', '전시', '작품'],
            '궁|궁궐': ['궁궐', '역사', '조선', '문화재', '전통'],
            '성|성곽': ['성', '역사', '문화재', '전통', '방어'],
            '서원|향교': ['서원', '교육', '유교', '역사', '전통'],
            '유적지|유적': ['유적', '역사', '고고학', '문화재', '발굴'],
            '문화재': ['문화재', '역사', '전통', '보존', '문화'],
            '전통마을|한옥마을': ['전통마을', '한옥', '문화', '역사', '전통'],
            '벽화마을': ['벽화', '마을', '예술', '문화', '체험'],
            
            # 레저/체험 관광지
            '스키장': ['스키', '겨울스포츠', '눈', '레저', '스노보드'],
            '골프장': ['골프', '레저', '스포츠', '운동', '여가'],
            '놀이공원|테마파크': ['놀이공원', '가족', '재미', '엔터테인먼트', '체험'],
            '동물원': ['동물원', '동물', '가족', '교육', '체험'],
            '수족관': ['수족관', '바다생물', '교육', '체험', '가족'],
            '체험장|체험': ['체험', '교육', '활동', '참여', '학습'],
            
            # 특수 관광지
            '전망대|조망': ['전망대', '경치', '조망', '풍경', '경관'],
            '등대': ['등대', '바다', '해안', '항해', '역사'],
            '다리|교': ['다리', '건축', '경관', '도시', '교통'],
            '시장': ['시장', '음식', '쇼핑', '전통', '문화'],
            '터미널|역': ['교통', '여행', '출발점', '연결'],
        }
    
    def extract_region_short_name(self, region: str) -> str:
        """지역명에서 핵심 키워드 추출"""
        # 광역시/도 패턴 제거하고 핵심 지명만 추출
        region_clean = re.sub(r'(특별시|광역시|특별자치시|특별자치도|도)$', '', region.strip())
        
        # 주요 지역별 매핑
        region_mapping = {
            '서울': '서울',
            '부산': '부산', 
            '대구': '대구',
            '인천': '인천',
            '광주': '광주',
            '대전': '대전',
            '울산': '울산',
            '세종': '세종',
            '경기': '경기',
            '강원': '강원',
            '충북': '충북',
            '충남': '충남',
            '전북': '전북',
            '전남': '전남',
            '경북': '경북',
            '경남': '경남',
            '제주': '제주'
        }
        
        for full_name, short_name in region_mapping.items():
            if full_name in region_clean:
                return short_name
        
        return region_clean[:2]  # 처음 2글자 반환
    
    def extract_attraction_keywords(self, name: str) -> List[str]:
        """관광지명에서 패턴 기반 키워드 추출"""
        keywords = []
        name_lower = name.lower()
        
        for pattern, pattern_keywords in self.attraction_patterns.items():
            if re.search(pattern, name):
                keywords.extend(pattern_keywords)
        
        # 관광지명에서 직접적인 키워드 추출
        name_keywords = self._extract_direct_keywords(name)
        keywords.extend(name_keywords)
        
        # 중복 제거 및 정렬
        unique_keywords = list(dict.fromkeys(keywords))
        return unique_keywords[:12]  # 최대 12개
    
    def _extract_direct_keywords(self, name: str) -> List[str]:
        """관광지명에서 직접적인 명사 키워드 추출"""
        keywords = []
        
        # 자주 나오는 관광 관련 단어들
        tourism_words = [
            '바다', '산', '강', '호수', '계곡', '폭포', '온천', '해변', '섬',
            '공원', '숲', '정원', '해안', '갯벌', '동굴', '봉우리', '고개',
            '사찰', '절', '궁', '성', '탑', '문', '다리', '건물', '집',
            '박물관', '미술관', '전시관', '체험관', '문화원', '회관',
            '마을', '도시', '거리', '광장', '시장', '터미널', '역',
            '축제', '행사', '공연', '전시', '체험', '투어', '코스'
        ]
        
        for word in tourism_words:
            if word in name:
                keywords.append(word)
        
        return keywords
    
    def process_bulk_keywords(self, input_file: str, output_file: str):
        """전체 데이터에 대한 벌크 키워드 처리"""
        print(f"📁 {input_file} 파일 로딩 중...")
        df = pd.read_csv(input_file)
        
        print(f"총 {len(df)}개의 관광지 데이터 처리 시작")
        
        # keywords 컬럼 추가
        if 'keywords' not in df.columns:
            df['keywords'] = ''
        
        processed = 0
        for idx, row in df.iterrows():
            name = row['name']
            region = row['region']
            tags = row.get('tags', '관광')
            
            # 1. 관광지명 패턴 기반 키워드 추출
            attraction_keywords = self.extract_attraction_keywords(name)
            
            # 2. 지역 기반 키워드 추가
            region_short = self.extract_region_short_name(region)
            region_keywords = self.region_keywords.get(region_short, ['자연', '여행'])
            
            # 3. 기존 태그 분해
            tag_keywords = [tag.strip() for tag in tags.split(',') if tag.strip()]
            
            # 4. 모든 키워드 결합
            all_keywords = attraction_keywords + region_keywords[:3] + tag_keywords
            
            # 5. 중복 제거 및 정리
            unique_keywords = list(dict.fromkeys(all_keywords))
            final_keywords = [kw for kw in unique_keywords if len(kw) >= 2][:15]
            
            # 6. DataFrame 업데이트
            df.at[idx, 'keywords'] = ','.join(final_keywords)
            processed += 1
            
            # 진행상황 출력
            if processed % 1000 == 0:
                print(f"🔄 {processed:,}/{len(df):,} 처리 완료 ({processed/len(df)*100:.1f}%)")
        
        # 결과 저장
        print(f"💾 결과를 {output_file}에 저장 중...")
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print(f"✅ 벌크 키워드 처리 완료!")
        print(f"   - 처리된 관광지: {len(df):,}개")
        print(f"   - 출력 파일: {output_file}")
        
        # 샘플 결과 출력
        print("\n📋 처리 결과 샘플:")
        for i in range(min(5, len(df))):
            row = df.iloc[i]
            print(f"  {i+1}. {row['name']} ({row['region']})")
            print(f"     키워드: {row['keywords']}")
            print()

def main():
    processor = BulkKeywordProcessor()
    
    # 전체 데이터 처리
    processor.process_bulk_keywords(
        input_file="data/tour_api.csv",
        output_file="data/tour_api_with_keywords.csv"
    )

if __name__ == "__main__":
    main()