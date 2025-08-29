"""
scripts/init_db.py
==================

Database 초기화 및 더미 데이터 로딩 스크립트
------------------------------------------------
KDT 해커톤 프로젝트의 로컬 개발·시연 환경용 PostgreSQL + pgvector 데이터베이스를
완전히 재생성하고, CSV 기반 더미 데이터를 UPSERT(삽입/갱신)하며
OpenAI Embedding API를 통해 임베딩 벡터를 저장합니다.

실행 단계
~~~~~~~~~
0. pgvector `vector` EXTENSION 설치
1. 기존 모든 테이블 **DROP**
2. `Base.metadata.create_all()` 로 테이블 **재생성**
3. `data/dummy_jobs.csv` → `JobPost` 테이블 UPSERT
4. `JobPost` 태그 임베딩 갱신
5. `TourSpot` 관광지 개요 임베딩 갱신
6. `data/dummy_prefer.csv` → 더미 사용자 선호 태그 로드

주요 함수
~~~~~~~~~
- ``upsert_from_df(df, model, db)``
  Pandas DataFrame을 ORM 테이블에 UPSERT합니다.

- ``refresh_embeddings(db, rows, attr_name="tags")``
  `embedding` 필드가 비어 있는 레코드를 임베딩 후 저장합니다.

사용 예시
~~~~~~~~~
```bash
python -m scripts.init_db
```

환경 의존성
~~~~~~~~~~~
- .env : DB URL, OpenAI API KEY 등 환경 변수
- app.embeddings.embedding_service.embed_texts : OpenAI Embedding 호출 래퍼
"""

from pathlib import Path
import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import SessionLocal, Base, engine
from app.db import models
from app.embeddings.embedding_service import embed_texts

# --------------------------------------------------------------------------- #
# 상수: 더미 CSV 파일 경로 (일거리 데이터)
# --------------------------------------------------------------------------- #
CSV_JOBS = Path("data/dummy_jobs.csv")
CSV_TOURS = Path("data/tour_api_attractions.csv")  # 관광지 데이터 사용


def upsert_from_df(df: pd.DataFrame, model, db: Session):
    """DataFrame을 ORM 테이블에 UPSERT.

    Args:
        df (pd.DataFrame): 삽입/갱신할 데이터프레임 (PK 컬럼 포함).
        model (DeclarativeMeta): SQLAlchemy ORM 모델 클래스.
        db (Session): SQLAlchemy 세션 인스턴스.

    Notes:
        - `sqlalchemy.dialects.postgresql.insert` 사용.
        - Primary Key 충돌 시 `ON CONFLICT DO UPDATE`로 id 외 컬럼을 갱신합니다.
    """
    # DataFrame → list[dict] 로 변환하여 bulk insert 형태로 작성
    records = df.to_dict("records")

    insert_stmt = insert(model).values(records)

    # id(PK)를 제외한 모든 컬럼을 업데이트 대상으로 지정
    update_cols = {
        c: getattr(insert_stmt.excluded, c)
        for c in df.columns if c != "id"
    }

    stmt = insert_stmt.on_conflict_do_update(
        index_elements=[model.__table__.primary_key.columns.keys()[0]],
        set_=update_cols,
    )

    db.execute(stmt)
    db.commit()


def refresh_embeddings(db: Session, rows, attr_name: str = "tags"):
    """pref_vector가 비어 있는 레코드만 임베딩 후 저장합니다.

    Args:
        db (Session): SQLAlchemy 세션.
        rows (list[Any]): ORM 객체 리스트 (JobPost, TourSpot 등).
        attr_name (str): 임베딩 대상 텍스트가 저장된 속성명.
    """
    # 1) pref_vector가 None 인 레코드만 필터링
    needs = [r for r in rows if getattr(r, "pref_vector", None) is None]
    if not needs:
        return  # 모두 임베딩 존재

    # 2) 텍스트 추출 (list → 공백 join, str → 그대로)
    texts = []
    for r in needs:
        val = getattr(r, attr_name)
        texts.append(" ".join(val) if isinstance(val, list) else str(val))

    # 3) OpenAI Embedding API 호출 → 벡터 리스트 반환
    embeds = embed_texts(texts)

    # 4) ORM 객체 pref_vector 필드에 벡터 저장
    for obj, vec in zip(needs, embeds):
        obj.pref_vector = vec
    db.commit()


if __name__ == "__main__":
    # --------------------------- 0) pgvector 확장 --------------------------- #
    print("▶ pgvector extension 설치 중...")
    with engine.begin() as conn:  # 자동 커밋 컨텍스트
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

    # --------------------------- 1) 테이블 DROP ----------------------------- #
    print("▶ 기존 테이블(drop) 중...")
    Base.metadata.drop_all(bind=engine)

    # --------------------------- 2) 테이블 CREATE --------------------------- #
    print("▶ 테이블(create) 재생성 중...")
    Base.metadata.create_all(bind=engine)

    # SQLAlchemy 세션 생성
    db = SessionLocal()

    # ------------------- 3) dummy_jobs.csv UPSERT --------------------------- #
    print("▶ dummy_jobs.csv 로 일거리 UPSERT 중...")
    jobs_df = pd.read_csv(CSV_JOBS)
    
    # CSV 파일은 이미 올바른 영문 컬럼명을 사용하므로 매핑 불필요
    # 필요한 컬럼들이 모두 존재하는지 확인
    required_columns = ['title', 'work_date', 'work_hours', 'required_people', 'region', 'address', 'crop_type', 'preference_condition', 'image_url']
    missing_columns = [col for col in required_columns if col not in jobs_df.columns]
    if missing_columns:
        print(f"❌ CSV 파일에 필수 컬럼이 없습니다: {missing_columns}")
        print(f"📋 CSV 실제 컬럼: {list(jobs_df.columns)}")
        raise ValueError(f"CSV 파일 구조가 올바르지 않습니다: {missing_columns}")
    
    print(f"✅ CSV 파일 구조 확인 완료: {len(jobs_df)} 레코드, {len(jobs_df.columns)} 컬럼")
    
    # 근무시간에서 start_time, end_time 추출
    def parse_work_hours(work_hours):
        if pd.isna(work_hours) or work_hours == '':
            return None, None
        try:
            if '-' in str(work_hours):
                start, end = str(work_hours).split('-', 1)
                return start.strip(), end.strip()
        except:
            pass
        return None, None
    
    if 'work_hours' in jobs_df.columns:
        jobs_df[['start_time', 'end_time']] = jobs_df['work_hours'].apply(
            lambda x: pd.Series(parse_work_hours(x))
        )
    
    # tags 필드 생성 (crop_type + preference_condition 조합)
    if 'crop_type' in jobs_df.columns and 'preference_condition' in jobs_df.columns:
        jobs_df['tags'] = jobs_df.apply(
            lambda row: f"{row.get('crop_type', '')} {row.get('preference_condition', '')}".strip(),
            axis=1
        )
    elif 'tags' not in jobs_df.columns:
        jobs_df['tags'] = '농업 체험'  # 기본값
    
    # id 컬럼 처리
    if 'job_id' in jobs_df.columns:
        jobs_df = jobs_df.rename(columns={'job_id': 'id'})
    elif 'id' not in jobs_df.columns:
        jobs_df = jobs_df.reset_index()
        jobs_df = jobs_df.rename(columns={'index': 'id'})
        jobs_df['id'] = jobs_df['id'] + 1
    
    # 좌표 정보 생성 (지역 기반)
    from app.utils.location import get_coordinates_from_region
    
    if 'lat' not in jobs_df.columns or 'lon' not in jobs_df.columns:
        print("   🌍 지역 기반 좌표 생성 중...")
        coordinates = []
        
        for _, row in jobs_df.iterrows():
            region = row.get('region', '')
            lat, lon = get_coordinates_from_region(region)
            coordinates.append({'lat': lat, 'lon': lon})
        
        coords_df = pd.DataFrame(coordinates)
        jobs_df['lat'] = coords_df['lat']
        jobs_df['lon'] = coords_df['lon']
        
        print(f"   ✅ 좌표 생성 완료: 유효한 좌표 {sum(jobs_df['lat'].notna())}개")
    else:
        print("   ✅ 기존 좌표 정보 사용")
    
    upsert_from_df(jobs_df, models.JobPost, db)

    # ------------------- 3-2) 관광지 CSV 통합 로드 --------------------------- #
    print("▶ 관광지 데이터 통합 로드 중...")
    
    # 사용 가능한 관광지 CSV 파일들
    tour_files = [
        "data/tour_api_attractions.csv",
        "data/tour_api_cultural.csv", 
        "data/tour_api_festivals.csv",
        "data/tour_api_courses.csv",
        "data/tour_api_leisure.csv",
        "data/tour_api_shopping.csv"
    ]
    
    all_tours_df = pd.DataFrame()
    
    for file_path in tour_files:
        if Path(file_path).exists():
            try:
                df = pd.read_csv(file_path)
                print(f"   ✅ {Path(file_path).name}: {len(df)}건 로드")
                all_tours_df = pd.concat([all_tours_df, df], ignore_index=True)
            except Exception as e:
                print(f"   ⚠️ {Path(file_path).name} 로드 실패: {e}")
        else:
            print(f"   ❌ {Path(file_path).name} 파일 없음")
    
    if len(all_tours_df) > 0:
        # 데이터 정제: TourSpot 모델과 일치시키기
        print("   🔧 데이터 스키마 정리 중...")
        
        # 필수 컬럼만 추출 (TourSpot 모델에 맞게)
        required_columns = ['name', 'region', 'tags', 'lat', 'lon', 'contentid', 'image_url', 'detailed_keywords', 'keywords']
        
        # 존재하는 컬럼만 유지
        available_columns = [col for col in required_columns if col in all_tours_df.columns]
        clean_tours_df = all_tours_df[available_columns].copy()
        
        # 누락된 컬럼 기본값으로 채우기
        for col in required_columns:
            if col not in clean_tours_df.columns:
                if col in ['detailed_keywords']:
                    clean_tours_df[col] = "[]"
                elif col in ['keywords', 'image_url']:
                    clean_tours_df[col] = ""
                else:
                    clean_tours_df[col] = None
        
        # id 컬럼 추가 (인덱스 기반)
        clean_tours_df = clean_tours_df.reset_index()
        clean_tours_df = clean_tours_df.rename(columns={'index': 'id'})
        clean_tours_df['id'] = clean_tours_df['id'] + 1
        
        # 중복 행 제거 (contentid 기준)
        if 'contentid' in clean_tours_df.columns:
            clean_tours_df = clean_tours_df.drop_duplicates(subset=['contentid'], keep='first')
        
        print(f"   📊 정제된 관광지 데이터: {len(clean_tours_df)}건")
        print(f"   📋 사용 컬럼: {list(clean_tours_df.columns)}")
        
        upsert_from_df(clean_tours_df, models.TourSpot, db)
    else:
        print("   ❌ 로드할 관광지 데이터가 없습니다.")

    # --------------------- 4) JobPost 임베딩 갱신 --------------------------- #
    print("▶ 일거리 embedding 갱신 중...")
    job_rows = db.query(models.JobPost).all()
    refresh_embeddings(db, job_rows, attr_name="tags")

    # --------------------- 5) TourSpot 임베딩 갱신 -------------------------- #
    print("▶ 관광지 embedding 갱신 중...")
    tour_rows = db.query(models.TourSpot).all()
    
    # 벡터가 없는 관광지만 필터링
    tours_needing_embedding = []
    texts_for_embedding = []
    
    for tour in tour_rows:
        if tour.pref_vector is None:
            tours_needing_embedding.append(tour)
            
            # keywords 컬럼이 있으면 활용, 없으면 name + tags 사용
            if hasattr(tour, 'keywords') and tour.keywords and tour.keywords.strip():
                text_for_embedding = f"{tour.name} {tour.keywords} {tour.tags}"
            else:
                text_for_embedding = f"{tour.name} {tour.tags}"
            
            texts_for_embedding.append(text_for_embedding)
    
    print(f"   💡 임베딩이 필요한 관광지: {len(tours_needing_embedding)}개")
    
    # 배치로 임베딩 생성
    if tours_needing_embedding:
        embeddings = embed_texts(texts_for_embedding)
        
        # ORM 객체에 벡터 할당
        for tour, embedding in zip(tours_needing_embedding, embeddings):
            tour.pref_vector = embedding
    
    db.commit()
    print("✅ 관광지 임베딩 갱신 완료 (키워드 포함)")

    # ----------------- 6) 숙박·음식점 데이터 로딩 --------------------------- #
    print("▶ 숙박·음식점 데이터 로딩 중...")
    
    # 숙박 데이터
    accommodations_file = Path("data/accommodations.csv")
    if accommodations_file.exists():
        try:
            acc_df = pd.read_csv(accommodations_file)
            acc_df = acc_df.reset_index()
            acc_df = acc_df.rename(columns={'index': 'id'})
            acc_df['id'] = acc_df['id'] + 1
            upsert_from_df(acc_df, models.Accommodation, db)
            print(f"   ✅ 숙박시설: {len(acc_df)}건 로드")
        except Exception as e:
            print(f"   ⚠️ 숙박시설 로드 실패: {e}")
    else:
        print("   ❌ accommodations.csv 파일 없음")
    
    # 음식점 데이터
    restaurants_file = Path("data/restaurants.csv")
    if restaurants_file.exists():
        try:
            rest_df = pd.read_csv(restaurants_file)
            rest_df = rest_df.reset_index()
            rest_df = rest_df.rename(columns={'index': 'id'})
            rest_df['id'] = rest_df['id'] + 1
            upsert_from_df(rest_df, models.Restaurant, db)
            print(f"   ✅ 음식점: {len(rest_df)}건 로드")
        except Exception as e:
            print(f"   ⚠️ 음식점 로드 실패: {e}")
    else:
        print("   ❌ restaurants.csv 파일 없음")
    
    # 숙박·음식점 임베딩 생성
    print("▶ 숙박·음식점 임베딩 생성 중...")
    
    # 숙박시설 임베딩
    acc_rows = db.query(models.Accommodation).all()
    refresh_embeddings(db, acc_rows, attr_name="tags")
    
    # 음식점 임베딩
    rest_rows = db.query(models.Restaurant).all()
    refresh_embeddings(db, rest_rows, attr_name="tags")
    
    print("✅ 숙박·음식점 임베딩 완료")

    # ----------------- 7) 더미 사용자 선호 태그 로딩 ------------------------ #
    print("▶ 더미 사용자 선호 태그 로딩 중...")
    dummy_prefer_file = Path("data/dummy_prefer.csv")
    if dummy_prefer_file.exists():
        try:
            # 순환 import 방지를 위한 지연 import
            from app.db.crud import load_dummy_preferences
            load_dummy_preferences(db, "data/dummy_prefer.csv")
            print("✅ 더미 선호 태그 로딩 완료")
        except Exception as e:
            print(f"⚠️ 더미 선호 태그 로딩 실패: {e}")
    else:
        print("❌ dummy_prefer.csv 파일 없음 (건너뛰기)")

    # 세션 종료
    db.close()
    print("✅ DB 초기화 완료!")
