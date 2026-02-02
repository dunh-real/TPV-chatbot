from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from generate_id import GenerateID
from vector_service import EmbeddingService

class Chunking_Service:
    def __init__(self):
        self.custom_header_patterns = {"**": 1, "*": 2}
        self.header_to_split_on = [("**", "Bold Header"), ("*", "Bold Header")]
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on = self.header_to_split_on,
            custom_header_patterns = self.custom_header_patterns,
            strip_headers = False
        )
        self.embeddings = HuggingFaceBgeEmbeddings(model_name = "paraphrase-multilingual-MiniLM-L12-v2")
        self.semantic_chunker = SemanticChunker(self.embeddings,
                                        breakpoint_threshold_type = "percentile",
                                        breakpoint_threshold_amount = 55)
        self.id_generator = GenerateID()
        self.embedding_model = EmbeddingService()

    def structure_chunking(self, markdown_path, tenant_id):
        with open(markdown_path, "r", encoding = "utf-8") as f:
            markdown_document = f.read()
        parent_chunks = []
        chunks = self.markdown_splitter.split_text(markdown_document)
        for chunk in chunks:
            chunk_dict = {}
            chunk_dict["tenant_id"] = tenant_id
            chunk_dict["chunk_id"] = self.id_generator.generate_id()
            chunk_dict["chunk_type"] = "parent_chunk"
            chunk_dict["vector"] = self.embedding_model.encode(chunk.page_content)
            chunk_dict["content"] = chunk.page_content
            parent_chunks.append(chunk_dict)
        
        return parent_chunks
    
    def semantic_chunking(self, parent_chunks):
        children_chunks = []
        for parent_chunk in parent_chunks:
            child_chunks = self.semantic_chunker.split_text(parent_chunk["content"])
            for chunk in child_chunks:
                child_chunk = {}
                child_chunk["tenant_id"] = parent_chunk["tenant_id"]
                child_chunk["parent_id"] = parent_chunk["chunk_id"]
                child_chunk["chunk_id"] = self.id_generator.generate_id()
                child_chunk["chunk_type"] = "children_chunk"
                child_chunk["vector"] = self.embedding_model.encode(chunk)
                child_chunk["content"] = chunk
                children_chunks.append(child_chunk)

        return children_chunks
    


# test_chunking = Chunking_Service()
# parent_chunks = test_chunking.structure_chunking("../../data/markdown/document_1_output.md", "abc123")
# children_chunks = test_chunking.semantic_chunking(parent_chunks)
# # print(parent_chunks)
# # print("-"*70)
# # print(type(parent_chunks))
# # print("-"*70)
# for children_chunk in children_chunks:
#     print("-"*70)
#     print(children_chunk)
#     print(type(children_chunk))
#     print("-"*70)
#     print(children_chunk["content"])
#     print("-"*70)