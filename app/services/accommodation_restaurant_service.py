"""
accommodation_restaurant_service.py
===================================
숙박 및 음식점 추천 서비스

최종 일정이 생성된 후 확정된 농가/관광지 위치 기반으로 
가까운 숙박시설 및 음식점을 추천하는 기능
"""

from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db import models
from app.schemas import AccommodationCard, RestaurantCard
from app.services.detail_loader import enrich_accommodation_cards, enrich_restaurant_cards
import math


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 간의 거리를 계산합니다 (단위: km)."""
    if not all([lat1, lon1, lat2, lon2]):
        return float('inf')
    
    # Haversine 공식
    R = 6371  # 지구 반지름 (km)
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat/2) * math.sin(dlat/2) + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlon/2) * math.sin(dlon/2))
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    
    return distance


def get_center_coordinates(locations: List[Tuple[float, float]]) -> Tuple[float, float]:
    """여러 위치의 중심 좌표를 계산합니다."""
    if not locations:
        return 37.5665, 126.9780  # 서울 중심부 기본값
    
    avg_lat = sum(lat for lat, lon in locations) / len(locations)
    avg_lon = sum(lon for lat, lon in locations) / len(locations)
    
    return avg_lat, avg_lon


def find_nearby_accommodations(
    db: Session,
    center_lat: float,
    center_lon: float,
    max_distance_km: float = 50.0,
    limit: int = 5
) -> List[AccommodationCard]:
    """중심 좌표 기준으로 근처 숙박시설을 찾습니다."""
    
    # PostgreSQL의 Earth distance 함수를 사용하여 거리 기반 검색
    # 서브쿼리를 사용하여 HAVING 대신 WHERE 절에서 distance 필터링
    query = text("""
        SELECT * FROM (
            SELECT *,
                   (6371 * acos(cos(radians(:center_lat)) 
                              * cos(radians(lat)) 
                              * cos(radians(lon) - radians(:center_lon)) 
                              + sin(radians(:center_lat)) 
                              * sin(radians(lat)))) as distance
            FROM accommodations 
            WHERE lat IS NOT NULL AND lon IS NOT NULL
        ) AS sub
        WHERE sub.distance <= :max_distance
        ORDER BY sub.distance ASC
        LIMIT :limit
    """)
    
    result = db.execute(query, {
        "center_lat": center_lat,
        "center_lon": center_lon, 
        "max_distance": max_distance_km,
        "limit": limit
    }).fetchall()
    
    accommodations = []
    for row in result:
        accommodations.append(AccommodationCard(
            id=row.id,
            name=row.name,
            region=row.region,
            tags=row.tags.split(',') if row.tags else [],
            lat=row.lat,
            lon=row.lon,
            image_url=row.image_url,
            distance=round(row.distance, 1),
            checkin_time=row.checkin_time,
            checkout_time=row.checkout_time,
            room_count=row.room_count,
            parking=row.parking,
            facilities=row.facilities,
            keywords=row.keywords or ""
        ))
    
    return accommodations


def find_nearby_restaurants(
    db: Session,
    center_lat: float,
    center_lon: float,
    max_distance_km: float = 30.0,
    limit: int = 5
) -> List[RestaurantCard]:
    """중심 좌표 기준으로 근처 음식점을 찾습니다."""
    
    query = text("""
        SELECT * FROM (
            SELECT *,
                   (6371 * acos(cos(radians(:center_lat)) 
                              * cos(radians(lat)) 
                              * cos(radians(lon) - radians(:center_lon)) 
                              + sin(radians(:center_lat)) 
                              * sin(radians(lat)))) as distance
            FROM restaurants 
            WHERE lat IS NOT NULL AND lon IS NOT NULL
        ) AS sub
        WHERE sub.distance <= :max_distance
        ORDER BY sub.distance ASC
        LIMIT :limit
    """)
    
    result = db.execute(query, {
        "center_lat": center_lat,
        "center_lon": center_lon,
        "max_distance": max_distance_km,
        "limit": limit
    }).fetchall()
    
    restaurants = []
    for row in result:
        restaurants.append(RestaurantCard(
            id=row.id,
            name=row.name,
            region=row.region,
            tags=row.tags.split(',') if row.tags else [],
            lat=row.lat,
            lon=row.lon,
            image_url=row.image_url,
            distance=round(row.distance, 1),
            menu=row.menu,
            open_time=row.open_time,
            rest_date=row.rest_date,
            parking=row.parking,
            reservation=row.reservation,
            packaging=row.packaging,
            keywords=row.keywords or ""
        ))
    
    return restaurants


def get_itinerary_recommendations(
    db: Session,
    job_locations: List[Tuple[float, float]],
    tour_locations: List[Tuple[float, float]]
) -> Dict[str, List[Any]]:
    """일정 기반 숙박 및 음식점 추천."""
    
    # 모든 위치를 합쳐서 중심점 계산
    all_locations = job_locations + tour_locations
    
    if not all_locations:
        return {
            "accommodations": [],
            "restaurants": []
        }
    
    center_lat, center_lon = get_center_coordinates(all_locations)
    
    # 숙박시설 추천 (반경 50km)
    accommodations = find_nearby_accommodations(
        db=db,
        center_lat=center_lat,
        center_lon=center_lon,
        max_distance_km=50.0,
        limit=5
    )
    
    # 음식점 추천 (반경 30km)
    restaurants = find_nearby_restaurants(
        db=db,
        center_lat=center_lat,
        center_lon=center_lon,
        max_distance_km=30.0,
        limit=5
    )
    
    # 실시간 상세정보 및 이미지 로드
    print(f"🔄 숙박·음식점 실시간 정보 로드 중...")
    
    # AccommodationCard 객체를 dict로 변환
    accommodations_dict = [acc.dict() for acc in accommodations]
    restaurants_dict = [rest.dict() for rest in restaurants]
    
    # 실시간 정보 추가 (최대 10개씩만)
    enriched_accommodations = enrich_accommodation_cards(accommodations_dict[:10])
    enriched_restaurants = enrich_restaurant_cards(restaurants_dict[:10])
    
    # 다시 AccommodationCard 객체로 변환
    final_accommodations = [AccommodationCard(**acc) for acc in enriched_accommodations]
    final_restaurants = [RestaurantCard(**rest) for rest in enriched_restaurants]
    
    print(f"✅ 실시간 정보 로드 완료: 숙박 {len(final_accommodations)}개, 음식점 {len(final_restaurants)}개")
    
    return {
        "accommodations": final_accommodations,
        "restaurants": final_restaurants,
        "center": {
            "lat": center_lat,
            "lon": center_lon
        }
    }


def get_location_based_recommendations(
    db: Session,
    lat: float,
    lon: float,
    accommodation_radius: float = 20.0,
    restaurant_radius: float = 10.0
) -> Dict[str, List[Any]]:
    """특정 위치 기반 숙박 및 음식점 추천."""
    
    # 숙박시설 추천
    accommodations = find_nearby_accommodations(
        db=db,
        center_lat=lat,
        center_lon=lon,
        max_distance_km=accommodation_radius,
        limit=5
    )
    
    # 음식점 추천
    restaurants = find_nearby_restaurants(
        db=db,
        center_lat=lat,
        center_lon=lon,
        max_distance_km=restaurant_radius,
        limit=5
    )
    
    return {
        "accommodations": accommodations,
        "restaurants": restaurants
    }