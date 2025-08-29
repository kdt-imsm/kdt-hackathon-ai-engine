"""
tour_api_loader.py (개선 버전)
==============================
한국관광공사_국문 관광정보 서비스(GW) → contentTypeId별 분리 수집

❶ .env 에 반드시 두 변수를 넣어 주세요
   TOUR_BASE_URL=https://apis.data.go.kr/B551011/KorService2
   TOUR_API_KEY=발급받은키
❷ 실행 방법:
   python -m scripts.tour_api_loader        # contentType별 분리 수집
   python -m scripts.init_db                # 임베딩 재계산

주요 개선사항:
- contentTypeId별 개별 CSV 파일 생성
- 각 파일이 어떤 데이터인지 직관적 파일명
- 개발 과정에서 데이터 추적 용이
"""

from __future__ import annotations
import httpx, pandas as pd, time
from pathlib import Path
from typing import List, Dict

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import SessionLocal, Base, engine
from app.db import models
from app.embeddings.embedding_service import embed_texts
from app.utils.keyword_search import get_keyword_service
import json

# httpx 클라이언트: 연결·전체 요청 타임아웃 설정
CLIENT = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))

# 환경설정 로드 (.env → Pydantic Settings)
settings = get_settings()

# contentTypeId별 파일명 매핑
CONTENT_TYPE_FILES = {
    12: "tour_api_attractions.csv",      # 관광지 (기존 tour_api_with_keywords.csv와 동일)
    14: "tour_api_cultural.csv",         # 문화시설
    15: "tour_api_festivals.csv",        # 축제/공연/행사  
    25: "tour_api_courses.csv",          # 여행코스
    28: "tour_api_leisure.csv",          # 레포츠
    38: "tour_api_shopping.csv",         # 쇼핑
    32: "tour_api_accommodations.csv",   # 숙박 (별도 스크립트)
    39: "tour_api_restaurants.csv"       # 음식점 (별도 스크립트)
}

BASE_URL: str = settings.tour_base_url.rstrip("/")          # KorService2 베이스 URL
SERVICE_KEY: str = settings.tour_api_key                     # 개인 인증키

print(f"🔧 환경 설정 확인:")
print(f"   BASE_URL: {BASE_URL}")
print(f"   SERVICE_KEY: {'*' * 10}{SERVICE_KEY[-10:] if len(SERVICE_KEY) > 10 else SERVICE_KEY}")
print()

# ─────────────────────────────────────────────────────────────
# API 호출 & 페이지네이션
# ─────────────────────────────────────────────────────────────

# API 공통 파라미터 (listYN 제거)
DEFAULT_PARAMS = {
    "serviceKey": SERVICE_KEY,
    "MobileOS": "ETC",
    "MobileApp": "KDT-AgricultureTourApp",
    "_type": "json",
    "arrange": "A",     # 제목 순 정렬  
    "numOfRows": 100,   # 페이지당 100개
    "pageNo": 1
}

def fetch_area_list(
    page: int = 1,
    contentTypeId=None,        # None이면 모든 분류 수집
    areaCode=None,
    sigunguCode=None,
    max_retries: int = 3
) -> tuple[list[dict], int]:
    """areaBasedList2 API 호출 (페이지별)."""
    
    params = DEFAULT_PARAMS.copy()
    params["pageNo"] = page
    
    if areaCode:
        params["areaCode"] = areaCode
    if sigunguCode:
        params["sigunguCode"] = sigunguCode
    if contentTypeId:
        params["contentTypeId"] = contentTypeId

    url = f"{BASE_URL}/areaBasedList2"
    
    for attempt in range(max_retries):
        try:
            print(f"   📡 API 호출: 페이지 {page} (시도 {attempt + 1}/{max_retries})")
            response = CLIENT.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # 응답 내용 디버깅
            response_text = response.text.strip()
            if not response_text:
                print(f"   ⚠️ 빈 응답 받음 (페이지 {page})")
                return [], 0
                
            if not response_text.startswith('{'):
                print(f"   ⚠️ JSON이 아닌 응답 받음 (페이지 {page}): {response_text[:200]}...")
                return [], 0
            
            data = response.json()
            
            # 디버깅: API 응답 구조 출력
            print(f"   🔍 API 응답 구조: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}...")
            
            # TourAPI 응답 구조 파싱
            if "response" not in data:
                print(f"   ❌ 응답에 'response' 키가 없습니다: {data}")
                return [], 0
                
            response_data = data["response"]
            print(f"   📋 response 데이터: {response_data}")
            
            header = response_data.get("header", {})
            print(f"   📄 header: {header}")
            
            body = response_data.get("body", {})
            if not body or body.get("totalCount", 0) == 0:
                print(f"   ⚠️ body가 없거나 totalCount가 0입니다: {body}")
                return [], 0
            
            items = body.get("items", {})
            if not items:
                return [], body.get("totalCount", 0)
                
            item_list = items.get("item", [])
            if not isinstance(item_list, list):
                item_list = [item_list]  # 단일 아이템을 리스트로 변환
                
            total_count = body.get("totalCount", len(item_list))
            return item_list, total_count
            
        except Exception as e:
            print(f"   ❌ API 호출 실패 (시도 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 지수 백오프
            else:
                raise e

    return [], 0

def generate_tags_by_content_type(content_type_id, cat1):
    """contentTypeId와 cat1에 따라 적절한 태그를 생성합니다."""
    tags = []
    
    # contentTypeId별 태그 매핑
    type_mapping = {
        12: "관광지",
        14: "문화시설", 
        15: "축제",
        25: "여행코스",
        28: "레포츠",
        38: "쇼핑",
        32: "숙박",
        39: "음식점"
    }
    
    if content_type_id and int(content_type_id) in type_mapping:
        tags.append(type_mapping[int(content_type_id)])
    
    # cat1 분류별 세부 태그
    if cat1:
        cat1_mapping = {
            "A01": "자연",
            "A02": "인문",
            "A03": "레포츠", 
            "A04": "쇼핑",
            "A05": "음식",
            "B02": "숙박",
            "C01": "추천코스"
        }
        if cat1 in cat1_mapping:
            tags.append(cat1_mapping[cat1])
    
    return ",".join(tags) if tags else "기타"

def to_dataframe(tour_items: list[dict]) -> pd.DataFrame:
    """TourAPI 응답을 DataFrame으로 변환."""
    rows = []
    
    for it in tour_items:
        # 좌표 변환 (문자열 → float)
        try:
            longitude = float(it.get("mapx", 0)) if it.get("mapx") else None
            latitude = float(it.get("mapy", 0)) if it.get("mapy") else None
        except (ValueError, TypeError):
            longitude = None
            latitude = None
        
        rows.append(
            dict(
                # TourSpot 모델 필드와 일치
                id=None,                                         # 자동 증가
                name=it.get("title", "제목없음"),
                region=it.get("addr1", "주소없음"),
                lat=latitude,                                   # latitude → lat
                lon=longitude,                                  # longitude → lon
                contentid=it.get("contentid", ""),           # TourAPI contentid
                # contentTypeId에 따른 태그 생성
                tags=generate_tags_by_content_type(it.get("contenttypeid"), it.get("cat1")),
                image_url=None,                                 # 기본값
                detailed_keywords="[]",                         # 기본값
                keywords=None                                   # 기본값
            )
        )
    
    return pd.DataFrame(rows)

# ─────────────────────────────────────────────────────────────
# 이미지 수집 함수
# ─────────────────────────────────────────────────────────────

def fetch_detail_image(contentid: str) -> str | None:
    """TourAPI detailImage2 엔드포인트로 관광지 이미지 URL을 가져옵니다.
    
    Parameters
    ----------
    contentid : str
        TourAPI contentid
        
    Returns
    -------
    str | None
        대표 이미지 URL 또는 None (이미지가 없는 경우)
    """
    if not contentid:
        return None
        
    params = {
        "serviceKey": SERVICE_KEY,
        "MobileOS": "ETC",
        "MobileApp": "KDT-AgricultureTourApp",
        "contentId": contentid,
        "imageYN": "Y",
        "numOfRows": 1,  # 대표 이미지 1개만
        "_type": "json"
    }
    
    url = f"{BASE_URL}/detailImage2"
    
    try:
        r = CLIENT.get(url, params=params)
        r.raise_for_status()
        body = r.json()["response"]["body"]
        
        items_field = body.get("items")
        if not items_field:
            return None
            
        if isinstance(items_field, dict):
            raw_items = items_field.get("item", [])
            items = raw_items if isinstance(raw_items, list) else [raw_items]
        elif isinstance(items_field, list):
            items = items_field
        else:
            return None
            
        # 첫 번째 이미지의 originimgurl 반환
        if items and len(items) > 0:
            return items[0].get("originimgurl")
            
    except Exception as e:
        print(f"⚠️ 이미지 수집 실패 (contentid: {contentid}): {e}")
        
    return None

# ─────────────────────────────────────────────────────────────
# 메인 로직
# ─────────────────────────────────────────────────────────────

def load_existing_data_for_type(content_type_id: int) -> tuple[pd.DataFrame | None, set]:
    """특정 contentTypeId의 기존 CSV 파일을 로드합니다."""
    file_path = Path("data") / CONTENT_TYPE_FILES[content_type_id]
    
    if file_path.exists():
        try:
            existing_df = pd.read_csv(file_path)
            existing_contentids = set(existing_df["contentid"].astype(str))
            print(f"📄 기존 {CONTENT_TYPE_FILES[content_type_id]} 파일 로드: {len(existing_df)}건")
            return existing_df, existing_contentids
        except Exception as e:
            print(f"❌ 기존 파일 로드 실패 ({CONTENT_TYPE_FILES[content_type_id]}): {e}")
            return None, set()
    else:
        print(f"📄 {CONTENT_TYPE_FILES[content_type_id]} 파일이 없습니다. 새로 생성합니다.")
        return None, set()

def collect_all_content_type_data(content_type_id: int, type_name: str, existing_contentids: set) -> list[dict]:
    """특정 contentTypeId의 데이터를 전부 수집합니다 (개수 제한 없음, 중복 제외)."""
    print(f"🔍 {type_name} 데이터 전체 수집 시작 (contentTypeId: {content_type_id})...")
    
    all_items: list[dict] = []
    new_items_count = 0
    
    # 첫 페이지로 전체 개수 파악
    items, total_count = fetch_area_list(1, content_type_id)
    
    if not items and total_count == 0:
        print(f"❌ {type_name} 데이터가 없습니다.")
        return []
        
    # 중복 체크하여 신규 데이터만 추가
    for item in items:
        if item.get("contentid", "") not in existing_contentids:
            all_items.append(item)
            new_items_count += 1
    
    # 전체 페이지 수 계산
    page_size = DEFAULT_PARAMS["numOfRows"]
    total_pages = (total_count + page_size - 1) // page_size
    
    print(f"   {type_name}: 전체 {total_count}개 데이터, {total_pages}페이지 (전체 수집)")
    print(f"   🔄 1/{total_pages} 페이지 완료 - 신규: {new_items_count}건")
    
    # 나머지 페이지 수집
    for page in range(2, total_pages + 1):
        try:
            items, _ = fetch_area_list(page, content_type_id)
            if not items:
                print(f"   ⚠️  {page}페이지에서 데이터가 없어 수집을 종료합니다.")
                break
        except Exception as e:
            print(f"   ❌ {page}페이지 수집 실패, 계속 진행: {e}")
            continue  # 실패한 페이지는 건너뛰고 계속
        
        # 중복 체크
        page_new_count = 0
        for item in items:
            if item.get("contentid", "") not in existing_contentids:
                all_items.append(item)
                page_new_count += 1
                
        new_items_count += page_new_count
        
        if page % 10 == 0:  # 10페이지마다 진행 상황 출력
            print(f"   🔄 {page}/{total_pages} 페이지 완료 - 총 신규 누적: {new_items_count}건")
        time.sleep(0.2)
    
    print(f"✅ {type_name} 수집 완료: 총 {len(all_items)}건 신규 데이터")
    return all_items

def save_type_specific_data(content_type_id: int, new_df: pd.DataFrame, existing_df: pd.DataFrame | None):
    """contentType별로 개별 CSV 파일에 저장합니다."""
    filename = CONTENT_TYPE_FILES[content_type_id]
    file_path = Path("data") / filename
    
    # 이미지 URL과 detailed_keywords 기본값 설정
    if "image_url" not in new_df.columns:
        new_df["image_url"] = None
    if "detailed_keywords" not in new_df.columns:
        new_df["detailed_keywords"] = "[]"
    
    # 기존 데이터와 병합
    if existing_df is not None:
        # 기존 데이터에 컬럼이 없을 수 있으므로 처리
        if "image_url" not in existing_df.columns:
            existing_df["image_url"] = None
        if "detailed_keywords" not in existing_df.columns:
            existing_df["detailed_keywords"] = "[]"
            
        final_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        final_df = new_df
    
    # CSV 파일 저장
    Path("data").mkdir(exist_ok=True)
    final_df.to_csv(file_path, index=False)
    print(f"✅ {filename} 저장 완료: {len(final_df)}건")
    
    return final_df

def main():
    print("🌟 contentType별 분리 수집을 시작합니다!")
    print("📌 TOUR_DATA_SYSTEM_GUIDE.md에 따라 6개 관광 콘텐츠를 수집합니다")
    print("   (관광지, 문화시설, 축제, 여행코스, 레포츠, 쇼핑)\n")
    print("   숙박/음식점은 별도 스크립트로 수집하세요: accommodation_restaurant_loader.py\n")

    # 1) 테이블 생성
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    # 2) 수집할 contentType 정의 (가이드 문서 기준 전체 수집)
    content_types = [
        (12, "관광지"),
        (14, "문화시설"), 
        (15, "축제/공연/행사"),
        (25, "여행코스"),
        (28, "레포츠"),
        (38, "쇼핑")
    ]
    
    print("🌟 전체 모드: 가이드 문서에 따라 6개 contentType을 모두 수집합니다.")
    
    total_new_items = 0
    all_db_items = []  # 데이터베이스 저장용
    
    # 3) contentType별로 개별 처리
    for content_type_id, type_name in content_types:
        print(f"\n{'='*60}")
        print(f"🔄 {type_name} (contentTypeId: {content_type_id}) 처리 시작")
        print(f"{'='*60}")
        
        # 기존 데이터 로드
        existing_df, existing_contentids = load_existing_data_for_type(content_type_id)
        
        # 신규 데이터 수집
        new_items = collect_all_content_type_data(content_type_id, type_name, existing_contentids)
        
        if new_items:
            print(f"💾 {type_name} 신규 데이터 처리 시작: {len(new_items)}건")
            new_df = to_dataframe(new_items)
            
            # contentType별 파일 저장
            final_df = save_type_specific_data(content_type_id, new_df, existing_df)
            
            # 데이터베이스 저장용 누적
            all_db_items.extend(new_df.to_dict("records"))
            total_new_items += len(new_items)
            
            print(f"✅ {type_name} 처리 완료 (신규 {len(new_items)}건, 총 {len(final_df)}건)")
        else:
            print(f"🎉 {type_name}: 신규 수집할 데이터가 없습니다.")
        
        time.sleep(2.0)  # API 안정성을 위한 간격

    # 4) 데이터베이스 일괄 저장 (신규 데이터만)
    if all_db_items:
        print(f"\n🗄️ 데이터베이스에 신규 데이터 일괄 저장 중: {len(all_db_items)}건...")
        spots = [models.TourSpot(**row) for row in all_db_items]
        db.bulk_save_objects(spots, return_defaults=False)
        db.commit()
        print(f"✅ 데이터베이스 저장 완료")

        # 5) 임베딩 벡터 생성 (신규 데이터만)
        print("🧠 OpenAI 임베딩 벡터 생성 중...")
        tag_texts = [row["tags"] for row in all_db_items]
        vectors = embed_texts(tag_texts)
        
        # 벡터를 데이터베이스에 업데이트
        for i, row in enumerate(all_db_items):
            tour_spot = db.query(models.TourSpot).filter_by(contentid=row["contentid"]).first()
            if tour_spot:
                tour_spot.pref_vector = vectors[i]
        
        db.commit()
        print(f"✅ 임베딩 벡터 생성 완료: {len(vectors)}개")
    else:
        print("\n🎉 모든 데이터가 최신 상태입니다. 새로 수집할 데이터가 없습니다.")
    
    db.close()
    
    print(f"\n{'='*60}")
    print("🎉 모든 작업이 완료되었습니다!")
    print(f"📊 총 신규 수집: {total_new_items}건")
    print("📁 생성된 파일들:")
    for content_type_id, filename in CONTENT_TYPE_FILES.items():
        if content_type_id in [ct[0] for ct in content_types]:
            file_path = Path("data") / filename
            if file_path.exists():
                print(f"   - {filename}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()