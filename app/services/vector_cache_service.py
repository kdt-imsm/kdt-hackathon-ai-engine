"""
벡터 캐시 서비스
사전 생성된 관광지 벡터를 메모리에 로딩하고 관리
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import time

class VectorCacheService:
    """관광지 벡터 캐시 관리 서비스"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.vectors_data: Optional[Dict[str, Any]] = None
        self.vectors_by_region: Dict[str, List[Dict[str, Any]]] = {}
        self.loaded_at: Optional[float] = None
        
    def load_vectors(self, force_reload: bool = False) -> bool:
        """사전 생성된 벡터 데이터를 메모리에 로딩"""
        
        if self.vectors_data is not None and not force_reload:
            print("📦 벡터 데이터가 이미 메모리에 로드되어 있습니다.")
            return True
        
        vectors_file = self.project_root / "data" / "attraction_vectors.json"
        
        if not vectors_file.exists():
            print(f"❌ 벡터 파일이 존재하지 않습니다: {vectors_file}")
            print("💡 먼저 'python scripts/precompute_attraction_vectors.py'를 실행하세요.")
            return False
        
        try:
            print(f"📂 벡터 데이터 로딩 중: {vectors_file}")
            start_time = time.time()
            
            with open(vectors_file, 'r', encoding='utf-8') as f:
                self.vectors_data = json.load(f)
            
            # 지역별 인덱싱
            self._build_region_index()
            
            load_time = time.time() - start_time
            self.loaded_at = time.time()
            
            total_vectors = len(self.vectors_data.get('vectors', {}))
            file_size_mb = vectors_file.stat().st_size / (1024 * 1024)
            
            print(f"✅ 벡터 데이터 로딩 완료:")
            print(f"   📊 총 벡터 개수: {total_vectors}개")
            print(f"   📁 파일 크기: {file_size_mb:.2f}MB")
            print(f"   ⏱️  로딩 시간: {load_time:.2f}초")
            print(f"   🗂️  지역별 분류: {len(self.vectors_by_region)}개 지역")
            
            return True
            
        except Exception as e:
            print(f"❌ 벡터 데이터 로딩 실패: {e}")
            return False
    
    def _build_region_index(self):
        """지역별 벡터 인덱스 구축"""
        
        if not self.vectors_data:
            return
        
        self.vectors_by_region = {}
        vectors = self.vectors_data.get('vectors', {})
        
        for key, vector_data in vectors.items():
            region = vector_data.get('region')
            if region:
                if region not in self.vectors_by_region:
                    self.vectors_by_region[region] = []
                
                # 벡터 데이터에 키 정보 추가
                vector_data['_cache_key'] = key
                self.vectors_by_region[region].append(vector_data)
        
        # 지역별 통계 출력
        for region, attractions in self.vectors_by_region.items():
            print(f"   🏛️  {region}: {len(attractions)}개 관광지")
    
    def get_vectors_by_region(self, region: str) -> List[Dict[str, Any]]:
        """특정 지역의 모든 벡터 데이터 반환"""
        
        if not self.vectors_data:
            if not self.load_vectors():
                return []
        
        return self.vectors_by_region.get(region, [])
    
    def get_all_vectors(self) -> List[Dict[str, Any]]:
        """모든 벡터 데이터 반환"""
        
        if not self.vectors_data:
            if not self.load_vectors():
                return []
        
        all_vectors = []
        for attractions in self.vectors_by_region.values():
            all_vectors.extend(attractions)
        
        return all_vectors
    
    def calculate_similarity(self, user_vector: List[float], attraction_vector: List[float]) -> float:
        """코사인 유사도 계산 (최적화된 버전)"""
        
        try:
            import math
            
            # 내적 계산
            dot_product = sum(a * b for a, b in zip(user_vector, attraction_vector))
            
            # 벡터 크기 계산
            magnitude1 = math.sqrt(sum(a * a for a in user_vector))
            magnitude2 = math.sqrt(sum(a * a for a in attraction_vector))
            
            # 코사인 유사도 계산
            if magnitude1 * magnitude2 == 0:
                return 0.0
            
            similarity = dot_product / (magnitude1 * magnitude2)
            return max(0.0, min(1.0, similarity))  # 0-1 범위로 제한
            
        except Exception as e:
            print(f"❌ 유사도 계산 실패: {e}")
            return 0.0
    
    def find_similar_attractions(self, user_vector: List[float], region: Optional[str] = None, 
                               top_k: int = 20) -> List[Tuple[Dict[str, Any], float]]:
        """유사도 기반 관광지 검색 (캐시된 벡터 사용)"""
        
        if not self.vectors_data:
            if not self.load_vectors():
                return []
        
        # 검색 대상 결정
        if region:
            search_vectors = self.get_vectors_by_region(region)
            if not search_vectors:
                print(f"⚠️  {region} 지역의 벡터 데이터를 찾을 수 없습니다.")
                return []
        else:
            search_vectors = self.get_all_vectors()
        
        # 유사도 계산
        similarities = []
        for attraction_data in search_vectors:
            attraction_vector = attraction_data.get('vector', [])
            if attraction_vector:
                similarity = self.calculate_similarity(user_vector, attraction_vector)
                similarities.append((attraction_data, similarity))
        
        # 유사도 순으로 정렬
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def get_cache_info(self) -> Dict[str, Any]:
        """캐시 상태 정보 반환"""
        
        if not self.vectors_data:
            return {"status": "not_loaded"}
        
        metadata = self.vectors_data.get('metadata', {})
        
        return {
            "status": "loaded",
            "loaded_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.loaded_at)),
            "total_vectors": len(self.vectors_data.get('vectors', {})),
            "regions": list(self.vectors_by_region.keys()),
            "regions_count": len(self.vectors_by_region),
            "model": metadata.get('model', 'unknown'),
            "vector_dimension": metadata.get('vector_dimension', 0),
            "created_at": metadata.get('created_at', 'unknown')
        }

# 싱글톤 인스턴스
_vector_cache = None

def get_vector_cache_service() -> VectorCacheService:
    """VectorCacheService 싱글톤 반환"""
    global _vector_cache
    if _vector_cache is None:
        _vector_cache = VectorCacheService()
    return _vector_cache