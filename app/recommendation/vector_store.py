"""
vector_store.py
~~~~~~~~~~~~~~~
pgvector 기반 벡터 검색 헬퍼.
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Sequence


def search_similar_content(
    db: Session,
    user_vec: Sequence[float],
    table: str,
    k: int = 20,
    extra_filter_sql: str = ""
):
    """
    :param table: "job_posts" 또는 "tour_spots"
    :return: (id, distance, title/name) 리스트
    """
    # L2 거리 유사도 예시
    sql = text(f"""
        SELECT id,
               ({user_vec}) <-> pref_vector AS distance,
               title_or_name
        FROM (
            SELECT id,
                   { 'title' if table == 'job_posts' else 'name' } AS title_or_name,
                   -- 가정 : 임베딩 열 pref_vector 를 미리 채워둠
                   pref_vector
            FROM {table}
            {extra_filter_sql}
        ) sub
        ORDER BY distance ASC
        LIMIT :k
    """)
    res = db.execute(sql, {"k": k}).fetchall()
    return res
