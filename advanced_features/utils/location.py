"""
app/utils/location.py
=====================
지역명 정규화, 매칭 및 지리적 거리 계산 유틸리티

* 기능
  1. 한국 행정구역 체계를 고려한 지역명 매칭 로직
  2. Haversine 공식을 사용한 두 지점 간 거리 계산
  3. 지역명을 위도/경도 좌표로 변환
  4. 거리 기반 필터링 및 점수 계산
"""

import re
import math
from typing import List, Set, Tuple, Optional, Any


# 한국 주요 지역 좌표 데이터 (위도, 경도)
KOREA_LOCATIONS = {
    # 서울/경기
    "서울": (37.5665, 126.9780),
    "경기": (37.4138, 127.5183),
    "인천": (37.4563, 126.7052),
    "수원": (37.2636, 127.0286),
    "성남": (37.4449, 127.1388),
    "고양": (37.6584, 126.8320),
    
    # 강원도
    "강원": (37.8228, 128.1555),
    "춘천": (37.8813, 127.7298),
    "원주": (37.3422, 127.9202),
    "강릉": (37.7519, 128.8761),
    "속초": (38.2070, 128.5918),
    
    # 충청도
    "충북": (36.8, 127.7),
    "충남": (36.5, 126.8),
    "대전": (36.3504, 127.3845),
    "청주": (36.6424, 127.4890),
    "천안": (36.8151, 127.1139),
    "충주": (36.9910, 127.9259),
    
    # 전라도
    "전북": (35.7175, 127.153),
    "전남": (34.8679, 126.991),
    "광주": (35.1595, 126.8526),
    "전주": (35.8242, 127.1480),
    "군산": (35.9677, 126.7369),
    "익산": (35.9483, 126.9578),
    "고창": (35.4351, 126.7014),
    "순천": (34.9506, 127.4872),
    "여수": (34.7604, 127.6622),
    "목포": (34.8118, 126.3922),
    
    # 경상도
    "경북": (36.4919, 128.8889),
    "경남": (35.4606, 128.2132),
    "대구": (35.8714, 128.6014),
    "부산": (35.1796, 129.0756),
    "울산": (35.5384, 129.3114),
    "포항": (36.0190, 129.3435),
    "경주": (35.8562, 129.2247),
    "안동": (36.5684, 128.7294),
    "창원": (35.2281, 128.6811),
    "김해": (35.2342, 128.8890),
    "진주": (35.1800, 128.1076),
    
    # 제주도
    "제주": (33.4996, 126.5312),
    "서귀포": (33.2541, 126.5601),
    
    # 추가 지역 좌표 (새로 추가된 농가 데이터용)
    "김제": (35.8020, 126.8814),
    "예산": (36.6826, 126.8508),
    "논산": (36.1871, 127.0986),
    "홍성": (36.6015, 126.6612),
    "금산": (36.1089, 127.4876),
    "군위": (36.2426, 128.5716),
    "영천": (35.9734, 128.9386),
    "청도": (35.6477, 128.7356),
    "의성": (36.3528, 128.6997),
    "홍천": (37.6968, 127.8890),
    "횡성": (37.4937, 127.9829),
    "정선": (37.3805, 128.6606),
    "평창": (37.3702, 128.3230),
    "완도": (34.3105, 126.7550),
    "보성": (34.7718, 127.0799),
    "해남": (34.5734, 126.5991),
    "광양": (34.9407, 127.5956),
}


# 한국 시도명 매핑
REGION_MAPPING = {
    # 전체 형태 -> 약어
    "서울특별시": ["서울", "서울시"],
    "부산광역시": ["부산", "부산시"],
    "대구광역시": ["대구", "대구시"],
    "인천광역시": ["인천", "인천시"],
    "광주광역시": ["광주", "광주시"],
    "대전광역시": ["대전", "대전시"],
    "울산광역시": ["울산", "울산시"],
    "경기도": ["경기", "경기도"],
    "강원도": ["강원", "강원도"],
    "충청북도": ["충북", "충청북도"],
    "충청남도": ["충남", "충청남도"],
    "전라북도": ["전북", "전라북도"],
    "전라남도": ["전남", "전라남도"],
    "경상북도": ["경북", "경상북도"],
    "경상남도": ["경남", "경상남도"],
    "제주특별자치도": ["제주", "제주도"],
}

# 역매핑: 약어 -> 전체 형태
REVERSE_MAPPING = {}
for full_name, aliases in REGION_MAPPING.items():
    for alias in aliases:
        REVERSE_MAPPING[alias] = full_name
    REVERSE_MAPPING[full_name] = full_name

# 한국 주요 시/군/구 → 시도 매핑 (시/군 단위 지역명만으로도 인식하도록)
SIGUNGU_TO_SIDO_MAPPING = {
    # 서울특별시 (구 단위)
    "강남구": "서울", "강동구": "서울", "강북구": "서울", "강서구": "서울", 
    "관악구": "서울", "광진구": "서울", "구로구": "서울", "금천구": "서울",
    "노원구": "서울", "도봉구": "서울", "동대문구": "서울", "동작구": "서울",
    "마포구": "서울", "서대문구": "서울", "서초구": "서울", "성동구": "서울",
    "성북구": "서울", "송파구": "서울", "양천구": "서울", "영등포구": "서울",
    "용산구": "서울", "은평구": "서울", "종로구": "서울", "중구": "서울", "중랑구": "서울",
    
    # 경기도
    "수원시": "경기", "수원": "경기", "성남시": "경기", "성남": "경기",
    "고양시": "경기", "고양": "경기", "용인시": "경기", "용인": "경기",
    "부천시": "경기", "부천": "경기", "안산시": "경기", "안산": "경기",
    "안양시": "경기", "안양": "경기", "남양주시": "경기", "남양주": "경기",
    "화성시": "경기", "화성": "경기", "평택시": "경기", "평택": "경기",
    "의정부시": "경기", "의정부": "경기", "시흥시": "경기", "시흥": "경기",
    "파주시": "경기", "파주": "경기", "광명시": "경기", "광명": "경기",
    "김포시": "경기", "김포": "경기", "군포시": "경기", "군포": "경기",
    "광주시": "경기", "이천시": "경기", "이천": "경기", "양주시": "경기", "양주": "경기",
    "오산시": "경기", "오산": "경기", "구리시": "경기", "구리": "경기",
    "안성시": "경기", "안성": "경기", "포천시": "경기", "포천": "경기",
    "의왕시": "경기", "의왕": "경기", "하남시": "경기", "하남": "경기",
    "여주시": "경기", "여주": "경기", "양평군": "경기", "양평": "경기",
    "동두천시": "경기", "동두천": "경기", "과천시": "경기", "과천": "경기",
    "가평군": "경기", "가평": "경기", "연천군": "경기", "연천": "경기",
    
    # 인천광역시
    "중구": "인천", "동구": "인천", "미추홀구": "인천", "연수구": "인천",
    "남동구": "인천", "부평구": "인천", "계양구": "인천", "서구": "인천",
    "강화군": "인천", "강화": "인천", "옹진군": "인천", "옹진": "인천",
    
    # 강원특별자치도
    "춘천시": "강원", "춘천": "강원", "원주시": "강원", "원주": "강원",
    "강릉시": "강원", "강릉": "강원", "동해시": "강원", "동해": "강원",
    "태백시": "강원", "태백": "강원", "속초시": "강원", "속초": "강원",
    "삼척시": "강원", "삼척": "강원", "홍천군": "강원", "홍천": "강원",
    "횡성군": "강원", "횡성": "강원", "영월군": "강원", "영월": "강원",
    "평창군": "강원", "평창": "강원", "정선군": "강원", "정선": "강원",
    "철원군": "강원", "철원": "강원", "화천군": "강원", "화천": "강원",
    "양구군": "강원", "양구": "강원", "인제군": "강원", "인제": "강원",
    "고성군": "강원", "고성": "강원", "양양군": "강원", "양양": "강원",
    
    # 충청북도
    "청주시": "충북", "청주": "충북", "충주시": "충북", "충주": "충북",
    "제천시": "충북", "제천": "충북", "보은군": "충북", "보은": "충북",
    "옥천군": "충북", "옥천": "충북", "영동군": "충북", "영동": "충북",
    "증평군": "충북", "증평": "충북", "진천군": "충북", "진천": "충북",
    "괴산군": "충북", "괴산": "충북", "음성군": "충북", "음성": "충북",
    "단양군": "충북", "단양": "충북", # 사용자 예시 단양 추가
    
    # 충청남도
    "천안시": "충남", "천안": "충남", "공주시": "충남", "공주": "충남",
    "보령시": "충남", "보령": "충남", "아산시": "충남", "아산": "충남",
    "서산시": "충남", "서산": "충남", "논산시": "충남", "논산": "충남",
    "계룡시": "충남", "계룡": "충남", "당진시": "충남", "당진": "충남",
    "금산군": "충남", "금산": "충남", "부여군": "충남", "부여": "충남",
    "서천군": "충남", "서천": "충남", "청양군": "충남", "청양": "충남",
    "홍성군": "충남", "홍성": "충남", "예산군": "충남", "예산": "충남",
    "태안군": "충남", "태안": "충남",
    
    # 전라북도
    "전주시": "전북", "전주": "전북", "군산시": "전북", "군산": "전북",
    "익산시": "전북", "익산": "전북", "정읍시": "전북", "정읍": "전북",
    "남원시": "전북", "남원": "전북", "김제시": "전북", "김제": "전북",
    "완주군": "전북", "완주": "전북", "진안군": "전북", "진안": "전북",
    "무주군": "전북", "무주": "전북", "장수군": "전북", "장수": "전북",
    "임실군": "전북", "임실": "전북", "순창군": "전북", "순창": "전북",
    "고창군": "전북", "고창": "전북", "부안군": "전북", "부안": "전북",
    
    # 전라남도
    "목포시": "전남", "목포": "전남", "여수시": "전남", "여수": "전남",
    "순천시": "전남", "순천": "전남", "나주시": "전남", "나주": "전남",
    "광양시": "전남", "광양": "전남", "담양군": "전남", "담양": "전남",
    "곡성군": "전남", "곡성": "전남", "구례군": "전남", "구례": "전남",
    "고흥군": "전남", "고흥": "전남", "보성군": "전남", "보성": "전남",
    "화순군": "전남", "화순": "전남", "장흥군": "전남", "장흥": "전남",
    "강진군": "전남", "강진": "전남", "해남군": "전남", "해남": "전남",
    "영암군": "전남", "영암": "전남", "무안군": "전남", "무안": "전남",
    "함평군": "전남", "함평": "전남", "영광군": "전남", "영광": "전남",
    "장성군": "전남", "장성": "전남", "완도군": "전남", "완도": "전남",
    "진도군": "전남", "진도": "전남", "신안군": "전남", "신안": "전남",
    
    # 경상북도
    "포항시": "경북", "포항": "경북", "경주시": "경북", "경주": "경북",
    "김천시": "경북", "김천": "경북", "안동시": "경북", "안동": "경북",
    "구미시": "경북", "구미": "경북", "영주시": "경북", "영주": "경북",
    "영천시": "경북", "영천": "경북", "상주시": "경북", "상주": "경북",
    "문경시": "경북", "문경": "경북", "경산시": "경북", "경산": "경북",
    "군위군": "경북", "군위": "경북", "의성군": "경북", "의성": "경북",
    "청송군": "경북", "청송": "경북", "영양군": "경북", "영양": "경북",
    "영덕군": "경북", "영덕": "경북", "청도군": "경북", "청도": "경북",
    "고령군": "경북", "고령": "경북", "성주군": "경북", "성주": "경북",
    "칠곡군": "경북", "칠곡": "경북", "예천군": "경북", "예천": "경북",
    "봉화군": "경북", "봉화": "경북", "울진군": "경북", "울진": "경북",
    "울릉군": "경북", "울릉": "경북",
    
    # 경상남도
    "창원시": "경남", "창원": "경남", "진주시": "경남", "진주": "경남",
    "통영시": "경남", "통영": "경남", "사천시": "경남", "사천": "경남",
    "김해시": "경남", "김해": "경남", "밀양시": "경남", "밀양": "경남",
    "거제시": "경남", "거제": "경남", "양산시": "경남", "양산": "경남",
    "의령군": "경남", "의령": "경남", "함안군": "경남", "함안": "경남",
    "창녕군": "경남", "창녕": "경남", "고성군": "경남", "남해군": "경남", "남해": "경남",
    "하동군": "경남", "하동": "경남", "산청군": "경남", "산청": "경남",
    "함양군": "경남", "함양": "경남", "거창군": "경남", "거창": "경남",
    "합천군": "경남", "합천": "경남",
    
    # 대구광역시
    "중구": "대구", "동구": "대구", "서구": "대구", "남구": "대구",
    "북구": "대구", "수성구": "대구", "달서구": "대구", "달성군": "대구", "달성": "대구",
    
    # 부산광역시
    "중구": "부산", "서구": "부산", "동구": "부산", "영도구": "부산",
    "부산진구": "부산", "동래구": "부산", "남구": "부산", "북구": "부산",
    "해운대구": "부산", "사하구": "부산", "금정구": "부산", "강서구": "부산",
    "연제구": "부산", "수영구": "부산", "사상구": "부산", "기장군": "부산", "기장": "부산",
    
    # 울산광역시
    "중구": "울산", "남구": "울산", "동구": "울산", "북구": "울산",
    "울주군": "울산", "울주": "울산",
    
    # 광주광역시
    "동구": "광주", "서구": "광주", "남구": "광주", "북구": "광주", "광산구": "광주",
    
    # 대전광역시
    "동구": "대전", "중구": "대전", "서구": "대전", "유성구": "대전", "대덕구": "대전",
    
    # 제주특별자치도
    "제주시": "제주", "서귀포시": "제주", "서귀포": "제주",
}

# 강화된 지역명 정규화 매핑 테이블 - 모든 입력 변형 대응
COMPREHENSIVE_REGION_MAPPING = {
    # 충청도 매핑 강화 (사용자 핵심 요구사항)
    "충청도": ["충청북도", "충청남도", "충북", "충남", "대전", "세종", "충청", "청주", "대전", "천안", "충주"],
    "충청": ["충청도", "충청북도", "충청남도", "충북", "충남", "대전", "세종"],
    "충북": ["충청북도", "충청도", "충청", "청주", "충주", "제천", "단양", "음성", "진천", "괴산", "증평", "영동", "옥천", "보은"],
    "충청북도": ["충북", "충청도", "충청", "청주", "충주", "제천", "단양", "음성", "진천", "괴산", "증평", "영동", "옥천", "보은"],
    "충남": ["충청남도", "충청도", "충청", "천안", "공주", "보령", "아산", "서산", "논산", "계룡", "당진", "금산", "부여", "서천", "청양", "홍성", "예산", "태안"],
    "충청남도": ["충남", "충청도", "충청", "천안", "공주", "보령", "아산", "서산", "논산", "계룡", "당진", "금산", "부여", "서천", "청양", "홍성", "예산", "태안"],
    
    # 전라도 매핑 강화
    "전라도": ["전라북도", "전라남도", "전북", "전남", "광주", "전주", "군산", "익산", "목포", "여수", "순천"],
    "전라": ["전라도", "전라북도", "전라남도", "전북", "전남", "광주"],
    "전북": ["전라북도", "전북특별자치도", "전라도", "전라", "전주", "군산", "익산", "정읍", "남원", "김제", "김제시", "전북 김제시", "완주", "진안", "무주", "장수", "임실", "순창", "고창", "부안"],
    "전라북도": ["전북", "전북특별자치도", "전라도", "전라", "전주", "군산", "익산", "정읍", "남원", "김제", "완주", "진안", "무주", "장수", "임실", "순창", "고창", "부안"],
    "전북특별자치도": ["전북", "전라북도", "전라도", "전라", "전주", "군산", "익산", "정읍", "남원", "김제", "완주", "진안", "무주", "장수", "임실", "순창", "고창", "부안"],
    "전남": ["전라남도", "전라도", "전라", "목포", "여수", "순천", "나주", "광양", "담양", "곡성", "구례", "고흥", "보성", "화순", "장흥", "강진", "해남", "영암", "무안", "함평", "영광", "장성", "완도", "진도", "신안"],
    "전라남도": ["전남", "전라도", "전라", "목포", "여수", "순천", "나주", "광양", "담양", "곡성", "구례", "고흥", "보성", "화순", "장흥", "강진", "해남", "영암", "무안", "함평", "영광", "장성", "완도", "진도", "신안"],
    
    # 김제 특별 매핑 (농가 데이터 집중 지역)
    "김제": ["김제시", "전북 김제시", "전북", "전라북도", "전북특별자치도", "전라도", "전라", "전북 김제"],
    "김제시": ["김제", "전북 김제시", "전북", "전라북도", "전북특별자치도", "전라도", "전라", "전북 김제"],
    
    # 경상도 매핑 강화
    "경상도": ["경상북도", "경상남도", "경북", "경남", "대구", "부산", "울산", "포항", "경주", "안동", "창원", "진주"],
    "경상": ["경상도", "경상북도", "경상남도", "경북", "경남"],
    "경북": ["경상북도", "경상도", "경상", "포항", "경주", "김천", "안동", "구미", "영주", "영천", "상주", "문경", "경산"],
    "경상북도": ["경북", "경상도", "경상", "포항", "경주", "김천", "안동", "구미", "영주", "영천", "상주", "문경", "경산"],
    "경남": ["경상남도", "경상도", "경상", "창원", "진주", "통영", "사천", "김해", "밀양", "거제", "양산"],
    "경상남도": ["경남", "경상도", "경상", "창원", "진주", "통영", "사천", "김해", "밀양", "거제", "양산"],
    
    # 제주도 매핑 강화
    "제주도": ["제주", "제주특별자치도", "제주시", "서귀포", "제주 제주", "제주 서귀포"],
    "제주": ["제주도", "제주특별자치도", "제주시", "서귀포", "제주 제주", "제주 서귀포"],
    "제주특별자치도": ["제주", "제주도", "제주시", "서귀포", "제주 제주", "제주 서귀포"],
    "서귀포": ["제주", "제주도", "제주특별자치도", "제주 서귀포"],
    
    # 강원도 매핑 강화
    "강원도": ["강원", "강원특별자치도", "춘천", "원주", "강릉", "속초", "평창", "홍천", "횡성", "정선", "영월", "태백", "삼척", "동해"],
    "강원": ["강원도", "강원특별자치도", "춘천", "원주", "강릉", "속초", "평창", "홍천", "횡성", "정선", "영월", "태백", "삼척", "동해"],
    "강원특별자치도": ["강원", "강원도", "춘천", "원주", "강릉", "속초", "평창", "홍천", "횡성", "정선", "영월", "태백", "삼척", "동해"],
    
    # 경기도 매핑 강화
    "경기도": ["경기", "수원", "성남", "고양", "용인", "부천", "안산", "안양", "남양주", "화성", "평택", "의정부", "시흥", "파주", "광명", "김포", "군포", "이천", "양주", "오산", "구리", "안성", "포천", "의왕", "하남", "여주", "양평", "동두천", "과천", "가평", "연천"],
    "경기": ["경기도", "수원", "성남", "고양", "용인", "부천", "안산", "안양", "남양주", "화성", "평택", "의정부", "시흥", "파주", "광명", "김포", "군포", "이천", "양주", "오산", "구리", "안성", "포천", "의왕", "하남", "여주", "양평", "동두천", "과천", "가평", "연천"],
    
    # 주요 광역시 매핑
    "서울": ["서울특별시", "서울시"],
    "서울특별시": ["서울", "서울시"], 
    "서울시": ["서울", "서울특별시"],
    "부산": ["부산광역시", "부산시"],
    "부산광역시": ["부산", "부산시"],
    "부산시": ["부산", "부산광역시"],
    "대구": ["대구광역시", "대구시"],
    "대구광역시": ["대구", "대구시"],
    "대구시": ["대구", "대구광역시"],
    "인천": ["인천광역시", "인천시"],
    "인천광역시": ["인천", "인천시"],
    "인천시": ["인천", "인천광역시"],
    "광주": ["광주광역시", "광주시"],
    "광주광역시": ["광주", "광주시"],
    "광주시": ["광주", "광주광역시"],
    "대전": ["대전광역시", "대전시"],
    "대전광역시": ["대전", "대전시"],
    "대전시": ["대전", "대전광역시"],
    "울산": ["울산광역시", "울산시"],
    "울산광역시": ["울산", "울산시"],
    "울산시": ["울산", "울산광역시"],
    "세종": ["세종특별자치시", "세종시"],
    "세종특별자치시": ["세종", "세종시"],
    "세종시": ["세종", "세종특별자치시"],
    
    # 전라북도 매핑 강화
    "전북": ["전라북도", "전북특별자치도", "전북 전주", "전북 군산", "전북 익산", "전북 고창", "전북 김제", "전북 남원", "전북 정읍", "전북 부안", "전북 무주", "전주", "군산", "익산", "고창", "김제", "남원", "정읍", "부안", "무주"],
    "전라북도": ["전북", "전북특별자치도", "전북 전주", "전북 군산", "전북 익산", "전북 고창", "전북 김제", "전북 남원", "전북 정읍", "전북 부안", "전북 무주", "전주", "군산", "익산", "고창", "김제", "남원", "정읍", "부안", "무주"],
    "전북특별자치도": ["전북", "전라북도", "전북 전주", "전북 군산", "전북 익산", "전북 고창", "전북 김제", "전북 남원", "전북 정읍", "전북 부안", "전북 무주", "전주", "군산", "익산", "고창", "김제", "남원", "정읍", "부안", "무주"],
    "전주": ["전북", "전라북도", "전북특별자치도", "전북 전주"],
    "군산": ["전북", "전라북도", "전북특별자치도", "전북 군산"],
    "익산": ["전북", "전라북도", "전북특별자치도", "전북 익산"],
    "고창": ["전북", "전라북도", "전북특별자치도", "전북 고창"],
    "남원": ["전북", "전라북도", "전북특별자치도", "전북 남원"],
    "무주": ["전북", "전라북도", "전북특별자치도", "전북 무주"],
    
    # 기타 시도 매핑 강화
    "경기도": ["경기", "경기 수원", "경기 성남", "경기 고양", "경기 가평", "경기 안성", "수원", "성남", "고양", "안성", "가평"],
    "경기": ["경기도", "경기 수원", "경기 성남", "경기 고양", "경기 가평", "경기 안성", "수원", "성남", "고양", "안성", "가평"],
    "수원": ["경기", "경기도", "경기 수원"],
    "성남": ["경기", "경기도", "경기 성남"],
    "고양": ["경기", "경기도", "경기 고양"],
    "안성": ["경기", "경기도", "경기 안성"],
    "가평": ["경기", "경기도", "경기 가평"],
    
    "충남": ["충청남도", "충남 논산", "충남 천안", "충남 서산", "논산", "천안", "서산"],
    "충청남도": ["충남", "충남 논산", "충남 천안", "충남 서산", "논산", "천안", "서산"],
    "논산": ["충남", "충청남도", "충남 논산"],
    "천안": ["충남", "충청남도", "충남 천안"],
    "서산": ["충남", "충청남도", "충남 서산"],
    
    "전남": ["전라남도", "전남 담양", "전남 장성", "전남 나주", "전남 무안", "담양", "장성", "나주", "무안"],
    "전라남도": ["전남", "전남 담양", "전남 장성", "전남 나주", "전남 무안", "담양", "장성", "나주", "무안"],
    "나주": ["전남", "전라남도", "전남 나주"],
    "무안": ["전남", "전라남도", "전남 무안"],
    
    "경북": ["경상북도", "경북 경산", "경북 안동", "경북 경주", "경북 영천", "안동", "경주", "경산", "영천"],
    "경상북도": ["경북", "경북 경산", "경북 안동", "경북 경주", "경북 영천", "안동", "경주", "경산", "영천"],
    "안동": ["경북", "경상북도", "경북 안동"],
    "경주": ["경북", "경상북도", "경북 경주"],
    "영천": ["경북", "경상북도", "경북 영천"],
    
    "경남": ["경상남도", "경남 창원", "경남 밀양", "창원", "밀양"],
    "경상남도": ["경남", "경남 창원", "경남 밀양", "창원", "밀양"],
    "창원": ["경남", "경상남도", "경남 창원"],
    "밀양": ["경남", "경상남도", "경남 밀양"],
    
    "부산": ["부산광역시", "부산시", "부산 연제구", "부산 강서구"],
    "부산광역시": ["부산", "부산시", "부산 연제구", "부산 강서구"],
    "인천": ["인천광역시", "인천시", "인천 서구"],
    "인천광역시": ["인천", "인천시", "인천 서구"],
}


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Haversine 공식을 사용하여 두 좌표 간의 거리를 계산합니다.
    
    Parameters
    ----------
    lat1, lon1 : float
        첫 번째 지점의 위도, 경도
    lat2, lon2 : float
        두 번째 지점의 위도, 경도
        
    Returns
    -------
    float
        두 지점 간의 거리 (km)
    """
    # 지구 반지름 (km)
    R = 6371.0
    
    # 위도, 경도를 라디안으로 변환
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # 위도, 경도 차이
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # Haversine 공식
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    distance = R * c
    return distance


def get_location_coords(region_name: str) -> Optional[Tuple[float, float]]:
    """
    지역명에서 위도/경도 좌표를 찾습니다.
    
    Parameters
    ----------
    region_name : str
        지역명 (예: "전북 고창", "서울", "부산" 등)
        
    Returns
    -------
    Optional[Tuple[float, float]]
        (위도, 경도) 또는 None (찾을 수 없는 경우)
    """
    if not region_name:
        return None
    
    # 공백과 특수문자 제거하여 정규화
    normalized = re.sub(r'[^\w가-힣]', '', region_name)
    
    # 정확한 매치 먼저 시도
    if normalized in KOREA_LOCATIONS:
        return KOREA_LOCATIONS[normalized]
    
    # 부분 매치 시도 (예: "전북 고창" → "고창")
    for location, coords in KOREA_LOCATIONS.items():
        if location in normalized or normalized in location:
            return coords
    
    # 패턴 매치 (예: "전북" 포함 시 전북 좌표 반환)
    region_patterns = [
        ("서울", ["서울"]),
        ("경기", ["경기", "수원", "성남", "고양"]),
        ("인천", ["인천"]),
        ("강원", ["강원", "춘천", "원주", "강릉", "속초"]),
        ("충북", ["충북", "청주", "충주"]),
        ("충남", ["충남", "천안"]),
        ("대전", ["대전"]),
        ("전북", ["전북", "전주", "군산", "익산", "고창"]),
        ("전남", ["전남", "순천", "여수", "목포"]),
        ("광주", ["광주"]),
        ("경북", ["경북", "포항", "경주", "안동"]),
        ("경남", ["경남", "창원", "김해", "진주"]),
        ("대구", ["대구"]),
        ("부산", ["부산"]),
        ("울산", ["울산"]),
        ("제주", ["제주", "서귀포"]),
    ]
    
    for region_key, patterns in region_patterns:
        for pattern in patterns:
            if pattern in normalized:
                return KOREA_LOCATIONS.get(region_key)
    
    return None


def filter_by_distance(
    items: List[Any], 
    user_coords: Tuple[float, float], 
    max_distance_km: float = 100.0,
    lat_field: str = "lat",
    lon_field: str = "lon"
) -> List[Tuple[Any, float]]:
    """
    거리 기준으로 아이템들을 필터링하고 거리와 함께 반환합니다.
    
    Parameters
    ----------
    items : List[Any]
        필터링할 아이템 리스트 (JobPost, TourSpot 등)
    user_coords : Tuple[float, float]
        사용자 위치 (위도, 경도)
    max_distance_km : float, default=100.0
        최대 거리 (km)
    lat_field : str, default="lat"
        위도 필드명
    lon_field : str, default="lon"
        경도 필드명
        
    Returns
    -------
    List[Tuple[Any, float]]
        (아이템, 거리) 튜플 리스트, 거리순으로 정렬
    """
    user_lat, user_lon = user_coords
    results = []
    
    for item in items:
        # 아이템의 위도/경도 추출
        item_lat = getattr(item, lat_field, None)
        item_lon = getattr(item, lon_field, None)
        
        if item_lat is None or item_lon is None:
            continue
        
        # 거리 계산
        distance = calculate_distance(user_lat, user_lon, item_lat, item_lon)
        
        # 최대 거리 내에 있는 경우만 포함
        if distance <= max_distance_km:
            results.append((item, distance))
    
    # 거리순으로 정렬
    results.sort(key=lambda x: x[1])
    return results


def calculate_location_score(distance_km: float, max_distance_km: float = 100.0) -> float:
    """
    거리를 기반으로 위치 점수를 계산합니다.
    
    Parameters
    ----------
    distance_km : float
        거리 (km)
    max_distance_km : float, default=100.0
        최대 거리 (km)
        
    Returns
    -------
    float
        위치 점수 (0.0 ~ 1.0, 가까울수록 높음)
    """
    if distance_km >= max_distance_km:
        return 0.0
    
    # 선형 감소: 거리 0km = 1.0, max_distance_km = 0.0
    return max(0.0, 1.0 - (distance_km / max_distance_km))


def parse_region(region_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    지역 텍스트를 시도와 시군구로 분리합니다.
    
    Parameters
    ----------
    region_text : str
        지역 텍스트 (예: "전북 고창", "서울", "경기 수원")
        
    Returns
    -------
    Tuple[Optional[str], Optional[str]]
        (시도, 시군구) 튜플
    """
    if not region_text:
        return None, None
    
    # 공백으로 분리
    parts = region_text.strip().split()
    
    if len(parts) == 1:
        # "서울", "부산" 등 광역시인 경우
        return parts[0], None
    elif len(parts) >= 2:
        # "전북 고창", "경기 수원" 등
        return parts[0], parts[1]
    
    return None, None


def match_region_strict(target_region: str, user_regions: List[str]) -> Tuple[bool, float]:
    """
    사용자가 지정한 지역과 대상 지역의 정확한 매칭 여부를 확인합니다.
    데이터의 다양한 지역 표기 형식을 처리합니다.
    
    Parameters
    ----------
    target_region : str
        대상 지역 (DB의 region 필드값, 예: "전북 고창", "전라남도", "강원특별자치도")
    user_regions : List[str]
        사용자가 지정한 지역 리스트
        
    Returns
    -------
    Tuple[bool, float]
        (매칭 여부, 매칭 점수 0.0~1.0)
    """
    if not user_regions or not target_region:
        return False, 0.0
    
    # 대상 지역 정규화
    target_normalized = normalize_region_text(target_region)
    
    for user_region in user_regions:
        user_normalized = normalize_region_text(user_region)
        
        # 1단계: 정확한 매칭
        if target_normalized == user_normalized:
            return True, 1.0
        
        # 2단계: 시도 레벨 매칭
        target_sido = extract_sido(target_normalized)
        user_sido = extract_sido(user_normalized)
        
        if target_sido and user_sido and target_sido == user_sido:
            # 시군구 정보 확인
            target_sigungu = extract_sigungu(target_normalized)
            user_sigungu = extract_sigungu(user_normalized)
            
            if target_sigungu and user_sigungu and target_sigungu == user_sigungu:
                return True, 1.0  # 시도+시군구 완전 매칭
            elif user_sigungu is None:
                return True, 0.8  # 시도만 매칭 (사용자가 시군구 지정 안함)
            elif target_sigungu is None:
                return True, 0.7  # 대상에 시군구 정보 없음
        
        # 3단계: 부분 매칭 (문자열 포함)
        if target_normalized in user_normalized or user_normalized in target_normalized:
            return True, 0.6
    
    return False, 0.0


def get_region_expansion_levels(user_regions: List[str]) -> List[Tuple[str, float]]:
    """
    사용자 지역을 기준으로 확장 레벨을 생성합니다.
    
    Parameters
    ----------
    user_regions : List[str]
        사용자가 지정한 지역 리스트
        
    Returns
    -------
    List[Tuple[str, float]]
        (확장된_지역_패턴, 가중치) 리스트
    """
    expansion_levels = []
    
    for user_region in user_regions:
        sido, sigungu = parse_region(user_region)
        
        if sido and sigungu:
            # 1단계: 정확한 지역 (예: "전북 고창")
            expansion_levels.append((f"{sido} {sigungu}", 1.0))
            # 2단계: 같은 시도 (예: "전북")
            expansion_levels.append((sido, 0.7))
        elif sido:
            # 시도만 지정된 경우
            expansion_levels.append((sido, 0.9))
    
    # 중복 제거하면서 높은 가중치 유지
    unique_levels = {}
    for pattern, weight in expansion_levels:
        if pattern not in unique_levels or unique_levels[pattern] < weight:
            unique_levels[pattern] = weight
    
    # 가중치 순으로 정렬
    return sorted(unique_levels.items(), key=lambda x: x[1], reverse=True)


def normalize_region_names(region_list: List[str]) -> Set[str]:
    """
    지역명 리스트를 정규화하여 가능한 모든 매칭 패턴 반환.
    
    Args:
        region_list: 사용자가 입력한 지역명 리스트 (예: ["전북 고창"])
        
    Returns:
        정규화된 지역명 집합 (예: {"전북", "전라북도", "고창", "고창군"})
    """
    normalized = set()
    
    for region in region_list:
        # 공백으로 분리된 지역명 처리 (예: "전북 고창" -> ["전북", "고창"])
        parts = region.strip().split()
        
        for part in parts:
            # 기본 지역명 추가
            normalized.add(part)
            
            # 시도명 정규화
            if part in REVERSE_MAPPING:
                full_name = REVERSE_MAPPING[part]
                normalized.add(full_name)
                # 해당 시도의 모든 별칭도 추가
                normalized.update(REGION_MAPPING.get(full_name, []))
            
            # 군/구/시 접미사 처리
            for suffix in ["군", "구", "시"]:
                if not part.endswith(suffix):
                    normalized.add(f"{part}{suffix}")
                else:
                    # 접미사 제거한 버전도 추가
                    base = part[:-len(suffix)]
                    if base:
                        normalized.add(base)
    
    return normalized


def build_region_filter_condition(region_prefs: List[str]) -> str:
    """
    지역 선호도를 SQL WHERE 조건으로 변환.
    
    Args:
        region_prefs: 슬롯에서 추출된 지역 선호도 리스트
        
    Returns:
        SQL WHERE 조건 문자열
    """
    if not region_prefs:
        return "1=1"  # 지역 필터링 없음
        
    normalized_regions = normalize_region_names(region_prefs)
    
    # ILIKE 조건들 생성 (대소문자 무시, 부분 매칭)
    conditions = []
    for region in normalized_regions:
        conditions.append(f"region ILIKE '%{region}%'")
    
    return "(" + " OR ".join(conditions) + ")"


def calculate_region_match_score(item_region: str, preferred_regions: List[str]) -> float:
    """
    아이템의 지역과 사용자 선호 지역 간의 매칭 점수 계산.
    
    Args:
        item_region: 데이터베이스의 지역 필드값
        preferred_regions: 사용자가 선호하는 지역 리스트
        
    Returns:
        매칭 점수 (0.0 ~ 1.0, 높을수록 더 적합)
    """
    if not preferred_regions or not item_region:
        return 0.5  # 중립적 점수
        
    normalized_prefs = normalize_region_names(preferred_regions)
    item_region_lower = item_region.lower()
    
    # 정확한 매칭
    for pref in normalized_prefs:
        if pref.lower() in item_region_lower:
            return 1.0
            
    # 부분 매칭 점수 계산
    max_score = 0.0
    for pref in normalized_prefs:
        pref_lower = pref.lower()
        # 공통 문자 비율 계산
        common_chars = set(pref_lower) & set(item_region_lower)
        if common_chars:
            score = len(common_chars) / max(len(pref_lower), len(item_region_lower))
            max_score = max(max_score, score * 0.7)  # 부분 매칭은 70% 점수
            
    return max_score


def normalize_region_text(region_text: str) -> str:
    """
    지역 텍스트를 정규화합니다.
    """
    if not region_text:
        return ""
    
    # 공백 제거 및 소문자 변환
    normalized = re.sub(r'\s+', '', region_text.strip())
    
    # 특별자치도 → 도 변환
    normalized = re.sub(r'특별자치도$', '도', normalized)
    
    # 광역시 → 시 변환  
    normalized = re.sub(r'광역시$', '시', normalized)
    
    # 특별시 → 시 변환
    normalized = re.sub(r'특별시$', '시', normalized)
    
    return normalized


def extract_sido_from_sigungu(region_text: str) -> Optional[str]:
    """
    시/군/구 단위 지역명에서 시도명을 추출합니다.
    """
    if not region_text:
        return None
    
    # 공백 및 접미사 제거하여 정규화
    normalized = region_text.strip()
    
    # 직접 매핑에서 찾기
    if normalized in SIGUNGU_TO_SIDO_MAPPING:
        return SIGUNGU_TO_SIDO_MAPPING[normalized]
    
    # 접미사 제거 후 다시 시도
    for suffix in ["시", "군", "구"]:
        if normalized.endswith(suffix):
            base_name = normalized[:-len(suffix)]
            if base_name in SIGUNGU_TO_SIDO_MAPPING:
                return SIGUNGU_TO_SIDO_MAPPING[base_name]
    
    return None


def extract_sido(region_text: str) -> Optional[str]:
    """
    지역 텍스트에서 시도명을 추출합니다.
    시도명이 명시되지 않은 경우 시/군/구에서 추론합니다.
    """
    if not region_text:
        return None
    
    # 1단계: 전체 시도명 매핑 (정확한 매칭 우선)
    sido_mapping = {
        '서울특별시': '서울', '서울시': '서울', '서울': '서울',
        '부산광역시': '부산', '부산시': '부산', '부산': '부산',
        '대구광역시': '대구', '대구시': '대구', '대구': '대구',
        '인천광역시': '인천', '인천시': '인천', '인천': '인천',
        '광주광역시': '광주', '광주시': '광주', '광주': '광주',
        '대전광역시': '대전', '대전시': '대전', '대전': '대전',
        '울산광역시': '울산', '울산시': '울산', '울산': '울산',
        '경기도': '경기', '경기': '경기',
        '강원특별자치도': '강원', '강원도': '강원', '강원': '강원',
        '충청북도': '충북', '충북': '충북',
        '충청남도': '충남', '충남': '충남',
        '전라북도': '전북', '전북특별자치도': '전북', '전북': '전북',
        '전라남도': '전남', '전남': '전남',
        '경상북도': '경북', '경북': '경북',
        '경상남도': '경남', '경남': '경남',
        '제주특별자치도': '제주', '제주도': '제주', '제주': '제주'
    }
    
    # 정확한 매칭 우선
    for full_name, short_name in sido_mapping.items():
        if region_text.startswith(full_name):
            return short_name
    
    # 2단계: 패턴 매칭 (기존 로직)
    sido_patterns = [
        r'^서울', r'^부산', r'^대구', r'^인천', r'^광주', r'^대전', r'^울산',
        r'^경기', r'^강원', r'^충북', r'^충남', r'^전북', r'^전남', r'^경북', r'^경남', r'^제주'
    ]
    
    for pattern in sido_patterns:
        if re.search(pattern, region_text):
            match = re.search(pattern, region_text)
            return match.group()
    
    # 3단계: 시/군/구에서 시도 추론 (새 기능)
    sido_from_sigungu = extract_sido_from_sigungu(region_text)
    if sido_from_sigungu:
        return sido_from_sigungu
    
    return None


def extract_sigungu(region_text: str) -> Optional[str]:
    """
    지역 텍스트에서 시군구명을 추출합니다.
    """
    if not region_text:
        return None
    
    # 시도명 제거 후 나머지 부분이 시군구
    sido = extract_sido(region_text)
    if sido:
        remaining = region_text.replace(sido, '', 1).strip()
        if remaining:
            return remaining
    
    return None


def is_region_match(target_region: str, user_regions: List[str]) -> Tuple[bool, float]:
    """
    포괄적인 지역 매칭 함수.
    
    Args:
        target_region: 데이터베이스의 지역 (예: "제주특별자치도", "강원 강릉")
        user_regions: 사용자 입력 지역 (예: ["제주도"], ["강원도"])
        
    Returns:
        (매칭여부, 신뢰도점수)
    """
    if not user_regions or not target_region:
        return False, 0.0
    
    # 정규화
    target_normalized = normalize_region_text(target_region)
    
    for user_region in user_regions:
        user_normalized = normalize_region_text(user_region)
        
        # 1단계: 정확한 문자열 매칭
        if user_normalized in target_normalized or target_normalized in user_normalized:
            return True, 1.0
        
        # 2단계: 포괄적 매핑 테이블 검색
        if user_region in COMPREHENSIVE_REGION_MAPPING:
            for mapped_region in COMPREHENSIVE_REGION_MAPPING[user_region]:
                if mapped_region in target_region or normalize_region_text(mapped_region) in target_normalized:
                    return True, 0.9
        
        # 3단계: 시도 레벨 매칭
        target_sido = extract_sido(target_region)
        user_sido = extract_sido(user_region)
        
        if target_sido and user_sido:
            if target_sido == user_sido:
                return True, 0.8
            # 시도 별칭 매칭 (예: "제주" == "제주도")
            if user_sido in COMPREHENSIVE_REGION_MAPPING:
                for mapped in COMPREHENSIVE_REGION_MAPPING[user_sido]:
                    if extract_sido(mapped) == target_sido:
                        return True, 0.8
    
    return False, 0.0


def is_region_specified(region_pref: List[str]) -> bool:
    """
    사용자가 의미있는 지역을 명시했는지 판단합니다.
    
    Parameters
    ----------
    region_pref : List[str]
        슬롯 추출된 지역 선호도 리스트
        
    Returns
    -------
    bool
        True: 구체적인 지역이 명시됨, False: 지역이 명시되지 않음
    """
    if not region_pref:
        return False
    
    # 무의미한 지역 표현들
    generic_regions = {
        "전국", "전체", "어디든", "어디나", "상관없음", 
        "모름", "모르겠음", "미정", "아무곳", "아무곳이나"
    }
    
    for region in region_pref:
        region_clean = region.strip().lower()
        
        # 무의미한 표현이 아니고, 길이가 2자 이상인 경우 의미있는 지역으로 판단
        if region_clean not in generic_regions and len(region_clean) >= 2:
            # 한국의 실제 지역명 패턴 확인
            if any(keyword in region_clean for keyword in [
                "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
                "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
                "도", "시", "군", "구"
            ]):
                return True
    
    return False


def get_progressive_region_patterns(user_regions: List[str]) -> List[Tuple[str, float, str]]:
    """
    점진적 확장 검색을 위한 지역 패턴 생성.
    
    Returns:
        [(검색패턴, 가중치, 설명), ...]
    """
    patterns = []
    
    for user_region in user_regions:
        # 1단계: 정확한 지역명
        patterns.append((user_region, 1.0, f"정확매칭: {user_region}"))
        
        # 2단계: 매핑 테이블의 모든 별칭
        if user_region in COMPREHENSIVE_REGION_MAPPING:
            for mapped_region in COMPREHENSIVE_REGION_MAPPING[user_region]:
                patterns.append((mapped_region, 0.9, f"별칭매칭: {mapped_region}"))
        
        # 3단계: 시도 레벨 확장
        sido = extract_sido(user_region)
        if sido and sido != user_region:
            patterns.append((sido, 0.7, f"시도확장: {sido}"))
    
    # 중복 제거 및 높은 가중치 우선
    unique_patterns = {}
    for pattern, weight, desc in patterns:
        if pattern not in unique_patterns or unique_patterns[pattern][0] < weight:
            unique_patterns[pattern] = (weight, desc)
    
    return [(pattern, weight, desc) for pattern, (weight, desc) in unique_patterns.items()]


def get_intelligent_region_expansion(user_regions: List[str]) -> List[Tuple[List[str], float, str]]:
    """
    지능적 지역 확장 시스템
    사용자 입력 지역을 단계별로 지능적으로 확장하여 검색 범위를 넓힘
    
    Parameters
    ----------
    user_regions : List[str]
        사용자가 입력한 지역 리스트 (예: ["충청도"], ["충북", "충남"])
        
    Returns
    -------
    List[Tuple[List[str], float, str]]
        [(확장된_지역_리스트, 가중치, 설명), ...] 리스트
        가중치가 높을수록 사용자 의도에 근접
    """
    expansion_levels = []
    
    for user_region in user_regions:
        # 0단계: 정확한 매칭 (최고 가중치)
        expansion_levels.append(([user_region], 1.0, f"정확 매칭: '{user_region}'"))
        
        # 1단계: 직접 별칭 확장
        if user_region in COMPREHENSIVE_REGION_MAPPING:
            aliases = COMPREHENSIVE_REGION_MAPPING[user_region]
            expansion_levels.append((aliases[:5], 0.9, f"별칭 확장: '{user_region}' → {aliases[:3]}..."))
        
        # 2단계: 시도 레벨 확장
        sido = extract_sido(user_region) 
        if sido and sido != user_region:
            expansion_levels.append(([sido], 0.8, f"시도 확장: '{user_region}' → '{sido}'"))
            if sido in COMPREHENSIVE_REGION_MAPPING:
                sido_aliases = COMPREHENSIVE_REGION_MAPPING[sido]
                expansion_levels.append((sido_aliases[:3], 0.7, f"시도 별칭 확장: '{sido}' → {sido_aliases[:2]}..."))
        
        # 3단계: 지리적 인접 지역 확장 (신중하게)
        adjacent_regions = get_adjacent_regions(user_region)
        if adjacent_regions:
            expansion_levels.append((adjacent_regions[:2], 0.4, f"인접 지역: '{user_region}' → {adjacent_regions[:2]}"))
    
    # 중복 제거 및 가중치 순 정렬
    unique_expansions = {}
    for regions, weight, desc in expansion_levels:
        key = tuple(sorted(regions))
        if key not in unique_expansions or unique_expansions[key][1] < weight:
            unique_expansions[key] = (list(regions), weight, desc)
    
    result = sorted(unique_expansions.values(), key=lambda x: x[1], reverse=True)
    
    print(f"🔄 지능적 지역 확장 결과:")
    for regions, weight, desc in result[:5]:
        print(f"   • {desc} (가중치: {weight:.1f})")
    
    return result


def get_adjacent_regions(region: str) -> List[str]:
    """지리적으로 인접한 지역들을 반환 (보수적 접근)"""
    sido = extract_sido(region)
    if not sido:
        return []
    
    # 지리적으로 인접한 시도들 (보수적 매핑)
    adjacent_mapping = {
        "충북": ["충남", "경기", "강원", "전북"],
        "충남": ["충북", "대전", "세종", "경기", "전북"],
        "충청": ["대전", "세종", "전북"],
        "전북": ["전남", "충남", "경남", "충북", "충청", "김제"],  # 김제 직접 추가
        "전남": ["전북", "광주", "경남"],
        "경북": ["경남", "대구", "강원", "충북"],
        "경남": ["경북", "부산", "울산", "전북"],
        "강원": ["경기", "충북", "경북"],
        "경기": ["서울", "인천", "강원", "충북", "충남"]
    }
    
    return adjacent_mapping.get(sido, [])


def get_similar_regions(region: str) -> List[str]:
    """기존 유사 지역 함수 (하위 호환성 유지)"""
    expansion_result = get_intelligent_region_expansion([region])
    similar_regions = []
    
    for regions, _, _ in expansion_result:  # weight, desc는 사용하지 않으므로 _로 표시
        similar_regions.extend(regions)
    
    # 자기 자신 제외 및 중복 제거
    unique_similar = []
    for similar in similar_regions:
        if similar != region and similar not in unique_similar:
            unique_similar.append(similar)
    
    return unique_similar[:10]


def get_coordinates_from_region(region: str) -> Tuple[float, float]:
    """
    지역명에서 위도/경도 좌표를 반환합니다.
    
    Parameters
    ----------
    region : str
        지역명 (예: "전북 김제시", "제주 서귀포시", "경북 안동시")
        
    Returns
    -------
    Tuple[float, float]
        (위도, 경도) 좌표. 찾을 수 없으면 기본 좌표 반환
    """
    if not region:
        return 37.5665, 126.9780  # 서울 기본 좌표
    
    # 1단계: get_location_coords 함수 사용
    coords = get_location_coords(region)
    if coords:
        return coords
    
    # 2단계: 지역명 파싱하여 시도에서 좌표 찾기
    parts = region.strip().split()
    
    if len(parts) >= 2:
        # "전북 김제시" → "전북", "김제" 순으로 시도
        sido = parts[0]
        sigungu = parts[1]
        
        # 시군구 우선 검색
        sigungu_base = re.sub(r'(시|군|구)$', '', sigungu)
        if sigungu_base in KOREA_LOCATIONS:
            return KOREA_LOCATIONS[sigungu_base]
        
        # 시도 검색  
        if sido in KOREA_LOCATIONS:
            return KOREA_LOCATIONS[sido]
    
    elif len(parts) == 1:
        # "김제시" → "김제" 변환 후 검색
        region_clean = parts[0]
        region_base = re.sub(r'(시|군|구)$', '', region_clean)
        
        if region_base in KOREA_LOCATIONS:
            return KOREA_LOCATIONS[region_base]
        
        if region_clean in KOREA_LOCATIONS:
            return KOREA_LOCATIONS[region_clean]
    
    # 3단계: 시도 추출하여 해당 시도 중심 좌표 반환
    sido = extract_sido(region)
    if sido and sido in KOREA_LOCATIONS:
        return KOREA_LOCATIONS[sido]
    
    # 4단계: 찾을 수 없으면 기본 좌표 (서울)
    print(f"⚠️ 지역 '{region}'의 좌표를 찾을 수 없습니다. 기본 좌표 사용.")
    return 37.5665, 126.9780