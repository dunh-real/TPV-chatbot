import uuid
import os
from pathlib import Path
from embedding_service import LocalDenseEmbedding, LocalSparseEmbedding
from chunking_service import ContextAwareChunking, RecursiveChunking
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Distance, VectorParams, SparseVectorParams, SparseIndexParams

# Setup DB
QDRANT_URL = "http://localhost:6333" 
COLLECTION_NAME = "enterprise_documents" 
DENSE_VECTOR_NAME = "dense-vector"
SPARSE_VECTOR_NAME = "sparse-vector" 
DENSE_DIMENSION = 1024 

CURRENT_TENANT_ID = "VGP"

# Embedding Model
dense_embedder = LocalDenseEmbedding()
sparse_embedder = LocalSparseEmbedding()

# Chunking Text
struct = RecursiveChunking()
semantic = ContextAwareChunking()

def chunk_to_vec(file_path: str):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            markdown_document = f.read()
    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file tại {file_path}")
        return None, None, None

    # Chunking with structure
    chunks = struct.recursive_chunking(markdown_document)

    chunks_final = []
    metadata_list = []

    for parent_id, chunk in enumerate(chunks):
        # Chunking with semantic
        sub_chunks = semantic.context_aware_chunking(chunk.page_content)

        for child_id, sub_chunk in enumerate(sub_chunks):
            chunks_final.append(sub_chunk)

            metadata_list.append({
                "parent_id": parent_id, 
                "child_id": child_id
            })


    # Dense vector
    dense_vectors = dense_embedder.embed(chunks_final)
    
    # Sparse vector
    sparse_vectors = sparse_embedder.embed(chunks_final)

    return chunks_final, dense_vectors, sparse_vectors, metadata_list

def init_qdrant_collection(client: QdrantClient):
    if not client.collection_exists(collection_name=COLLECTION_NAME):
        # Create collection
        client.create_collection(
            collection_name=COLLECTION_NAME,

            # Create dense - vector
            vectors_config={
                DENSE_VECTOR_NAME: VectorParams(
                    size=DENSE_DIMENSION,
                    distance=Distance.COSINE
                )
            },

            # Create sparse - vector
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: SparseVectorParams(
                    index=SparseIndexParams(
                        on_disk=False, 
                    )
                )
            }
        )
        
        # Create payload (meta data)
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="tenant_id",
            field_schema=models.PayloadSchemaType.KEYWORD
        )
    else:
        print("Collection đã tồn tại. Bỏ qua bước tạo.")

def upload_data_to_qdrant(chunks, dense_vecs, sparse_vecs, metas, tenant_id="default_tenant"):
    client = QdrantClient(url=QDRANT_URL)
    
    init_qdrant_collection(client)
    
    points = []

    file_name = os.path.basename(md_file)

    for chunk, dense, sparse, meta in zip(chunks, dense_vecs, sparse_vecs, metas):      
        # Tenant + Filename + ParentId + ChildId
        id_seed = f"{tenant_id}_{file_name}_{meta['parent_id']}_{meta['child_id']}"
        deterministic_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, id_seed))

        payload = {
            "tenant_id": tenant_id,
            "file_name": file_name,
            "parent_id": meta['parent_id'], 
            "child_id": meta['child_id'],
            "content": chunk,
            "type": "child_chunk"
        }

        point = models.PointStruct(
            id=deterministic_id, 
            vector={
                DENSE_VECTOR_NAME: dense,
                SPARSE_VECTOR_NAME: sparse
            },
            payload=payload 
        )
        points.append(point)
        
    BATCH_SIZE = 100
    for i in range(0, len(points), BATCH_SIZE):
        batch_points = points[i : i + BATCH_SIZE]
        client.upsert(
            collection_name=COLLECTION_NAME,
            wait=True, 
            points=batch_points
        )

# Setup markdown file path
PATH_MD_CLEANED = "./md_cleaned"
md_files = list(Path(PATH_MD_CLEANED).glob("*.md"))

if __name__ == "__main__":
    for md_file in md_files:

        client = QdrantClient(url=QDRANT_URL)

        chunks, dense_vecs, sparse_vecs, metas = chunk_to_vec(md_file)

        # Push data to Qdrant
        if chunks and dense_vecs and sparse_vecs and metas:
            upload_data_to_qdrant(
                chunks=chunks,
                dense_vecs=dense_vecs,
                sparse_vecs=sparse_vecs,
                metas = metas,
                tenant_id=CURRENT_TENANT_ID
            )
        else:
            print("\nCó lỗi trong quá trình xử lý file. Không thể upload.")