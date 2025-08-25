"""
scripts/collect_tour_keywords.py
=================================
tour_api.csv의 각 관광지에 대해 TourAPI를 통해 상세 키워드를 수집하고
CSV 파일에 keywords 컬럼을 추가하는 스크립트

사용법:
python -m scripts.collect_tour_keywords

기능:
1. tour_api.csv 파일을 읽어서 각 관광지의 contentid 추출
2. TourAPI detailCommon1 엔드포인트로 각 관광지의 상세 정보 조회
3. 조회된 정보에서 키워드 추출 (제목, 개요, 태그 등)
4. 추출된 키워드를 keywords 컬럼에 추가하여 CSV 파일 업데이트
"""

import pandas as pd
import httpx
import time
import json
from pathlib import Path
from typing import List, Dict, Optional
import re
from tqdm import tqdm
from app.config import get_settings


class TourKeywordCollector:
    """TourAPI를 통한 관광지 키워드 수집기"""
    
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.tour_base_url.rstrip("/")
        self.service_key = settings.tour_api_key
        self.client = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))
        self.rate_limit_delay = 0.1  # API 호출 간격 (초)
    
    def search_related_keywords(self, tour_name: str) -> List[str]:
        """관광지 이름을 키워드로 검색해서 관련 키워드들을 찾습니다."""
        params = {
            "serviceKey": self.service_key,
            "MobileOS": "ETC",
            "MobileApp": "ruralplanner", 
            "keyword": tour_name,
            "pageNo": 1,
            "numOfRows": 20,  # 더 많은 결과 요청
            "_type": "json"
        }
        
        url = f"{self.base_url}/searchKeyword2"
        
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            keywords = set()
            
            # API 응답 구조 확인
            if data.get("response", {}).get("header", {}).get("resultCode") == "0000":
                items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
                if not items:
                    return []
                    
                if not isinstance(items, list):
                    items = [items]
                
                for item in items[:5]:  # 상위 5개만 사용
                    # 제목에서 키워드 추출
                    title = item.get("title", "")
                    if title:
                        extracted = self._extract_meaningful_words(title)
                        keywords.update(extracted)
                    
                    # 주소에서 지역 정보 추출  
                    addr1 = item.get("addr1", "")
                    if addr1:
                        location_keywords = self._extract_location_keywords(addr1)
                        keywords.update(location_keywords)
            
            return list(keywords)
            
        except Exception as e:
            print(f"❌ '{tour_name}' 키워드 검색 실패: {e}")
            return []
    
    def _extract_location_keywords(self, address: str) -> List[str]:
        """주소에서 지역 관련 키워드를 추출합니다."""
        location_keywords = []
        
        # 지역명 추출 패턴
        location_patterns = [
            r'([가-힣]+시)',      # 도시명
            r'([가-힣]+구)',      # 구명
            r'([가-힣]+군)',      # 군명
            r'([가-힣]+동)',      # 동명
            r'([가-힣]+면)',      # 면명
            r'([가-힣]+리)',      # 리명
        ]
        
        for pattern in location_patterns:
            matches = re.findall(pattern, address)
            for match in matches:
                if len(match) >= 2:
                    location_keywords.append(match)
        
        return location_keywords
    
    def extract_keywords_from_tour_name(self, tour_name: str, region: str) -> List[str]:
        """관광지 이름과 지역 정보를 기반으로 키워드를 추출합니다."""
        keywords = []
        
        # 1. 관광지 이름에서 직접 키워드 추출
        name_keywords = self._extract_meaningful_words(tour_name)
        keywords.extend(name_keywords)
        
        # 2. 지역 정보에서 키워드 추출
        region_keywords = self._extract_location_keywords(region)
        keywords.extend(region_keywords)
        
        # 3. searchKeyword2 API로 관련 키워드 검색
        related_keywords = self.search_related_keywords(tour_name)
        keywords.extend(related_keywords)
        
        # 4. 관광지 이름 패턴 기반 키워드 추가
        pattern_keywords = self._extract_pattern_based_keywords(tour_name)
        keywords.extend(pattern_keywords)
        
        # 중복 제거 및 정리
        unique_keywords = list(dict.fromkeys(keywords))  # 순서 유지하면서 중복 제거
        return [k for k in unique_keywords if len(k) >= 2][:15]  # 최대 15개 키워드
    
    def _extract_pattern_based_keywords(self, tour_name: str) -> List[str]:
        """관광지 이름의 패턴을 기반으로 키워드를 추출합니다."""
        keywords = []
        
        # 관광지 유형별 패턴 매칭
        patterns = {
            "해수욕장": ["바다", "해변", "물놀이", "여름", "해수욕", "모래"],
            "온천": ["온천", "힐링", "휴양", "스파", "치유"],
            "박물관": ["문화", "교육", "전시", "학습", "역사"],
            "공원": ["자연", "산책", "휴식", "녹지", "운동"],
            "사찰": ["불교", "문화재", "역사", "전통", "문화"],
            "등대": ["바다", "항해", "등대", "해안", "관광"],
            "폭포": ["자연", "물", "계곡", "시원", "여름"],
            "산": ["등산", "자연", "산행", "트레킹", "경치"],
            "섬": ["바다", "자연", "섬", "여행", "힐링"],
            "체험": ["체험", "교육", "활동", "참여", "학습"],
            "마을": ["전통", "문화", "마을", "체험", "농촌"],
            "전망대": ["경치", "전망", "관광", "풍경", "경관"]
        }
        
        tour_name_lower = tour_name.lower()
        for pattern, pattern_keywords in patterns.items():
            if pattern in tour_name_lower:
                keywords.extend(pattern_keywords)
                
        return keywords
    
    def _extract_meaningful_words(self, text: str) -> List[str]:
        """텍스트에서 의미있는 단어들을 추출합니다."""
        if not text:
            return []
            
        # HTML 태그 제거
        text = re.sub(r'<[^>]+>', '', text)
        
        # 한글 단어 추출 (2글자 이상)
        korean_words = re.findall(r'[가-힣]{2,}', text)
        
        # 영문 단어 추출 (3글자 이상)
        english_words = re.findall(r'[A-Za-z]{3,}', text)
        
        # 불용어 제거
        stop_words = {
            "있습니다", "있다", "이다", "있는", "되어", "위해", "통해", "대한", "같은", 
            "많은", "다양한", "여러", "모든", "각종", "전체", "일반", "기본", "주요",
            "지역", "장소", "곳", "위치", "시설", "건물", "구조", "형태", "모습",
            "관광", "여행", "관람", "견학", "체험", "활동", "이용", "방문", "참여"
        }
        
        # 의미있는 키워드만 필터링
        meaningful_words = []
        for word in korean_words + english_words:
            if (len(word) >= 2 and 
                word not in stop_words and
                not word.isdigit()):
                meaningful_words.append(word)
        
        return meaningful_words
    
    def collect_keywords_for_csv(self, csv_path: str, batch_size: int = 100):
        """CSV 파일의 모든 관광지에 대해 키워드를 수집하고 업데이트합니다."""
        
        # 1. CSV 파일 읽기
        df = pd.read_csv(csv_path)
        print(f"총 {len(df)}개의 관광지 데이터를 처리합니다.")
        
        # 2. keywords 컬럼이 없으면 추가
        if 'keywords' not in df.columns:
            df['keywords'] = ''
        
        # 3. 이미 키워드가 있는 항목은 건너뛰기
        needs_processing = df[df['keywords'].isna() | (df['keywords'] == '')].copy()
        print(f"🔄 키워드 수집이 필요한 관광지: {len(needs_processing)}개")
        
        if len(needs_processing) == 0:
            print("✅ 모든 관광지의 키워드가 이미 수집되었습니다.")
            return
        
        # 4. 배치별로 처리
        successful_updates = 0
        failed_updates = 0
        
        with tqdm(total=len(needs_processing), desc="키워드 수집 중") as pbar:
            for idx, row in needs_processing.iterrows():
                tour_name = row['name']
                region = row['region']
                
                try:
                    # 관광지 이름과 지역 정보로 키워드 추출
                    keywords = self.extract_keywords_from_tour_name(tour_name, region)
                    
                    if keywords and len(keywords) > 2:  # 최소 3개 이상의 키워드가 있어야 성공
                        # DataFrame 업데이트
                        df.at[idx, 'keywords'] = ','.join(keywords[:12])  # 최대 12개 키워드
                        successful_updates += 1
                    else:
                        # 키워드를 충분히 추출하지 못한 경우 기본 태그 + 패턴 키워드 사용
                        pattern_keywords = self._extract_pattern_based_keywords(tour_name)
                        combined_keywords = row.get('tags', '관광').split(',') + pattern_keywords
                        df.at[idx, 'keywords'] = ','.join(combined_keywords[:8])
                        failed_updates += 1
                        
                except Exception as e:
                    print(f"❌ '{tour_name}' 키워드 추출 중 오류: {e}")
                    # 오류 발생 시 기본 태그 + 패턴 기반 키워드 사용
                    pattern_keywords = self._extract_pattern_based_keywords(tour_name)
                    basic_tags = row.get('tags', '관광').split(',')
                    combined_keywords = basic_tags + pattern_keywords
                    df.at[idx, 'keywords'] = ','.join(combined_keywords[:6])
                    failed_updates += 1
                
                # API 호출 제한 준수
                time.sleep(self.rate_limit_delay)
                
                pbar.update(1)
                
                # 주기적으로 저장 (100개마다)
                if (successful_updates + failed_updates) % batch_size == 0:
                    df.to_csv(csv_path, index=False)
                    print(f"\n💾 중간 저장 완료: 성공 {successful_updates}개, 실패 {failed_updates}개")
        
        # 5. 최종 저장
        df.to_csv(csv_path, index=False)
        print(f"\n✅ 키워드 수집 완료!")
        print(f"   📈 성공: {successful_updates}개")
        print(f"   ⚠️ 실패: {failed_updates}개")
        print(f"   💾 파일 저장됨: {csv_path}")


def main():
    """메인 실행 함수"""
    csv_path = "data/tour_api.csv"
    
    if not Path(csv_path).exists():
        print(f"❌ {csv_path} 파일을 찾을 수 없습니다.")
        return
    
    collector = TourKeywordCollector()
    collector.collect_keywords_for_csv(csv_path)


if __name__ == "__main__":
    main()