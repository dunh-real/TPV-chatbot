import sys
from app.services.llm_service import OllamaChatLLM, RerankerService, PromptBuilder
from app.services.qdrant_service import VectorStoreService
from app.services.memory_service import RedisChatMemory

# Load client service
db_client = VectorStoreService()
rerank_client = RerankerService()
prompt_client = PromptBuilder()
memory_client = RedisChatMemory()

# API return: tenant_id, role_user from user'query
tenant_id = ""
role_user = ""

# Loop chat
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
        
        if not query: continue

        try:
            print("   🔍 Đang tìm kiếm thông tin...")
            
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
            
            response_obj, citation = llm_client.invoke(messages)
            
            final_answer = ""
            if hasattr(response_obj, 'content'):
                final_answer = response_obj.content 
            else:
                final_answer = str(response_obj)    

            # Output for Backend Team
            result = {
                "query": query,
                "answer": final_answer,
                "citation": citation
            }
            
            # In ra màn hình
            print(f"\n🤖 ChatBot: {final_answer}")
            print("-" * 50)

        except Exception as e:
            print(f"❌ Chi tiết lỗi: {e}")