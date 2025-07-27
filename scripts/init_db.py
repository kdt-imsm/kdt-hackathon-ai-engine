"""
init_db.py
~~~~~~~~~~
- dummy_jobs.csv → JobPost (UPSERT: id 중복 시 UPDATE)
- tags 컬럼만 변경된 레코드만 임베딩 재계산
"""

from pathlib import Path
import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, Base, engine
from app.db import models
from app.embeddings.embedding_service import embed_texts

CSV_JOBS = Path("data/dummy_jobs.csv")

# ──────────────────────────────────────────────────────────
def upsert_from_df(df: pd.DataFrame, model):
    """
    DataFrame → UPSERT (id 중복 시 UPDATE)
    """
    records = df.to_dict("records")

    # ① insert_stmt 먼저 생성
    insert_stmt = insert(model).values(records)

    # ② insert_stmt.excluded 를 사용해 update dict 작성
    update_cols = {
        c: getattr(insert_stmt.excluded, c)  # ← 여기서 참조
        for c in df.columns
        if c != "id"
    }

    # ③ 최종 UPSERT 문 구성
    stmt = insert_stmt.on_conflict_do_update(
        index_elements=["id"],
        set_=update_cols,
    )

    db.execute(stmt)
    db.commit()



def refresh_embeddings(rows, attr_name="tags"):
    # pref_vector 가 아직 저장되지 않은(==None) 행만 임베딩 계산
    needs_update = [r for r in rows if r.pref_vector is None]
    if not needs_update:
        return

    embeds = embed_texts([getattr(r, attr_name) for r in needs_update])
    for obj, vec in zip(needs_update, embeds):
        obj.pref_vector = vec
    db.commit()


# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    # 1) JobPost UPSERT
    jobs_df = pd.read_csv(CSV_JOBS)
    upsert_from_df(jobs_df, models.JobPost)

    # 2) TourSpot 는 TourAPI 로더에서 이미 UPSERT + 임베딩 처리

    # 3) 임베딩 갱신(필요한 행만)
    refresh_embeddings(db.query(models.JobPost).all())
    refresh_embeddings(db.query(models.TourSpot).all())

    print("✅ init_db 완료: JobPost UPSERT + 임베딩 최신화")
