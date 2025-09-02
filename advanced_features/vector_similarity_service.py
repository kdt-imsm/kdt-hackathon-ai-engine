"""
벡터 유사도 기반 관광지/농가 추천 서비스
PostgreSQL + pgvector를 활용한 의미적 검색 시스템

주요 기능:
1. 사용자 자연어를 벡터로 변환
2. 관광지 벡터와 코사인 유사도 계산
3. 유사도 기반 추천 결과 반환
"""

import numpy as np
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.models import TourSpot, JobPost, User
from app.embeddings.embedding_service import embed_text, embed_texts
from app.config import get_settings

class VectorSimilarityService:
    """벡터 유사도 기반 추천 서비스"""
    
    def __init__(self):
        self.settings = get_settings()
    
    def calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        두 벡터 간의 코사인 유사도 계산
        
        Args:
            vec1: 첫 번째 벡터 (1536차원)
            vec2: 두 번째 벡터 (1536차원)
            
        Returns:
            코사인 유사도 값 (0-1 사이, 1에 가까울수록 유사)
        """
        # numpy 배열로 변환
        a = np.array(vec1, dtype=np.float32)
        b = np.array(vec2, dtype=np.float32)
        
        # 벡터 크기 계산
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        # 0 벡터 처리
        if norm_a == 0 or norm_b == 0:
            return 0.0
            
        # 코사인 유사도 = (A·B) / (|A| * |B|)
        similarity = np.dot(a, b) / (norm_a * norm_b)
        
        # 유사도를 0-1 사이 값으로 정규화 (코사인 값은 -1~1)
        return float((similarity + 1) / 2)
    
    def find_similar_tours_by_vector(self, 
                                   db: Session, 
                                   query_text: str, 
                                   region: str = None,
                                   limit: int = 10,
                                   similarity_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        벡터 유사도를 활용한 관광지 검색
        
        Args:
            db: 데이터베이스 세션
            query_text: 사용자 자연어 입력
            region: 지역 필터 (옵션)
            limit: 반환할 결과 개수
            similarity_threshold: 유사도 임계값
            
        Returns:
            유사도 기반 정렬된 관광지 목록
        """
        
        print(f"🔍 벡터 검색 시작: '{query_text}'")
        
        # 1. 사용자 입력을 벡터로 변환
        try:
            query_vector = embed_text(query_text)
            print(f"✅ 쿼리 벡터 생성 완료: {len(query_vector)}차원")
        except Exception as e:
            print(f"❌ 벡터 생성 실패: {e}")
            return []
        
        # 2. PostgreSQL + pgvector로 유사도 검색
        try:
            # pgvector의 코사인 유사도 연산자 (<->) 사용
            sql_query = text("""
                SELECT 
                    id, name, region, tags, lat, lon, contentid, image_url,
                    detailed_keywords, keywords,
                    (pref_vector <-> :query_vector::vector) as distance,
                    (1 - (pref_vector <-> :query_vector::vector)) as similarity
                FROM tour_spots 
                WHERE pref_vector IS NOT NULL
                  AND (:region IS NULL OR region = :region)
                ORDER BY pref_vector <-> :query_vector::vector
                LIMIT :limit
            """)
            
            result = db.execute(sql_query, {
                'query_vector': query_vector,
                'region': region,
                'limit': limit
            }).fetchall()
            
            print(f"✅ PostgreSQL 벡터 검색 완료: {len(result)}개 결과")
            
        except Exception as e:
            print(f"❌ pgvector 검색 실패, 메모리 기반 검색으로 전환: {e}")
            return self._fallback_memory_search(db, query_vector, region, limit, similarity_threshold)
        
        # 3. 결과 가공
        recommendations = []
        for row in result:
            # 유사도 임계값 필터링
            if row.similarity < similarity_threshold:
                continue
                
            recommendations.append({
                'id': row.id,
                'name': row.name,
                'region': row.region,
                'tags': row.tags,
                'lat': row.lat,
                'lon': row.lon,
                'contentid': row.contentid,
                'image_url': row.image_url,
                'keywords': row.keywords,
                'similarity_score': float(row.similarity),
                'distance': float(row.distance),
                'search_method': 'pgvector'
            })
        
        print(f"🎯 최종 추천 결과: {len(recommendations)}개 (임계값: {similarity_threshold})")
        return recommendations
    
    def _fallback_memory_search(self, 
                               db: Session, 
                               query_vector: List[float],
                               region: str = None,
                               limit: int = 10,
                               similarity_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        pgvector 실패 시 메모리 기반 유사도 검색 (폴백)
        """
        print("🔄 메모리 기반 벡터 검색 시작")
        
        # 벡터가 있는 관광지만 조회
        query = db.query(TourSpot).filter(TourSpot.pref_vector.isnot(None))
        if region:
            query = query.filter(TourSpot.region == region)
        
        tour_spots = query.all()
        print(f"📊 검색 대상 관광지: {len(tour_spots)}개")
        
        # 각 관광지와의 유사도 계산
        similarities = []
        for tour in tour_spots:
            if not tour.pref_vector:
                continue
                
            similarity = self.calculate_cosine_similarity(query_vector, tour.pref_vector)
            
            if similarity >= similarity_threshold:
                similarities.append({
                    'tour': tour,
                    'similarity': similarity
                })
        
        # 유사도 기준 정렬
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        similarities = similarities[:limit]
        
        print(f"🎯 메모리 검색 결과: {len(similarities)}개")
        
        # 결과 형식 맞춤
        recommendations = []
        for item in similarities:
            tour = item['tour']
            recommendations.append({
                'id': tour.id,
                'name': tour.name,
                'region': tour.region,
                'tags': tour.tags,
                'lat': tour.lat,
                'lon': tour.lon,
                'contentid': tour.contentid,
                'image_url': tour.image_url,
                'keywords': tour.keywords,
                'similarity_score': item['similarity'],
                'distance': 1 - item['similarity'],  # 거리 = 1 - 유사도
                'search_method': 'memory'
            })
        
        return recommendations
    
    def find_similar_jobs_by_vector(self, 
                                  db: Session,
                                  query_text: str,
                                  region: str = None,
                                  limit: int = 10,
                                  similarity_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        벡터 유사도를 활용한 농가 일자리 검색
        """
        print(f"🚜 농가 벡터 검색 시작: '{query_text}'")
        
        # 사용자 입력을 벡터로 변환
        try:
            query_vector = embed_text(query_text)
        except Exception as e:
            print(f"❌ 농가 벡터 생성 실패: {e}")
            return []
        
        # 농가 데이터 검색 (메모리 기반)
        query = db.query(JobPost).filter(JobPost.pref_vector.isnot(None))
        if region:
            query = query.filter(JobPost.region == region)
        
        jobs = query.all()
        print(f"📊 검색 대상 농가: {len(jobs)}개")
        
        # 유사도 계산
        similarities = []
        for job in jobs:
            if not job.pref_vector:
                continue
                
            similarity = self.calculate_cosine_similarity(query_vector, job.pref_vector)
            
            if similarity >= similarity_threshold:
                similarities.append({
                    'job': job,
                    'similarity': similarity
                })
        
        # 정렬 및 제한
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        similarities = similarities[:limit]
        
        # 결과 포맷팅
        recommendations = []
        for item in similarities:
            job = item['job']
            recommendations.append({
                'id': job.id,
                'title': job.title,
                'region': job.region,
                'address': job.address,
                'crop_type': job.crop_type,
                'work_date': job.work_date,
                'work_hours': job.work_hours,
                'tags': job.tags,
                'image_url': job.image_url,
                'similarity_score': item['similarity'],
                'search_method': 'vector'
            })
        
        print(f"🎯 농가 검색 결과: {len(recommendations)}개")
        return recommendations
    
    def update_content_vectors(self, db: Session, content_type: str = "tour") -> Dict[str, int]:
        """
        콘텐츠의 벡터를 일괄 업데이트
        
        Args:
            db: 데이터베이스 세션
            content_type: "tour" 또는 "job"
            
        Returns:
            업데이트 통계
        """
        print(f"📦 {content_type} 벡터 업데이트 시작")
        
        if content_type == "tour":
            return self._update_tour_vectors(db)
        elif content_type == "job":
            return self._update_job_vectors(db)
        else:
            raise ValueError(f"지원하지 않는 content_type: {content_type}")
    
    def _update_tour_vectors(self, db: Session) -> Dict[str, int]:
        """관광지 벡터 업데이트"""
        
        # 벡터가 없는 관광지 조회
        tours_without_vector = db.query(TourSpot).filter(
            TourSpot.pref_vector.is_(None)
        ).all()
        
        print(f"📍 벡터 업데이트 대상 관광지: {len(tours_without_vector)}개")
        
        if not tours_without_vector:
            return {"updated": 0, "failed": 0, "skipped": len(tours_without_vector)}
        
        # 벡터화할 텍스트 준비
        texts_to_embed = []
        for tour in tours_without_vector:
            # 관광지 이름 + 키워드 + 지역 정보 결합
            text_content = f"{tour.name}"
            if tour.keywords:
                text_content += f" {tour.keywords}"
            if tour.tags:
                text_content += f" {tour.tags}"
            if tour.region:
                text_content += f" {tour.region}"
            
            texts_to_embed.append(text_content)
        
        try:
            # 배치로 임베딩 생성
            vectors = embed_texts(texts_to_embed)
            print(f"✅ 벡터 생성 완료: {len(vectors)}개")
            
            # 데이터베이스에 저장
            updated_count = 0
            for i, tour in enumerate(tours_without_vector):
                try:
                    tour.pref_vector = vectors[i]
                    db.add(tour)
                    updated_count += 1
                except Exception as e:
                    print(f"❌ 관광지 {tour.name} 벡터 저장 실패: {e}")
            
            db.commit()
            print(f"✅ 관광지 벡터 업데이트 완료: {updated_count}개")
            
            return {
                "updated": updated_count,
                "failed": len(tours_without_vector) - updated_count,
                "skipped": 0
            }
            
        except Exception as e:
            print(f"❌ 관광지 벡터 업데이트 실패: {e}")
            db.rollback()
            return {"updated": 0, "failed": len(tours_without_vector), "skipped": 0}
    
    def _update_job_vectors(self, db: Session) -> Dict[str, int]:
        """농가 일자리 벡터 업데이트"""
        
        jobs_without_vector = db.query(JobPost).filter(
            JobPost.pref_vector.is_(None)
        ).all()
        
        print(f"🚜 벡터 업데이트 대상 농가: {len(jobs_without_vector)}개")
        
        if not jobs_without_vector:
            return {"updated": 0, "failed": 0, "skipped": len(jobs_without_vector)}
        
        # 벡터화할 텍스트 준비
        texts_to_embed = []
        for job in jobs_without_vector:
            text_content = f"{job.title}"
            if job.crop_type:
                text_content += f" {job.crop_type}"
            if job.tags:
                text_content += f" {job.tags}"
            if job.region:
                text_content += f" {job.region}"
            if job.preference_condition:
                text_content += f" {job.preference_condition}"
            
            texts_to_embed.append(text_content)
        
        try:
            vectors = embed_texts(texts_to_embed)
            
            updated_count = 0
            for i, job in enumerate(jobs_without_vector):
                try:
                    job.pref_vector = vectors[i]
                    db.add(job)
                    updated_count += 1
                except Exception as e:
                    print(f"❌ 농가 {job.title} 벡터 저장 실패: {e}")
            
            db.commit()
            print(f"✅ 농가 벡터 업데이트 완료: {updated_count}개")
            
            return {
                "updated": updated_count,
                "failed": len(jobs_without_vector) - updated_count,
                "skipped": 0
            }
            
        except Exception as e:
            print(f"❌ 농가 벡터 업데이트 실패: {e}")
            db.rollback()
            return {"updated": 0, "failed": len(jobs_without_vector), "skipped": 0}
    
    def semantic_search_demo(self, db: Session, query: str) -> Dict[str, Any]:
        """
        벡터 기반 의미적 검색 데모
        
        Args:
            db: 데이터베이스 세션
            query: 자연어 검색 쿼리
            
        Returns:
            검색 결과와 성능 정보
        """
        import time
        
        start_time = time.time()
        
        print(f"🎯 의미적 검색 데모: '{query}'")
        
        # 관광지 검색
        tour_results = self.find_similar_tours_by_vector(
            db=db,
            query_text=query,
            limit=5,
            similarity_threshold=0.6
        )
        
        # 농가 검색
        job_results = self.find_similar_jobs_by_vector(
            db=db,
            query_text=query,
            limit=3,
            similarity_threshold=0.6
        )
        
        end_time = time.time()
        
        return {
            "query": query,
            "tour_results": tour_results,
            "job_results": job_results,
            "performance": {
                "search_time": end_time - start_time,
                "tour_count": len(tour_results),
                "job_count": len(job_results)
            },
            "search_explanation": {
                "method": "벡터 의미적 검색",
                "embedding_model": "text-embedding-3-small",
                "vector_dimension": 1536,
                "similarity_metric": "코사인 유사도"
            }
        }


# 싱글톤 인스턴스
_vector_service = None

def get_vector_similarity_service() -> VectorSimilarityService:
    """VectorSimilarityService 싱글톤 반환"""
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorSimilarityService()
    return _vector_service