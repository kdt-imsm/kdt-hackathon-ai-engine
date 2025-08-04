"""
app/recommendation/vector_store.py
==================================
pgvector를 활용한 **코사인 유사도 기반 벡터 검색** 헬퍼

* 기능
  1. ``search_jobs``  : 사용자 벡터 ↔ JobPost.pref_vector 유사도 상위 N개 조회
  2. ``search_tours`` : 사용자 벡터 ↔ TourSpot.pref_vector 유사도 상위 N개 조회
  3. ``search_jobs_with_location`` : 위치 기반 필터링과 벡터 유사도를 결합한 검색
  4. ``search_tours_with_location`` : 위치 기반 필터링과 벡터 유사도를 결합한 검색

* 구현 방식
  - PostgreSQL + pgvector 연산자 ``<#>`` (inner product/cosine distance) 사용
  - *1 - distance* 로 스코어를 변환하여 1에 가까울수록 유사도가 높음
  - 위치 필터링 시 거리 계산과 벡터 유사도를 결합한 복합 점수 사용
  - 결과는 `(ORM 객체, score)` 튜플 리스트 형태로 반환해 추후 랭킹·필터링에 활용

주의
----
이 모듈은 단일 SQL 쿼리로 벡터 검색을 수행하므로, 대규모 트래픽 환경에서는
별도의 벡터 DB(예: **Pinecone**, **Weaviate**) 도입을 고려해야 합니다.
"""

from typing import Optional, Tuple, List
from sqlalchemy import text  # RAW SQL 실행용
from app.db.database import SessionLocal
from app.config import get_settings
from app.utils.location import get_location_coords, calculate_distance, calculate_location_score

settings = get_settings()  # .env → Settings 싱글턴


# 내부 전용 RAW 쿼리 실행 핸들러 -------------------------------------------

def _query(sql: str, vec: list[float], lim: int):
    """Parameterized RAW SQL 실행 후 Row 객체 리스트 반환."""
    with SessionLocal() as db:
        return db.execute(text(sql), {"uvec": vec, "lim": lim}).all()


def _query_with_location(sql: str, vec: list[float], lat: float, lon: float, lim: int):
    """위치 파라미터를 포함한 RAW SQL 실행."""
    with SessionLocal() as db:
        return db.execute(text(sql), {"uvec": vec, "lat": lat, "lon": lon, "lim": lim}).all()


# ─────────────────────────────────────────────────────────────
# JobPost 벡터 검색 -------------------------------------------------------
# ─────────────────────────────────────────────────────────────

def search_jobs(user_vec, limit=None):
    """JobPost 테이블에서 코사인 유사도 상위 *limit*건 조회.

    Returns
    -------
    list[tuple[JobPost, float]]
        (ORM 인스턴스, score) 튜플 리스트.
    """
    if limit is None:
        limit = settings.max_results  # 설정에 없으면 AttributeError 발생 가능

    sql = """
    SELECT *, 1 - (pref_vector <#> CAST(:uvec AS vector)) AS score
    FROM jobs
    WHERE pref_vector IS NOT NULL
    ORDER BY pref_vector <#> CAST(:uvec AS vector)
    LIMIT :lim
    """

    rows = _query(sql, user_vec, limit)

    # 벡터가 없는 경우 fallback: 최신 레코드 반환
    if not rows:
        fallback_sql = """
        SELECT *, 0.5 AS score
        FROM jobs
        ORDER BY id DESC
        LIMIT :lim
        """
        rows = _query(fallback_sql, user_vec, limit)

    from app.db.models import JobPost  # 순환 import 방지용 지연 import
    results = []
    for row in rows:
        data = row._mapping  # RowMapping
        # Row → ORM 객체로 매핑 (편의상 새 인스턴스 생성)
        job = JobPost(**{col.name: data[col.name] for col in JobPost.__table__.columns})
        score = data.get("score")
        results.append((job, score))
    return results


def search_jobs_with_location(
    user_vec, 
    user_coords: Optional[Tuple[float, float]] = None,
    max_distance_km: float = 100.0,
    location_weight: float = 0.3,
    limit=None
):
    """
    위치 기반 필터링과 벡터 유사도를 결합한 JobPost 검색.
    
    Parameters
    ----------
    user_vec : list[float]
        사용자 선호도 벡터
    user_coords : Optional[Tuple[float, float]]
        사용자 위치 (위도, 경도). None이면 위치 필터링 없음
    max_distance_km : float, default=100.0
        최대 검색 거리 (km)
    location_weight : float, default=0.3
        위치 점수 가중치 (0.0~1.0)
    limit : int, optional
        반환할 최대 결과 수
        
    Returns
    -------
    list[tuple[JobPost, float]]
        (ORM 인스턴스, 복합 점수) 튜플 리스트
    """
    if limit is None:
        limit = getattr(settings, 'max_results', 20)
        
    # 위치 필터링이 없는 경우 기본 벡터 검색 사용
    if user_coords is None:
        return search_jobs(user_vec, limit)
    
    user_lat, user_lon = user_coords
    
    # 모든 결과를 가져와서 Python에서 필터링 (PostGIS 없이도 동작)
    all_jobs = search_jobs(user_vec, limit * 3)
    results = []
    
    for job, vector_score in all_jobs:
        if job.lat is None or job.lon is None:
            continue
            
        distance = calculate_distance(user_lat, user_lon, job.lat, job.lon)
        if distance <= max_distance_km:
            location_score = calculate_location_score(distance, max_distance_km)
            # 복합 점수 계산: 벡터 유사도 + 위치 점수
            combined_score = (1 - location_weight) * vector_score + location_weight * location_score
            results.append((job, combined_score))
    
    # 복합 점수로 정렬하고 상위 limit개 반환
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]


def search_jobs_guaranteed(
    user_vec, 
    user_coords: Optional[Tuple[float, float]] = None,
    user_regions: Optional[List[str]] = None,
    target_count: int = 10,
    max_distance_km: float = 100.0,
    location_weight: float = 0.4
):
    """
    정확히 target_count 개의 일거리를 보장하는 검색 함수.
    사용자가 지역을 지정한 경우 해당 지역 내 결과를 우선 검색합니다.
    
    Parameters
    ----------
    user_vec : list[float]
        사용자 선호도 벡터
    user_coords : Optional[Tuple[float, float]]
        사용자 위치 (위도, 경도)
    user_regions : Optional[List[str]]
        사용자 지정 지역 리스트 (예: ["전북 고창"])
    target_count : int, default=10
        반환할 정확한 결과 개수
    max_distance_km : float, default=100.0
        초기 최대 검색 거리 (km)
    location_weight : float, default=0.4
        위치 점수 가중치
        
    Returns
    -------
    list[tuple[JobPost, float]]
        정확히 target_count 개의 (일거리, 점수) 튜플 리스트
    """
    from app.utils.location import get_progressive_region_patterns, match_region_strict
    
    # 지역 기반 단계별 검색
    if user_regions:
        expansion_patterns = get_progressive_region_patterns(user_regions)
        print(f"지역 확장 패턴: {expansion_patterns}")
        
        accumulated_results = []
        existing_ids = set()
        
        for region_pattern, region_weight, _ in expansion_patterns:
            print(f"지역 '{region_pattern}' 검색 중...")
            
            # 해당 지역 내에서 벡터 검색
            region_results = search_jobs_by_region(
                user_vec, region_pattern, user_coords, 
                max_distance_km, location_weight, target_count * 2
            )
            
            # 중복 제거하면서 결과 누적
            for job, score in region_results:
                if job.id not in existing_ids:
                    accumulated_results.append((job, score * region_weight))
                    existing_ids.add(job.id)
            
            print(f"지역 '{region_pattern}'에서 {len(region_results)}개 발견, 누적: {len(accumulated_results)}개")
            
            if len(accumulated_results) >= target_count:
                # 점수순 정렬 후 반환
                accumulated_results.sort(key=lambda x: x[1], reverse=True)
                return accumulated_results[:target_count]
        
        # 지역 검색 결과가 부족한 경우
        if accumulated_results:
            needed_count = target_count - len(accumulated_results)
            print(f"지역 검색으로 {len(accumulated_results)}개 확보, {needed_count}개 더 필요")
            
            # 전국 검색으로 보완
            additional_results = search_jobs(user_vec, target_count * 3)
            for job, score in additional_results:
                if job.id not in existing_ids:
                    accumulated_results.append((job, score * 0.3))  # 지역 외 결과는 점수 낮게
                    needed_count -= 1
                    if needed_count <= 0:
                        break
            
            accumulated_results.sort(key=lambda x: x[1], reverse=True)
            return accumulated_results[:target_count]
    # 1단계: 위치 기반 검색 시도
    if user_coords is not None:
        results = search_jobs_with_location(
            user_vec, user_coords, max_distance_km, location_weight, target_count
        )
        
        if len(results) >= target_count:
            return results[:target_count]
        
        # 부족한 경우 거리 제한을 2배로 확장
        extended_results = search_jobs_with_location(
            user_vec, user_coords, max_distance_km * 2, location_weight, target_count * 2
        )
        
        if len(extended_results) >= target_count:
            return extended_results[:target_count]
        
        # 여전히 부족한 경우 기존 결과 보존하고 추가 검색
        existing_ids = {job.id for job, _ in extended_results}
        needed_count = target_count - len(extended_results)
    else:
        extended_results = []
        existing_ids = set()
        needed_count = target_count
    
    # 2단계: 위치 제한 없는 벡터 유사도만으로 보완
    all_results = search_jobs(user_vec, target_count * 3)
    additional_results = []
    
    for job, score in all_results:
        if job.id not in existing_ids:
            additional_results.append((job, score))
            if len(additional_results) >= needed_count:
                break
    
    # 3단계: 결과 결합 및 정렬
    final_results = list(extended_results) + additional_results[:needed_count]
    
    # 4단계: 여전히 부족한 경우 최후 수단
    if len(final_results) < target_count:
        # 전체 데이터베이스에서 랜덤 선택으로 채우기
        with SessionLocal() as db:
            from app.db.models import JobPost
            existing_job_ids = {job.id for job, _ in final_results}
            
            remaining_jobs = db.query(JobPost).filter(
                ~JobPost.id.in_(existing_job_ids)
            ).limit(target_count - len(final_results)).all()
            
            for job in remaining_jobs:
                final_results.append((job, 0.1))  # 최소 점수
    
    return final_results[:target_count]


def search_jobs_by_region(
    user_vec,
    region_pattern: str,
    user_coords: Optional[Tuple[float, float]] = None,
    max_distance_km: float = 100.0,
    location_weight: float = 0.4,
    limit: int = 10
):
    """
    특정 지역 패턴에 해당하는 일거리를 벡터 유사도로 검색합니다.
    지역 매칭과 거리 기반 필터링을 모두 적용합니다.
    """
    from app.utils.location import is_region_match, calculate_distance, calculate_location_score
    
    print(f"🔍 일거리 지역 검색: '{region_pattern}' (최대거리: {max_distance_km}km)")
    
    # 모든 일거리를 가져와서 지역 필터링
    all_results = search_jobs(user_vec, limit * 10)  # 더 많이 가져와서 필터링
    
    region_filtered = []
    distance_filtered = []
    
    for job, score in all_results:
        # 1단계: 지역 매칭 확인
        is_match, region_score = is_region_match(job.region, [region_pattern])
        
        if is_match:
            # 지역 매칭 성공 시 강력한 부스트 적용
            region_boost = 2.0 * region_score
            boosted_score = score + region_boost
            region_filtered.append((job, boosted_score))
            
            # 2단계: 거리 기반 추가 필터링 (좌표가 있는 경우)
            if user_coords and job.lat and job.lon:
                user_lat, user_lon = user_coords
                distance = calculate_distance(user_lat, user_lon, job.lat, job.lon)
                
                if distance <= max_distance_km:
                    location_score = calculate_location_score(distance, max_distance_km)
                    final_score = boosted_score * (1 - location_weight) + location_score * location_weight
                    distance_filtered.append((job, final_score, distance))
                    print(f"  ✅ {job.title} ({job.region}) - 거리: {distance:.1f}km, 점수: {final_score:.3f}")
    
    print(f"📊 필터링 결과: 지역매칭 {len(region_filtered)}개 → 거리필터링 {len(distance_filtered)}개")
    
    # 거리 필터링된 결과가 있으면 우선 사용
    if distance_filtered:
        distance_filtered.sort(key=lambda x: x[1], reverse=True)
        return [(job, score) for job, score, _ in distance_filtered[:limit]]
    
    # 거리 필터링 결과가 없으면 지역 매칭 결과만 사용
    region_filtered.sort(key=lambda x: x[1], reverse=True)
    return region_filtered[:limit]


# ─────────────────────────────────────────────────────────────
# TourSpot 벡터 검색 ------------------------------------------------------
# ─────────────────────────────────────────────────────────────

def search_tours(user_vec, limit=None):
    """TourSpot 테이블에서 코사인 유사도 상위 *limit*건 조회."""
    if limit is None:
        limit = settings.max_results

    sql = """
    SELECT *, 1 - (pref_vector <#> CAST(:uvec AS vector)) AS score
    FROM tour_spots
    WHERE pref_vector IS NOT NULL
    ORDER BY pref_vector <#> CAST(:uvec AS vector)
    LIMIT :lim
    """

    rows = _query(sql, user_vec, limit)

    # 벡터가 없는 경우 fallback: 최신 레코드 반환
    if not rows:
        fallback_sql = """
        SELECT *, 0.5 AS score
        FROM tour_spots
        ORDER BY id DESC
        LIMIT :lim
        """
        rows = _query(fallback_sql, user_vec, limit)

    from app.db.models import TourSpot
    results = []
    for row in rows:
        data = row._mapping
        tour = TourSpot(**{col.name: data[col.name] for col in TourSpot.__table__.columns})
        score = data.get("score")
        results.append((tour, score))
    return results


def search_tours_with_location(
    user_vec, 
    user_coords: Optional[Tuple[float, float]] = None,
    max_distance_km: float = 100.0,
    location_weight: float = 0.3,
    limit=None
):
    """
    위치 기반 필터링과 벡터 유사도를 결합한 TourSpot 검색.
    
    Parameters는 search_jobs_with_location과 동일.
    """
    if limit is None:
        limit = getattr(settings, 'max_results', 20)
        
    # 위치 필터링이 없는 경우 기본 벡터 검색 사용
    if user_coords is None:
        return search_tours(user_vec, limit)
    
    user_lat, user_lon = user_coords
    
    # 모든 결과를 가져와서 Python에서 필터링
    all_tours = search_tours(user_vec, limit * 3)
    results = []
    
    for tour, vector_score in all_tours:
        if tour.lat is None or tour.lon is None:
            continue
            
        distance = calculate_distance(user_lat, user_lon, tour.lat, tour.lon)
        if distance <= max_distance_km:
            location_score = calculate_location_score(distance, max_distance_km)
            combined_score = (1 - location_weight) * vector_score + location_weight * location_score
            results.append((tour, combined_score))
    
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]


def search_tours_guaranteed(
    user_vec, 
    user_coords: Optional[Tuple[float, float]] = None,
    user_regions: Optional[List[str]] = None,
    target_count: int = 10,
    max_distance_km: float = 100.0,
    location_weight: float = 0.4
):
    """
    정확히 target_count 개의 관광지를 보장하는 검색 함수.
    사용자가 지역을 지정한 경우 해당 지역 내 결과를 우선 검색합니다.
    """
    from app.utils.location import get_progressive_region_patterns, match_region_strict
    
    # 지역 기반 단계별 검색
    if user_regions:
        expansion_patterns = get_progressive_region_patterns(user_regions)
        
        accumulated_results = []
        existing_ids = set()
        
        for region_pattern, region_weight, _ in expansion_patterns:
            # 해당 지역 내에서 관광지 검색
            region_results = search_tours_by_region(
                user_vec, region_pattern, user_coords, 
                max_distance_km, location_weight, target_count * 2
            )
            
            # 중복 제거하면서 결과 누적
            for tour, score in region_results:
                if tour.id not in existing_ids:
                    accumulated_results.append((tour, score * region_weight))
                    existing_ids.add(tour.id)
            
            if len(accumulated_results) >= target_count:
                # 점수순 정렬 후 반환
                accumulated_results.sort(key=lambda x: x[1], reverse=True)
                return accumulated_results[:target_count]
        
        # 지역 검색 결과가 부족한 경우 전국 검색으로 보완
        if accumulated_results:
            needed_count = target_count - len(accumulated_results)
            additional_results = search_tours(user_vec, target_count * 3)
            for tour, score in additional_results:
                if tour.id not in existing_ids:
                    accumulated_results.append((tour, score * 0.3))
                    needed_count -= 1
                    if needed_count <= 0:
                        break
            
            accumulated_results.sort(key=lambda x: x[1], reverse=True)
            return accumulated_results[:target_count]
    # 1단계: 위치 기반 검색 시도
    if user_coords is not None:
        results = search_tours_with_location(
            user_vec, user_coords, max_distance_km, location_weight, target_count
        )
        
        if len(results) >= target_count:
            return results[:target_count]
        
        # 부족한 경우 거리 제한을 2배로 확장
        extended_results = search_tours_with_location(
            user_vec, user_coords, max_distance_km * 2, location_weight, target_count * 2
        )
        
        if len(extended_results) >= target_count:
            return extended_results[:target_count]
        
        # 여전히 부족한 경우 기존 결과 보존하고 추가 검색
        existing_ids = {tour.id for tour, _ in extended_results}
        needed_count = target_count - len(extended_results)
    else:
        extended_results = []
        existing_ids = set()
        needed_count = target_count
    
    # 2단계: 위치 제한 없는 벡터 유사도만으로 보완
    all_results = search_tours(user_vec, target_count * 3)
    additional_results = []
    
    for tour, score in all_results:
        if tour.id not in existing_ids:
            additional_results.append((tour, score))
            if len(additional_results) >= needed_count:
                break
    
    # 3단계: 결과 결합 및 정렬
    final_results = list(extended_results) + additional_results[:needed_count]
    
    # 4단계: 여전히 부족한 경우 최후 수단
    if len(final_results) < target_count:
        # 전체 데이터베이스에서 랜덤 선택으로 채우기
        with SessionLocal() as db:
            from app.db.models import TourSpot
            existing_tour_ids = {tour.id for tour, _ in final_results}
            
            remaining_tours = db.query(TourSpot).filter(
                ~TourSpot.id.in_(existing_tour_ids)
            ).limit(target_count - len(final_results)).all()
            
            for tour in remaining_tours:
                final_results.append((tour, 0.1))  # 최소 점수
    
    return final_results[:target_count]


def search_tours_by_region(
    user_vec,
    region_pattern: str,
    user_coords: Optional[Tuple[float, float]] = None,
    max_distance_km: float = 100.0,
    location_weight: float = 0.4,
    limit: int = 10
):
    """
    특정 지역 패턴에 해당하는 관광지를 벡터 유사도로 검색합니다.
    지역 매칭과 거리 기반 필터링을 모두 적용합니다.
    """
    from app.utils.location import is_region_match, calculate_distance, calculate_location_score
    
    print(f"🔍 관광지 지역 검색: '{region_pattern}' (최대거리: {max_distance_km}km)")
    
    # 모든 관광지를 가져와서 지역 필터링
    all_results = search_tours(user_vec, limit * 10)  # 더 많이 가져와서 필터링
    
    region_filtered = []
    distance_filtered = []
    
    for tour, score in all_results:
        # 1단계: 지역 매칭 확인
        is_match, region_score = is_region_match(tour.region, [region_pattern])
        
        if is_match:
            # 지역 매칭 성공 시 강력한 부스트 적용
            region_boost = 2.0 * region_score
            boosted_score = score + region_boost
            region_filtered.append((tour, boosted_score))
            
            # 2단계: 거리 기반 추가 필터링 (좌표가 있는 경우)
            if user_coords and tour.lat and tour.lon:
                user_lat, user_lon = user_coords
                distance = calculate_distance(user_lat, user_lon, tour.lat, tour.lon)
                
                if distance <= max_distance_km:
                    location_score = calculate_location_score(distance, max_distance_km)
                    final_score = boosted_score * (1 - location_weight) + location_score * location_weight
                    distance_filtered.append((tour, final_score, distance))
                    print(f"  ✅ {tour.name} ({tour.region}) - 거리: {distance:.1f}km, 점수: {final_score:.3f}")
    
    print(f"📊 필터링 결과: 지역매칭 {len(region_filtered)}개 → 거리필터링 {len(distance_filtered)}개")
    
    # 거리 필터링된 결과가 있으면 우선 사용
    if distance_filtered:
        # 점수순 정렬
        distance_filtered.sort(key=lambda x: x[1], reverse=True)
        return [(tour, score) for tour, score, _ in distance_filtered[:limit]]
    
    # 거리 필터링 결과가 없으면 지역 매칭 결과만 사용
    region_filtered.sort(key=lambda x: x[1], reverse=True)
    return region_filtered[:limit]
def search_jobs_region_first(
    user_vec, 
    user_regions: List[str],
    user_coords: Optional[Tuple[float, float]] = None,
    target_count: int = 10,
    max_distance_km: float = 100.0,
    location_weight: float = 0.4
):
    """
    지역을 최우선으로 하는 검색 함수.
    지역 데이터를 먼저 추출한 후, 해당 범위 내에서만 벡터 검색을 수행합니다.
    """
    from app.utils.location import get_progressive_region_patterns
    
    print(f"🎯 지역 우선 일거리 검색 시작")
    print(f"   📍 대상 지역: {user_regions}")
    print(f"   📊 목표 개수: {target_count}개")
    print(f"   📏 최대 거리: {max_distance_km}km")
    print(f"   🎚️ 위치 가중치: {location_weight}")
    if user_coords:
        print(f"   🗺️ 사용자 좌표: {user_coords}")
    
    expansion_patterns = get_progressive_region_patterns(user_regions)
    print(f"   🔄 확장 패턴: {expansion_patterns}")
    
    accumulated_results = []
    existing_ids = set()
    
    for i, (region_pattern, region_weight, description) in enumerate(expansion_patterns, 1):
        print(f"\n📍 [{i}/{len(expansion_patterns)}] '{region_pattern}' ({description})")
        print(f"   ⚖️ 지역 가중치: {region_weight}")
        
        # 해당 지역 내에서 벡터 검색
        region_results = search_jobs_by_region(
            user_vec, region_pattern, user_coords, 
            max_distance_km, location_weight, target_count * 3
        )
        
        # 중복 제거하면서 결과 누적
        new_results = 0
        for job, score in region_results:
            if job.id not in existing_ids:
                # 지역별 가중치 적용 (정확한 지역일수록 높은 가중치)
                final_score = score * region_weight
                accumulated_results.append((job, final_score))
                existing_ids.add(job.id)
                new_results += 1
        
        print(f"   ✅ 새로 발견: {new_results}개 (중복 제외)")
        print(f"   📈 누적 결과: {len(accumulated_results)}개")
        
        # 충분한 결과를 얻었으면 중단
        if len(accumulated_results) >= target_count:
            print(f"   🎊 목표 달성! ({target_count}개 이상 확보)")
            break
    
    # 결과가 부족한 경우에만 전국 검색으로 보완
    if len(accumulated_results) < target_count:
        needed = target_count - len(accumulated_results)
        print(f"\n🌍 전국 검색으로 {needed}개 추가 검색...")
        
        nationwide_results = search_jobs(user_vec, target_count * 2)
        added = 0
        for job, score in nationwide_results:
            if job.id not in existing_ids:
                # 전국 검색 결과는 낮은 가중치 적용
                final_score = score * 0.3
                accumulated_results.append((job, final_score))
                added += 1
                if added >= needed:
                    break
        
        print(f"   ➕ 전국 검색으로 {added}개 추가")
    
    # 점수순 정렬 후 반환
    accumulated_results.sort(key=lambda x: x[1], reverse=True)
    final_results = accumulated_results[:target_count]
    
    print(f"\n🏆 최종 일거리 결과: {len(final_results)}개")
    print("   📋 상위 결과:")
    for i, (job, score) in enumerate(final_results[:5], 1):
        distance_info = ""
        if user_coords and job.lat and job.lon:
            from app.utils.location import calculate_distance
            distance = calculate_distance(user_coords[0], user_coords[1], job.lat, job.lon)
            distance_info = f" (거리: {distance:.1f}km)"
        print(f"      {i}. {job.title} ({job.region}) - 점수: {score:.3f}{distance_info}")
    
    return final_results


def search_tours_matching_jobs(
    user_vec,
    job_regions: List[str],
    user_coords: Optional[Tuple[float, float]] = None,
    max_distance_km: float = 50.0,
    location_weight: float = 0.3
):
    """
    일거리 지역과 1:1 매칭되는 관광지를 검색합니다.
    각 일거리 지역별로 관광지 1개씩 반환하여 총 len(job_regions)개 반환.
    순서 보장을 위해 더 정교한 매칭 로직을 사용합니다.
    
    Parameters
    ----------
    user_vec : list[float]
        사용자 선호도 벡터
    job_regions : List[str]
        일거리 지역 리스트 (순서대로 매칭)
    user_coords : Optional[Tuple[float, float]]
        사용자 위치 (위도, 경도)
    max_distance_km : float, default=50.0
        최대 검색 거리 (km)
    location_weight : float, default=0.3
        위치 점수 가중치
        
    Returns
    -------
    List[Tuple[TourSpot, float]]
        일거리 순서와 동일한 순서의 (관광지, 점수) 튜플 리스트
    """
    from app.utils.location import is_region_match, get_similar_regions
    
    print(f"🎯 일거리 지역 순서 매칭 시작: {len(job_regions)}개 지역")
    print(f"   📋 일거리 지역 순서: {job_regions}")
    
    # 1단계: 전체 관광지 풀을 미리 가져오기 (더 많은 후보 확보)
    all_tours = search_tours(user_vec, limit=100)  # 충분한 후보 확보
    print(f"   🏞️ 전체 관광지 후보: {len(all_tours)}개")
    
    # 2단계: 지역별 관광지 그룹화 (다양한 매칭 전략 사용)
    region_tour_map = {}
    unmatched_tours = []
    
    for tour, score in all_tours:
        tour_region = getattr(tour, 'region', '')
        if not tour_region:
            unmatched_tours.append((tour, score))
            continue
            
        # 각 일거리 지역과의 매칭 점수 계산
        best_match_region = None
        best_match_score = 0
        
        for job_region in job_regions:
            if not job_region:
                continue
                
            # 매칭 점수 계산 (더 정교한 전략 조합)
            match_score = 0
            
            # is_region_match 함수를 사용하여 정확한 매칭 확인
            is_match, region_match_score = is_region_match(tour_region, [job_region])
            
            if is_match:
                match_score = region_match_score
            else:
                # 추가 매칭 전략 - 더 엄격한 기준 적용
                # 1) 시/도 약어 매칭 (예: "경기" vs "경기도")
                from app.utils.location import extract_sido
                job_sido = extract_sido(job_region)
                tour_sido = extract_sido(tour_region)
                
                if job_sido and tour_sido and job_sido == tour_sido:
                    match_score = 0.7  # 같은 시도면 높은 점수
                # 2) 인접 지역 매칭 (더 제한적으로)
                elif job_sido and tour_sido and tour_sido in get_similar_regions(job_sido):
                    match_score = 0.3  # 인접 지역은 낮은 점수
            
            if match_score > best_match_score:
                best_match_score = match_score
                best_match_region = job_region
        
        # 가장 잘 매칭되는 지역에 관광지 추가 (더 엄격한 임계값)
        if best_match_region and best_match_score > 0.5:  # 높은 매칭 임계값으로 정확도 향상
            if best_match_region not in region_tour_map:
                region_tour_map[best_match_region] = []
            # 매칭 점수를 반영한 보정된 점수
            boosted_score = score + (best_match_score * 2.0)
            region_tour_map[best_match_region].append((tour, boosted_score, best_match_score))
        else:
            unmatched_tours.append((tour, score))
    
    # 각 지역별 관광지를 점수순으로 정렬
    for region in region_tour_map:
        region_tour_map[region].sort(key=lambda x: x[1], reverse=True)
    
    print(f"   📊 지역별 관광지 분포:")
    for region, tours in region_tour_map.items():
        print(f"      {region}: {len(tours)}개")
    print(f"   🔍 매칭되지 않은 관광지: {len(unmatched_tours)}개")
    
    # 3단계: 일거리 순서대로 관광지 할당
    results = []
    used_tour_ids = set()
    
    for i, job_region in enumerate(job_regions):
        print(f"\n🎯 [{i+1}/{len(job_regions)}] '{job_region}' → 관광지 매칭")
        
        if not job_region:
            print(f"   ❌ 지역 정보 없음")
            results.append(None)
            continue
        
        selected_tour = None
        
        # 해당 지역에서 아직 사용되지 않은 최고 점수 관광지 찾기
        if job_region in region_tour_map:
            for tour, boosted_score, match_score in region_tour_map[job_region]:
                if tour.id not in used_tour_ids:
                    selected_tour = (tour, boosted_score)
                    used_tour_ids.add(tour.id)
                    print(f"   ✅ 지역 매칭: {tour.name} ({tour.region}) - 매칭도: {match_score:.2f}, 점수: {boosted_score:.3f}")
                    break
        
        # 지역 매칭이 실패한 경우 인접 지역에서 찾기
        if not selected_tour:
            print(f"   🔍 '{job_region}' 직접 매칭 실패, 인접 지역 검색...")
            similar_regions = get_similar_regions(job_region)
            
            for similar_region in similar_regions:
                if similar_region in region_tour_map:
                    for tour, boosted_score, match_score in region_tour_map[similar_region]:
                        if tour.id not in used_tour_ids:
                            selected_tour = (tour, boosted_score * 0.7)  # 인접 지역 패널티
                            used_tour_ids.add(tour.id)
                            print(f"   ✅ 인접 지역 매칭: {tour.name} ({tour.region}) - 점수: {boosted_score * 0.7:.3f}")
                            break
                if selected_tour:
                    break
        
        # 여전히 매칭되지 않은 경우 매칭되지 않은 관광지에서 선택
        if not selected_tour and unmatched_tours:
            for tour, score in unmatched_tours:
                if tour.id not in used_tour_ids:
                    selected_tour = (tour, score * 0.5)  # 매칭되지 않은 관광지 패널티
                    used_tour_ids.add(tour.id)
                    print(f"   ✅ 전국 대체: {tour.name} ({getattr(tour, 'region', '정보없음')}) - 점수: {score * 0.5:.3f}")
                    break
        
        if selected_tour:
            results.append(selected_tour)
        else:
            print(f"   ❌ 매칭 실패: 사용 가능한 관광지 없음")
            results.append(None)
    
    # None 값 제거
    final_results = [tour for tour in results if tour is not None]
    
    # 매칭 성공률 계산
    successful_matches = len([r for r in results if r is not None])
    match_rate = (successful_matches / len(job_regions)) * 100 if job_regions else 0
    
    print(f"\n🏆 최종 순서 매칭 결과:")
    print(f"   📊 성공률: {match_rate:.1f}% ({successful_matches}/{len(job_regions)})")
    print(f"   📋 반환 관광지: {len(final_results)}개")
    
    # 매칭 결과 상세 로그
    for i, (job_region, result) in enumerate(zip(job_regions, results)):
        if result:
            tour, score = result
            print(f"   {i+1}. {job_region} → {tour.name} ({getattr(tour, 'region', '정보없음')})")
        else:
            print(f"   {i+1}. {job_region} → 매칭 실패")
    
    return final_results


def search_tours_region_first(
    user_vec, 
    user_regions: List[str],
    user_coords: Optional[Tuple[float, float]] = None,
    target_count: int = 10,
    max_distance_km: float = 100.0,
    location_weight: float = 0.4
):
    """
    지역을 최우선으로 하는 관광지 검색 함수.
    """
    from app.utils.location import get_progressive_region_patterns
    
    print(f"🎯 지역 우선 관광지 검색 시작")
    print(f"   📍 대상 지역: {user_regions}")
    print(f"   📊 목표 개수: {target_count}개")
    print(f"   📏 최대 거리: {max_distance_km}km")
    print(f"   🎚️ 위치 가중치: {location_weight}")
    if user_coords:
        print(f"   🗺️ 사용자 좌표: {user_coords}")
    
    expansion_patterns = get_progressive_region_patterns(user_regions)
    print(f"   🔄 확장 패턴: {expansion_patterns}")
    
    accumulated_results = []
    existing_ids = set()
    
    for i, (region_pattern, region_weight, description) in enumerate(expansion_patterns, 1):
        print(f"\n📍 [{i}/{len(expansion_patterns)}] '{region_pattern}' 관광지 ({description})")
        print(f"   ⚖️ 지역 가중치: {region_weight}")
        
        region_results = search_tours_by_region(
            user_vec, region_pattern, user_coords, 
            max_distance_km, location_weight, target_count * 3
        )
        
        new_results = 0
        for tour, score in region_results:
            if tour.id not in existing_ids:
                final_score = score * region_weight
                accumulated_results.append((tour, final_score))
                existing_ids.add(tour.id)
                new_results += 1
        
        print(f"   ✅ 새로 발견: {new_results}개 (중복 제외)")
        print(f"   📈 누적 결과: {len(accumulated_results)}개")
        
        if len(accumulated_results) >= target_count:
            print(f"   🎊 목표 달성! ({target_count}개 이상 확보)")
            break
    
    # 결과가 부족한 경우 전국 검색으로 보완
    if len(accumulated_results) < target_count:
        needed = target_count - len(accumulated_results)
        print(f"\n🌍 관광지 전국 검색으로 {needed}개 추가...")
        
        nationwide_results = search_tours(user_vec, target_count * 2)
        added = 0
        for tour, score in nationwide_results:
            if tour.id not in existing_ids:
                final_score = score * 0.3
                accumulated_results.append((tour, final_score))
                added += 1
                if added >= needed:
                    break
        
        print(f"   ➕ 전국 검색으로 {added}개 추가")
    
    accumulated_results.sort(key=lambda x: x[1], reverse=True)
    final_results = accumulated_results[:target_count]
    
    print(f"\n🏆 최종 관광지 결과: {len(final_results)}개")
    print("   📋 상위 결과:")
    for i, (tour, score) in enumerate(final_results[:5], 1):
        distance_info = ""
        if user_coords and tour.lat and tour.lon:
            from app.utils.location import calculate_distance
            distance = calculate_distance(user_coords[0], user_coords[1], tour.lat, tour.lon)
            distance_info = f" (거리: {distance:.1f}km)"
        print(f"      {i}. {tour.name} ({tour.region}) - 점수: {score:.3f}{distance_info}")
    
    return final_results