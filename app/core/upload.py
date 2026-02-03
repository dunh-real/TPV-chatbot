import sys
from pathlib import Path
from app.services.chunking_service import ChunkingService
from app.services.qdrant_service import VectorStoreService
from app.services.ocr_service import OCR_document

PATH_INPUT_FILE = "./data/raw_dir"
PATH_OUTPUT_FILE = "./data/md_dir"

# Load client service
db_client = VectorStoreService()
ocr_client = OCR_document()
chunking_client = ChunkingService()

# API return: file_path, tenant_id, role_user
file_path = ""
tenant_id = ""
role_user = ""

# Flow: Input data (PDF) -> OCR Model -> Output data (MD) -> Chunking Text -> Embedding and Insert data to Qdrant
def process_file_upload(file_path, tenant_id, role_user):
    print("\n" + "="*50)
    print("📂 CHẾ ĐỘ UPLOAD TÀI LIỆU")
    print("="*50)

    file_path = file_path.replace('"', '').replace("'", "")
    file_path = Path(file_path)

    # 1. Input data (PDF) -> OCR Model -> Output data (MD)
    print("Đang đọc tài liệu...")
    ocr_client.processing_data(file_path)
    md_output = Path(PATH_OUTPUT_FILE) / file_path.stem() + ".md"
    with open(md_output, "r", encoding="utf-8") as f:
        markdown_doc = f.read()

    # 2. Output data (MD) -> Chunking Text
    chunks = chunking_client.process_hybrid_splitting(markdown_doc, tenant_id, file_path, role_user)

    # 3. Chunking Text -> Embedding and Insert data to Qdrant
    db_client.add_chunks(chunks)

    db_client.optimize_indexing()

    print("Thêm thành công dữ liệu vào Qdrant DB")