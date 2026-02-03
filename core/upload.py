import sys
import os
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.services.chunking_service import ChunkingService
from app.services.qdrant_service import VectorStoreService
from app.services.ocr_service import OCR_document

"""
Hệ thống upload tài liệu:
- Input: File tài liệu đầu vào (PDF)
- Output: Data Point được lưu trữ trên Qdrant

Luồng hoạt động:
    1. Người dùng upload tài liệu. API trả về các tham số: tenant_id, list_access_role, src_file
    2. OCR tài liệu:
    Input File (PDF) -> OCR Model -> Output File (MD)
    3. Chia docs thành các chunk. Kết hợp Struct + Semantic Chunking:
    Output File (MD) -> Text -> Chunking -> List Chunks
    4. Chuyển các chunks từ dạng văn bản sang embedding và insert vào Qdrant DB
    List Chunks -> Embedding Model -> Dense Vector + Sparse Vector -> Insert Data to DB
"""

PATH_INPUT_FILE = "./data/raw_dir"
PATH_OUTPUT_FILE = "./data/md_dir"

# Load client service
db_client = VectorStoreService()
ocr_client = OCR_document()
chunking_client = ChunkingService()

class ProcessFileInput():
    def __init__(self):
        pass

    def process_file_upload(self, src_file, tenant_id, access_role):
        print("🚀 KHỞI ĐỘNG HỆ THỐNG RAG ENTERPRISE")
        print("="*50)
        print("📂 CHẾ ĐỘ UPLOAD TÀI LIỆU")
        print("="*50)

        # 1. Input data (PDF) -> OCR Model -> Output data (MD)
        print("Đang đọc tài liệu...")
        ocr_client.processing_data(src_file)
        md_output = Path(PATH_OUTPUT_FILE) / src_file.stem() + ".md"
        with open(md_output, "r", encoding="utf-8") as f:
            markdown_doc = f.read()

        # 2. Output data (MD) -> Chunking Text
        print("Đang chunking dữ liệu...")
        chunks = chunking_client.process_hybrid_splitting(markdown_doc, tenant_id, src_file, access_role)

        # 3. Chunking Text -> Embedding and Insert data to Qdrant
        print("Đang thêm dữ liệu vào Qdrant DB...")
        db_client.add_chunks(chunks)

        db_client.optimize_indexing()

        print("Thêm thành công dữ liệu vào Qdrant DB")

def main():
    process_client = ProcessFileInput()

    # API return: src_file, tenant_id, access_role
    src_file = None
    tenant_id = None
    access_role = None

    process_client.process_file_upload(src_file, tenant_id, access_role)

if __name__ == "__main__":
    main()