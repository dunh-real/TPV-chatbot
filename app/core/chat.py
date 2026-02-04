import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.services.llm_service import OllamaChatLLM, RerankerService, PromptBuilder
from app.services.qdrant_service import VectorStoreService
from app.services.memory_service import RedisChatMemory

"""
Hệ thống trò chuyện:
- Input: Truy vấn được nhập từ người dùng
- Output: Hệ thống chatbot đưa ra câu trả lời dựa trên truy vấn từ nguồn tri thức hệ thống

Luồng hoạt động:
    1. Người dùng nhập vào truy vấn (Query Input). API trả về các tham số sau: tenant_id, access_role, employee_id
    2. Thêm ngữ cảnh cho truy vấn dựa trên lịch sử hội thoại:
    Query Input + Conversation History -> LLM rewrite -> Context Query
    3. Embedding truy vấn:
    Context Query -> Embedding Model -> Dense Vector + Sparse Vector
    4. Truy vấn DB, tìm kiếm ngữ cảnh tương đồng:
    Retrieval to Qdrant DB -> Context Docs (20)
    5. Xếp hạng ngữ cảnh và lấy ra top ngữ cảnh tối ưu:
    Context Docs (20) -> LLM reranking -> Context Docs (5)
    6. Tăng cường context và đưa vào LLM để sinh ra phản hồi cuối cùng:
    Context Query + Context Docs (5) -> LLM -> Final Response 
    
    Format đầu ra JSON:
        {       
        "tenant_id": tenant_id,
        "employee_id": employee_id,
        "query": query,
        "answer": final_answer,
        "citation": citation
        }
"""

# Load client service
db_client = VectorStoreService()
rerank_client = RerankerService()
prompt_client = PromptBuilder()
memory_client = RedisChatMemory()

class ChatSession():
    def __init__(self):
        pass

    def chat_session(self, tenant_id, access_role, employee_id):
        print("🚀 KHỞI ĐỘNG HỆ THỐNG RAG ENTERPRISE")
        print("="*50)
        print("🤖 CHẾ ĐỘ TRÒ CHUYỆN")
        print("="*50)

        # Khởi tạo LLM
        try:
            llm_client = OllamaChatLLM()
            print(f"✅ Đã kết nối model: {llm_client.model_name}")
        except Exception as e:
            print(f"❌ Lỗi khởi tạo LLM: {e}")
            return
        
        # Loop chat
        while True:
            print("Nhập quit hoặc exit để kết thúc cuộc trò chuyện <3")
            query = input("\n👤 Bạn: ").strip()

            if query.lower() == 'quit' or query.lower() == 'exit':
                print("👋 Tạm biệt! Rất vui vì được hỗ trợ")
                sys.exit(0)
            
            if not query: continue
            # Get conversation history 
            chat_history = memory_client.get_history(tenant_id, employee_id, limit=2)

            # Rewrite query input
            context_query = memory_client.contextualize_query(query, chat_history)

            memory_client.add_message(tenant_id, employee_id, "user", context_query)

            # first_time = time.time()

            try:
                print("   🔍 Đang tìm kiếm thông tin...")
                
                # Search vector
                search_results = db_client.search_hybrid(context_query, tenant_id, access_role, k=20)
                # Reranking docs
                top_docs = rerank_client.rerank(context_query, search_results, top_k=5)
                # Build prompt 
                messages = prompt_client.build_chat_messages(
                    query=context_query, 
                    search_results=top_docs, 
                    reasoning=False
                )

                print("   🧠 AI đang suy luận...")
                
                response_obj, citation = llm_client.invoke(messages)
                
                final_answer = ""
                if hasattr(response_obj, 'content'):
                    final_answer = response_obj.content 
                else:
                    final_answer = str(response_obj) 

                # end_time = time.time() - first_time  

                # Save message to Redis
                memory_client.add_message(tenant_id, employee_id, "assistant", final_answer)

                # Output for Backend Team
                result = {
                    "tenant_id": tenant_id,
                    "employee_id": employee_id,
                    "query": query,
                    "answer": final_answer,
                    "citation": citation
                }
                
                # Print response
                print(f"\n🤖 ChatBot: {final_answer}")
                print(result)
                # print(end_time)
                print("=" * 50)

            except Exception as e:
                print(f"❌ Chi tiết lỗi: {e}")

def main():
    chat_client = ChatSession()

    # API return: tenant_id, access_role, employee_id
    tenant_id = "VGP"
    access_role = 1
    employee_id = "B123"

    chat_client.chat_session(tenant_id, access_role, employee_id)

if __name__ == "__main__":
    main()