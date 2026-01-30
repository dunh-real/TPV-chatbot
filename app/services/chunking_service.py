import torch
import os
import nltk
import re
from pathlib import Path
from nltk.tokenize import sent_tokenize
from sentence_transformers import SentenceTransformer, util
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab')

MODEL_NAME = "BAAI/bge-m3"
MODEL_CACHE_FOLDEL = os.path.join(os.path.dirname(__file__), "models_cache")
os.makedirs(MODEL_CACHE_FOLDEL, exist_ok=True)

class ContextAwareChunking:
    def __init__(self, model_name=MODEL_NAME, cache_folder=MODEL_CACHE_FOLDEL):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Load Model
        self.model = SentenceTransformer(
            model_name, 
            device=self.device,
            cache_folder=cache_folder
        )

    # Compare Context
    def should_break_here(self, context_before, context_after, threshold = 0.5):
        if not context_before.strip() or not context_after.strip():
            return False

        embed_before = self.model.encode(context_before, convert_to_tensor=True)
        embed_after = self.model.encode(context_after, convert_to_tensor=True)

        # Cosine Similarity
        score = util.cos_sim(embed_before, embed_after).item()

        return score <= threshold

    # Custom Sentences
    def custom_sent_tokenize(self, text):
        raw_sentences = sent_tokenize(text)
        
        merged_sentences = []
        buffer = ""
        
        re_list_marker = r'^[\s\*\#]*(\d+(\.\d+)*|[a-zA-Z])[\.\)][\s\*\#]*$'
        
        re_legal_marker = r'^[\s\*\#]*(Điều|Khoản|Chương|Mục|Phần|Tiểu mục)\s+\d+.*[\.\:]?[\s\*\#]*$'
        
        re_admin_marker = r'^[\s\*\#]*(QUYẾT ĐỊNH|THÔNG BÁO|CÔNG ĐIỆN|YÊU CẦU|KẾT LUẬN|CHỈ THỊ).*[:\.]?[\s\*\#]*$'

        re_orphan_number = r'^[\s\*\#]*\d+[\s\*\#]*$'

        for sent in raw_sentences:
            s_stripped = sent.strip()
            if not s_stripped: continue
            
            is_prefix = False
            
            if re.match(re_list_marker, s_stripped) or \
            re.match(re_legal_marker, s_stripped, re.IGNORECASE) or \
            re.match(re_admin_marker, s_stripped, re.IGNORECASE) or \
            re.match(re_orphan_number, s_stripped):
                
                if len(s_stripped.split()) < 15:
                    is_prefix = True

            if s_stripped.endswith(':'):
                is_prefix = True
            
            if is_prefix:
                buffer += s_stripped + " "
            else:
                full_sent = buffer + s_stripped
                merged_sentences.append(full_sent.strip())
                buffer = "" 
                
        if buffer:
            merged_sentences.append(buffer.strip())
            
        return merged_sentences

    # Chunking with semantic
    def context_aware_chunking(self, text):
        sentences = self.custom_sent_tokenize(text)
        chunks = []
        current_chunk = ""
        for i, sentence in enumerate(sentences):
            context_before = sentences[i-1] if i > 0 else ""
            context_after = sentence
            if i > 0 and self.should_break_here(context_before, context_after, threshold=0.6): 
                chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
            else:
                current_chunk += sentence + " "
                
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks
    
class RecursiveChunking:
    def __init__(self):
        pass

    # Chunking with structure
    def recursive_chunking(self, markdown_docs):

        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
        ]

        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        md_header_splits = markdown_splitter.split_text(markdown_docs)

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, 
            chunk_overlap=0,
            separators=["\n\n", "\n"]
        )
        
        chunks = text_splitter.split_documents(md_header_splits)

        return chunks