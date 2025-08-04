"""
tour_api_loader.py
==================
한국관광공사_국문 관광정보 서비스(GW) → areaBasedList(※ 숫자 없음) 호출
→ 관광지(TourSpot) 테이블 적재 + 태그(pref_vector) 임베딩

❶ .env 에 반드시 두 변수를 넣어 주세요
   TOUR_BASE_URL=https://apis.data.go.kr/B551011/KorService2
   TOUR_API_KEY=발급받은키
❷ 일자리 더미를 먼저 넣었다면
   python -m scripts.tour_api_loader        # 관광지 실데이터 수집
   python -m scripts.init_db                # 태그 임베딩 재계산
"""

# ---------------------------------------------------------------------------
# File Path : scripts/tour_api_loader.py
# Description:
#     • 한국관광공사 TourAPI(국문 관광정보 서비스 v2)의 `areaBasedList2` 엔드포인트를
#       호출하여 전국(또는 지역) 관광지 목록을 페이지 단위로 수집합니다.
#     • 응답 JSON을 정규화하여 `TourSpot` ORM 모델에 INSERT/UPSERT 하고,
#       관광지 카테고리(cat1)에 따라 간단한 태그 문자열을 생성합니다.
#     • `app.embeddings.embedding_service.embed_texts` 를 사용해 태그를 OpenAI
#       Embedding 벡터로 변환한 뒤 `pref_vector` 필드에 저장합니다.
#     • 호출 빈도를 제한하기 위해 페이지 간 0.2초 슬립, 오류 시 지수 백오프 등
#       기본적인 오류/재시도 로직을 포함합니다.
#
# Usage:
#     $ python -m scripts.tour_api_loader          # 관광지 실데이터 수집
#     이후 `python -m scripts.init_db` 로 임베딩 재계산 가능
# ---------------------------------------------------------------------------

from __future__ import annotations
import httpx, pandas as pd, time
from pathlib import Path
from typing import List

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import SessionLocal, Base, engine
from app.db import models
from app.embeddings.embedding_service import embed_texts

# httpx 클라이언트: 연결·전체 요청 타임아웃 설정
CLIENT = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))

# 환경설정 로드 (.env → Pydantic Settings)
settings = get_settings()
BASE_URL: str = settings.tour_base_url.rstrip("/")          # KorService2 베이스 URL
SERVICE_KEY: str = settings.tour_api_key                     # 개인 인증키

# ─────────────────────────────────────────────────────────────
# TourAPI 기본 쿼리 파라미터 (공통)
# ─────────────────────────────────────────────────────────────
DEFAULT_PARAMS = dict(
    MobileOS="ETC",           # 필수 값 (안드로이드/iOS 구분無)
    MobileApp="ruralplanner", # 임의 App명
    contentTypeId=12,          # 관광지(12) / 문화시설(14) / 축제공연행사(15) …
    # contentTypeId=None,      # ← None이면 모든 분류
    arrange="O",             # 대표이미지 여부 정렬 (O:제목순)
    numOfRows=100,            # 페이지 당 최대 100건
    areaCode=None,            # 0 또는 None = 전국
    _type="json",           # JSON 응답
)

# ─────────────────────────────────────────────────────────────
# API 호출 유틸리티
# ─────────────────────────────────────────────────────────────

def fetch_area_list(page: int = 1) -> tuple[list[dict], int]:
    """단일 페이지(`pageNo`) 관광지 목록을 반환합니다.

    • API 응답의 `items` 필드 형태가 dict/list/str/None 등 다양하므로
      모든 케이스를 안전하게 처리하여 list[dict] 형태로 변환합니다.
    • 네트워크 장애 또는 5xx 응답 시 지수 백오프로 최대 5회 재시도 후 실패.
    
    Returns:
        tuple: (items 리스트, totalCount)
    """
    params = {**DEFAULT_PARAMS, "pageNo": page, "serviceKey": SERVICE_KEY}
    url = f"{BASE_URL}/areaBasedList2"

    for attempt in range(5):        # 최대 5회 재시도
        try:
            r = CLIENT.get(url, params=params)
            r.raise_for_status()
            body = r.json()["response"]["body"]
            total_count = int(body.get("totalCount", 0))
            print(f"DEBUG 페이지 {page}: 총 {total_count}개 중 현재 페이지 데이터 처리")

            # ── items 필드가 dict·list·str 세 경우 모두 처리 ──
            items_field = body.get("items")
            if not items_field:                 # None · ""  → 데이터 없음
                return [], total_count
            if isinstance(items_field, dict):
                raw_items = items_field.get("item", [])
                items = raw_items if isinstance(raw_items, list) else [raw_items]
                return items, total_count
            if isinstance(items_field, list):
                return items_field, total_count
            # 문자열이면(오류 메시지·빈 XML 등) → 빈 목록
            return [], total_count

        except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
            # 지수 백오프: 1s → 2s → 4s …
            wait = 2 ** attempt
            print(f"⚠️  {type(e).__name__} {e} … {wait}s 후 재시도")
            time.sleep(wait)

    # 최대 재시도 초과 시 예외
    raise RuntimeError("TourAPI 요청 반복 실패")


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
        "MobileApp": "ruralplanner",
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


def to_dataframe(items: List[dict]) -> pd.DataFrame:
    """TourAPI raw 응답(list[dict]) → 표준화된 DataFrame 변환."""
    rows = []
    for it in items:
        # addr1 안전하게 처리 (빈 문자열이나 공백만 있는 경우 대비)
        addr1 = it.get("addr1", "").strip()
        if addr1:
            region_parts = addr1.split()
            region = region_parts[0] if region_parts else "미상"
        else:
            region = "미상"
            
        rows.append(
            dict(
                name=it["title"],
                region=region,   # 주소 앞단(시/도)
                lat=float(it["mapy"]),                        # 위도
                lon=float(it["mapx"]),                        # 경도
                # 🔥 NEW: contentid 추가
                contentid=it.get("contentid", ""),           # TourAPI contentid
                # cat1 == "A01" (자연) → 자연 태그, 그 외 문화 태그 부여
                tags="관광,자연" if it.get("cat1") == "A01" else "관광,문화",
            )
        )
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────
# 메인 로직
# ─────────────────────────────────────────────────────────────

def main():
    # 0) 테이블이 없을 수 있으므로 방어적으로 create_all
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    # 1) 첫 페이지 호출로 전체 데이터 개수 파악
    all_items: list[dict] = []
    
    print("🔍 Tour API에서 전체 데이터 수집을 시작합니다...")
    items, total_count = fetch_area_list(1)
    
    if not items and total_count == 0:
        print("❌ 가져온 데이터가 없습니다.")
        return
        
    all_items.extend(items)
    
    # 전체 페이지 수 계산
    page_size = DEFAULT_PARAMS["numOfRows"]  # 100
    total_pages = (total_count + page_size - 1) // page_size  # 올림 계산
    
    print(f"📊 전체 {total_count}개 데이터, {total_pages}페이지 예상")
    print(f"🔄 1/{total_pages} 페이지 완료 ({len(items)}건)")
    
    # 2) 나머지 페이지 순회 (최대 1000페이지로 안전장치)
    max_safety_pages = min(total_pages, 1000)
    
    for page in range(2, max_safety_pages + 1):
        items, _ = fetch_area_list(page)
        if not items:
            print(f"⚠️  {page}페이지에서 데이터가 없어 수집을 종료합니다.")
            break  # 더 이상 데이터 없음
            
        all_items.extend(items)
        print(f"🔄 {page}/{total_pages} 페이지 완료 ({len(items)}건) - 총 누적: {len(all_items)}건")
        time.sleep(0.2)              # 과속 방지 (일 1,000건 제한 대비)

    # 3) DataFrame 저장(백업) 및 가공
    print(f"💾 수집 완료: 총 {len(all_items)}건의 관광지 데이터")
    df = to_dataframe(all_items)
    Path("data").mkdir(exist_ok=True)
    df.to_csv("data/tour_api.csv", index=False)
    print(f"✅ CSV 파일 저장: data/tour_api.csv")

    # 4) 이미지 URL 수집
    print("🖼️ 관광지 이미지 수집 중...")
    image_urls = []
    for i, contentid in enumerate(df["contentid"], 1):
        if i % 10 == 0:  # 진행률 표시
            print(f"   진행률: {i}/{len(df)} ({i/len(df)*100:.1f}%)")
        
        image_url = fetch_detail_image(contentid)
        image_urls.append(image_url)
        time.sleep(0.1)  # API 호출 간격 조절
    
    df["image_url"] = image_urls
    print(f"✅ 이미지 수집 완료: {sum(1 for url in image_urls if url)}개 이미지")

    # 5) DB INSERT (ORM 객체 생성 후 bulk_save)
    spots = [models.TourSpot(**row) for row in df.to_dict("records")]
    db.bulk_save_objects(spots, return_defaults=False)
    db.commit()

    # 6) 태그 임베딩 → pref_vector 컬럼 저장
    print("🤖 OpenAI 임베딩 생성 중...")
    embeddings = embed_texts(df["tags"].tolist())
    for spot, vec in zip(spots, embeddings):
        spot.pref_vector = vec
    db.commit()

    print(f"✅ 데이터베이스 저장 완료: {len(spots)}개 관광지 + 임베딩 + 이미지")


if __name__ == "__main__":
    main()
