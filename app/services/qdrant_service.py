from typing import List, Dict, Optional
from qdrant_client import QdrantClient, models
from app.services.embedding_service import LocalDenseEmbedding, LocalSparseEmbedding
import uuid 
import math
import hashlib 

# Setup DB
QDRANT_URL = "http://localhost:6333" 
COLLECTION_NAME = "enterprise_docs" 
DENSE_VECTOR_NAME = "dense-vector"
SPARSE_VECTOR_NAME = "sparse-vector" 
DENSE_DIMENSION = 1024 

# Embedding Model
dense_embedder = LocalDenseEmbedding()
sparse_embedder = LocalSparseEmbedding()

class VectorStoreService:
    def __init__(self, shard_number: int = 2):
        # Connect Qdrant
        self.client = QdrantClient(url=QDRANT_URL) 
        self.collection_name = COLLECTION_NAME
        self.dense_vector = DENSE_VECTOR_NAME
        self.sparse_vector = SPARSE_VECTOR_NAME
        self.vector_size = DENSE_DIMENSION
        self.shard_number = shard_number 
        
        self._ensure_collection()

    def _ensure_collection(self):
        """Tạo collection hỗ trợ cả Dense và Sparse vector, tối ưu cho Upload."""

        if not self.client.collection_exists(self.collection_name):
            print(f"Tạo mới collection '{self.collection_name}' trong Qdrant...")
            # Create collection
            self.client.create_collection(
                collection_name=self.collection_name,
                
                # Create dense - vertor
                vectors_config={
                    self.dense_vector: models.VectorParams(
                        size=self.vector_size,
                        distance=models.Distance.COSINE,
                        on_disk=True
                    )
                },
                
                # Create sparse - vector
                sparse_vectors_config={
                    self.sparse_vector: models.SparseVectorParams(
                        index=models.SparseIndexParams(
                            on_disk=True, 
                        )
                    )
                },
                # Tạm tắt Indexing HNSW để tăng tốc độ upload
                hnsw_config=models.HnswConfigDiff(m=0),
                # Phân mảnh 
                shard_number=self.shard_number
            )
            
            # Create Payload Indexes for tenant_id, filename, role_user fields 
            try:
                self.client.create_payload_index(self.collection_name, "tenant_id", models.PayloadSchemaType.KEYWORD)
                self.client.create_payload_index(self.collection_name, "src_file", models.PayloadSchemaType.KEYWORD)
                self.client.create_payload_index(self.collection_name, "accessed_role", models.PayloadSchemaType.INTEGER)
            except Exception:
                pass
    
    def optimize_indexing(self):
        """Bật lại Indexing sau khi upload xong để tìm kiếm nhanh hơn."""

        self.client.update_collection(
            collection_name=self.collection_name,
            hnsw_config=models.HnswConfigDiff(m=16, ef_construct=100)
        )

    # Generate deterministic ID
    def generate_deterministic_id(self, tenant_id: str, src_file: str, chunk_idx: int) -> str:
        unique_str = f"{tenant_id}_{src_file}_{chunk_idx}"
        hash_obj = hashlib.md5(unique_str.encode('utf-8'))
        return str(uuid.UUID(hash_obj.hexdigest()))

    # Delete document by tenant_id and filename
    def delete_document(self, tenant_id: str, src_file: str):
        """Xóa toàn bộ chunks của một file cụ thể dựa trên tenant_id và src_file."""

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id)),
                        models.FieldCondition(key="src_file", match=models.MatchValue(value=src_file)),
                    ]
                )
            )
        )

    # Add chunks to Qdrant
    def add_chunks(self, chunks: List[Dict], batch_size: int = 128):
        """
        Upload chunks theo từng batch nhỏ.
        """
        if not chunks:
            return

        total_chunks = len(chunks)
        
        # BATCHING
        for i in range(0, total_chunks, batch_size):
            batch_chunks = chunks[i : i + batch_size]
            
            try:
                # 1. Lấy text
                texts = [chunk['content'] for chunk in batch_chunks]
                
                # 2. Tạo Dense Vectors
                dense_vectors = dense_embedder.embed(texts)

                # 3. Tạo Sparse Vectors
                sparse_vectors = sparse_embedder.embed(texts)
                
                points = []
                for j, chunk in enumerate(batch_chunks):

                    payload = {
                        "tenant_id": chunk.get("tenant_id"),      
                        "src_file": chunk.get("src_file"),
                        "accessed_role": chunk.get("accessed_role"),              
                        "content": chunk.get("content"),          
                        "metadata": chunk.get("metadata", {})
                    }

                    # Tạo ID cố định
                    global_idx = i + j
                    point_id = self.generate_deterministic_id(
                        payload["tenant_id"], 
                        payload["src_file"], 
                        global_idx
                    )

                    # Tạo Point
                    points.append(models.PointStruct(
                        id=point_id,
                        vector={
                            self.dense_vector: dense_vectors[j],
                            self.sparse_vector: sparse_vectors[j]
                        },
                        payload=payload
                    ))

                # Upsert Batch
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                
            except Exception as e:
                raise e
        
        print("Quá trình upload hoàn tất.")

    def search_hybrid(self, query: str, tenant_id: str, accessed_role: str, k: int = 10, top_k: Optional[int] = None):
        if top_k is not None:
            k = top_k
        
        # Tạo Vector cho câu Query
        dense_vector = dense_embedder.get_dense_vector(query)
        
        sparse_vector = sparse_embedder.get_sparse_vector(query)

        # Cấu hình Prefetch 
        prefetch_limit = k * 2 # Lấy dư ra để Fusion tốt hơn

        filter_condition = models.Filter(
            must=[
                models.FieldCondition(
                    key="tenant_id", 
                    match=models.MatchValue(value=tenant_id)
                ),
                models.FieldCondition(
                    key="accessed_role", 
                    match=models.MatchValue(value=accessed_role)
                )
            ]
        )

        prefetch_sparse = models.Prefetch(
            query=sparse_vector,
            using=self.sparse_vector,
            limit=prefetch_limit,
            filter=filter_condition
        )

        prefetch_dense = models.Prefetch(
            query=dense_vector,
            using=self.dense_vector,
            limit=prefetch_limit,
            filter=filter_condition
        )

        # Query Fusion
        results = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[prefetch_sparse, prefetch_dense],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=k, 
            with_payload=True,
        )

        return results.points