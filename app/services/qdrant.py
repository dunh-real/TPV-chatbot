from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

class QdrantService:
    def __init__(self):
        self.client = None
        self.collection_name = None
        self.vector_size = None
    
    def init_client(self):
        self.client = QdrantClient(url = "http://localhost:6333")
        return self.client
    
    def create_collection(self, collection_name, vector_size):
        self.client.create_collection(
            collection_name = collection_name,
            vectors_config = VectorParams(size = vector_size, distance = Distance.DOT),
        )
    
    def add_vector(self, collection_name, vectors):
        operation_info = self.client.upsert(
            collection_name = collection_name,
            wait = True,
            points = [
                PointStruct(tenant_id = vector.tenant_id, vector = vector.vector, payload = vector.payload) for vector in vectors
            ]
        )
        return operation_info
    
    def query(self, collection_name, query, tenant_id):
        search_result = self.client.query_points(
            collection_name = collection_name,
            query = query,
            query_filter = Filter(
                must = [FieldCondition(key = "tenant_id", match = MatchValue(value = tenant_id))]
            ),
            with_payload = True,
            limit = 10,
        ).points
        return search_result
    
