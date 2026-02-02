from sentence_transformers import SentenceTransformer

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

chunks = ["anh yêu em", "anh nhớ em baby à", "123 alo alo"]
embeddings = model.encode(chunks)

print(embeddings)

class EmbeddingService:
    def __init__(self):
        self.model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    def encode(self, chunks):
        embeddings = self.model.encode(chunks)
        return embeddings