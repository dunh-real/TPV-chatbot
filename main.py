import sys
from pathlib import Path
from generation_service.llm_service import OllamaChatLLM
from generation_service.prompt_builder import PromptBuilder
from generation_service.reranker_service import RerankerService
from ingestion_service.converter import DocumentConverter
from ingestion_service.splitter import ChunkingService
from retrieval_service.qdrant_service import VectorStoreService

# Load client service
converter_client = DocumentConverter()
chunking_client = ChunkingService()
db_client = VectorStoreService()
rerank_client = RerankerService()
prompt_client = PromptBuilder()

# Gọi API trả về 2 tham số sau:
tenant_id = "VGP"
role_user = "CEO"

def process_file_upload():
    """Quy trình nạp dữ liệu: Convert -> Split -> Embed -> Store"""
    print("\n" + "="*50)
    print("📂 CHẾ ĐỘ UPLOAD TÀI LIỆU")
    print("="*50)
    
    while True:
        file_path_str = input("👉 Nhập đường dẫn tuyệt đối của file (hoặc 's' để skip): ").strip()
        
        if file_path_str.lower() == 's':
            return
        
        # Xử lý đường dẫn
        file_path_str = file_path_str.replace('"', '').replace("'", "")
        path = Path(file_path_str)

        if not path.exists() or not path.is_file():
            print("❌ File không tồn tại hoặc đường dẫn sai. Vui lòng thử lại.")
            continue

        try:
            print("Đang đọc file...")
            
            # BƯỚC 1: CONVERT
            markdown_text = converter_client.convert(path, save_debug=True)
            if not markdown_text:
                print("❌ File rỗng hoặc không thể convert.")
                continue

            # BƯỚC 2: CHUNKING (Hybrid Splitting)
            print("Đang chunking dữ liệu...")
            chunks = chunking_client.process_hybrid_splitting(
                text=markdown_text,
                tenant_id=tenant_id,
                filename=path.name,
                role_user=role_user
            )

            # BƯỚC 3: VECTOR STORE (Embed + Save)
            print("Đang thêm dữ liệu vào Qdrant DB")
            db_client.add_chunks(chunks)
            
            # Tối ưu lại index sau khi nạp
            db_client.optimize_indexing()
            
            print(f"Thêm dữ liệu thành công!")
            break 

        except Exception:
            print("Lỗi xảy ra trong quá trình xử lý file :(")

def chat_session():
    """Vòng lặp trò chuyện RAG"""
    print("\n" + "="*50)
    print("🤖 CHẾ ĐỘ TRÒ CHUYỆN")
    print("="*50)

    # Khởi tạo LLM
    try:
        llm_client = OllamaChatLLM()
        print(f"✅ Đã kết nối model: {llm_client.model_name}")
    except Exception as e:
        print(f"❌ Lỗi khởi tạo LLM: {e}")
        return

    while True:
        print("Nhập quit hoặc exit để kết thúc cuộc trò chuyện <3")
        query = input("\n👤 Bạn: ").strip()

        if query.lower() == 'quit' or query.lower() == 'exit':
            print("👋 Tạm biệt! Rất vui vì được hỗ trợ")
            sys.exit(0)
        elif query.lower() == 'u':
            return "UPLOAD_MODE"
        
        if not query: continue

        try:
            print("   🔍 Đang tìm kiếm thông tin...")
            
            # --- RAG PIPELINE ---
            # Search vector
            search_results = db_client.search_hybrid(query, tenant_id, role_user, k=20)
            # Reranking docs
            top_docs = rerank_client.rerank(query, search_results, top_k=5)
            
            messages = prompt_client.build_chat_messages(
                query=query, 
                search_results=top_docs, 
                reasoning=False
            )

            print("   🧠 AI đang suy luận...")
            
            # GỌI HÀM INVOKE
            response_obj, citation = llm_client.invoke(messages)
            
            # Kiểm tra kỹ kiểu dữ liệu trước khi in
            final_answer = ""
            if hasattr(response_obj, 'content'):
                final_answer = response_obj.content # Nếu là AIMessage
            else:
                final_answer = str(response_obj)    # Nếu là String hoặc Dict

            result = {
                "query": query,
                "answer": final_answer,
                "citation": citation
            }
            
            # In ra màn hình
            print(f"\n🤖 ChatBot: {final_answer}")
            print(result)
            print("-" * 30)

        except Exception as e:
            print(f"❌ Chi tiết lỗi: {e}")

def main():
    print("🚀 KHỞI ĐỘNG HỆ THỐNG RAG ENTERPRISE")
    
    # # Mặc định vào upload trước
    # current_mode = "UPLOAD"
    
    # while True:
    #     if current_mode == "UPLOAD":
    #         process_file_upload()
    #         current_mode = "CHAT" # Upload xong tự động chuyển qua chat
        
    #     elif current_mode == "CHAT":
    #         signal = chat_session()
    #         if signal == "UPLOAD_MODE":
    #             current_mode = "UPLOAD"

    chat_session()

if __name__ == "__main__":
    main()