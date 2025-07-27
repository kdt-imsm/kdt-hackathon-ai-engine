"""
tour_api_loader.py
~~~~~~~~~~~~~~~~~~
한국관광공사_국문 관광정보 서비스(GW) → areaBasedList(※ 숫자 없음) 호출
→ 관광지(TourSpot) 테이블 적재 + 태그(pref_vector) 임베딩.

❶ .env 에 반드시 두 변수를 넣어 주세요
   TOUR_BASE_URL=https://apis.data.go.kr/B551011/KorService2
   TOUR_API_KEY=발급받은키
❷ 일자리 더미를 먼저 넣었다면
   python -m scripts.tour_api_loader        # 관광지 실데이터 수집
   python -m scripts.init_db                # 태그 임베딩 재계산
"""

from __future__ import annotations
import httpx, pandas as pd, time
from pathlib import Path
from typing import List

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import SessionLocal, Base, engine
from app.db import models
from app.embeddings.embedding_service import embed_texts

CLIENT = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))

settings = get_settings()
BASE_URL: str = settings.tour_base_url.rstrip("/")          # KorService1
SERVICE_KEY: str = settings.tour_api_key

# ─────────────────────────────────────────────────────────────

DEFAULT_PARAMS = dict(
    MobileOS="ETC",
    MobileApp="ruralplanner",
    contentTypeId=12,        # 관광지(12) / 문화시설(14) / 축제공연행사(15) …
    # contentTypeId=None,    # ← None이면 모든 분류
    arrange="O",
    numOfRows=100,
    areaCode=None,              # 0 = 전국
    _type="json",            # JSON 응답
)


def fetch_area_list(page: int = 1) -> list[dict]:
    """page 단위로 관광지 목록 반환 – 빈 목록·오류 문자열도 안전 처리"""
    params = {**DEFAULT_PARAMS, "pageNo": page, "serviceKey": SERVICE_KEY}
    url = f"{BASE_URL}/areaBasedList2"

    for attempt in range(5):        # 최대 5회 재시도
        try:
            r = CLIENT.get(url, params=params)
            r.raise_for_status()
            body = r.json()["response"]["body"]
            print("DEBUG", body["totalCount"], "개")    # 총건수 확인

            # ── items 필드가 dict·list·str 세 경우 모두 처리 ──
            items_field = body.get("items")
            if not items_field:                 # None · ""  → 데이터 없음
                return []
            if isinstance(items_field, dict):
                raw_items = items_field.get("item", [])
                return raw_items if isinstance(raw_items, list) else [raw_items]
            if isinstance(items_field, list):
                return items_field
            # 문자열이면(오류 메시지·빈 XML 등) → 빈 목록
            return []

        except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
            wait = 2 ** attempt
            print(f"⚠️  {type(e).__name__} {e} … {wait}s 후 재시도")
            time.sleep(wait)

    raise RuntimeError("TourAPI 요청 반복 실패")



def to_dataframe(items: List[dict]) -> pd.DataFrame:
    rows = []
    for it in items:
        rows.append(
            dict(
                name=it["title"],
                region=it.get("addr1", "미상").split()[0],
                lat=float(it["mapy"]),
                lon=float(it["mapx"]),
                tags="관광,자연" if it.get("cat1") == "A01" else "관광,문화",
            )
        )
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────

def main(max_pages: int = 20):
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    # 1) API 호출
    all_items: list[dict] = []
    for page in range(1, max_pages + 1):
        items = fetch_area_list(page)
        if not items:
            break
        all_items.extend(items)
        time.sleep(0.2)              # 과속 방지

    if not all_items:
        print("❌ 가져온 데이터가 없습니다.")
        return

    # 2) DataFrame → CSV 백업
    df = to_dataframe(all_items)
    Path("data").mkdir(exist_ok=True)
    df.to_csv("data/tourapi_raw.csv", index=False)

    # 3) DB INSERT (UPSERT: id 충돌 시 무시)
    spots = [models.TourSpot(**row) for row in df.to_dict("records")]
    db.bulk_save_objects(spots, return_defaults=False)
    db.commit()

    # 4) 태그 임베딩
    embeddings = embed_texts(df["tags"].tolist())
    for spot, vec in zip(spots, embeddings):
        spot.pref_vector = vec
    db.commit()

    print(f"✅ Inserted/Updated {len(spots)} tour spots.")


if __name__ == "__main__":
    main()
