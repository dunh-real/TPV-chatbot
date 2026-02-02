from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_community.embeddings import HuggingFaceBgeEmbeddings

# custom_header_patterns = {"**": 1, "*": 2}
# header_to_split_on = [("**", "Bold Header"), ("*", "Bold Header")]

# markdown_splitter = MarkdownHeaderTextSplitter(
#     headers_to_split_on = header_to_split_on,
#     custom_header_patterns = custom_header_patterns,
#     strip_headers = False
# )

# path = "../../data/markdown/document_1_output.md"
# with open(path, "r", encoding = "utf-8") as f:
#     markdown_document = f.read()

# chunks = markdown_splitter.split_text(markdown_document)
# contents = []
# for chunk in chunks:
#     contents.append(chunk.page_content)

# embeddings = HuggingFaceBgeEmbeddings(model_name = "paraphrase-multilingual-MiniLM-L12-v2")
# text_splitter = SemanticChunker(embeddings,
#                                 breakpoint_threshold_type = "percentile",
#                                 breakpoint_threshold_amount = 55)
# children_chunks = []

# for chunk in contents:
#     child_chunks = text_splitter.split_text(chunk)
#     for child_chunk in child_chunks:
#         children_chunks.append(child_chunk)

# for i in range(len(children_chunks)):
#     print("-"*70)
#     print(f"[parent chunk]")
#     print("-"*70)
#     print(f"[child chunk {i + 1}]")
#     print(children_chunks[i])
#     print("-"*70)

# for i in range(len(chunks)):
#     print(f"\n[Chunk {i + 1}]: {chunks[i].page_content}\n")
#     print(type(chunks[i].page_content))


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

    def structure_chunking(self, markdown_path):
        with open(markdown_path, "r", encoding = "utf-8") as f:
            markdown_document = f.read()
        
        chunks_content = []
        chunks = self.markdown_splitter.split_text(markdown_document)
        for chunk in chunks:
            chunks_content.append(chunk.page_content)
        
        return chunks_content
    
    def semantic_chunking(self, chunks):
        children_chunks = []
        for chunk in chunks:
            child_chunks = self.semantic_chunker.split_text(chunk)
            for child_chunk in child_chunks:
                children_chunks.append(child_chunk)
        
        return children_chunks
    
