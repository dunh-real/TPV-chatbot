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
    1. Người dùng nhập vào truy vấn (Query Input). API trả về các tham số sau: query_input, tenant_id, access_role, employee_id
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
llm_client = OllamaChatLLM()

class ChatSession():
    def __init__(self):
        pass

    def chat_session(self, query_input, tenant_id, access_role, employee_id): 
        first_time = time.time()

        query = query_input.strip()

        # 1. Query Input + Conversation History -> LLM rewrite -> Context Query
        # Get coversation history
        chat_history = memory_client.get_history(tenant_id, employee_id, limit=6)
        # Rewrite query input
        context_query = memory_client.contextualize_query(query, chat_history)
        # Save message to Redis
        memory_client.add_message(tenant_id, employee_id, "user", query)

        # 2. Context Query -> Embedding Model -> Dense Vector + Sparse Vector -> Retrieval to Qdrant DB -> Context Docs (20)
        search_results = db_client.search_hybrid(context_query, tenant_id, access_role, k=20)

        # 3. Context Docs (20) -> LLM reranking -> Context Docs (5)
        top_docs = rerank_client.rerank(context_query, search_results, top_k=5)

        # 4. Context Query + Context Docs (5) -> LLM -> Final Response 
        messages = prompt_client.build_chat_messages(
            query=context_query, 
            search_results=top_docs,
            chat_history=chat_history, 
            reasoning=False
        )

        response_obj, citation = llm_client.invoke(messages)
                
        final_answer = ""
        if hasattr(response_obj, 'content'):
            final_answer = response_obj.content 
        else:
            final_answer = str(response_obj) 

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

        end_time = time.time() - first_time

        return result, end_time

def main():
    chat_client = ChatSession()

    # API return: query_input, tenant_id, access_role, employee_id
    query_input = None
    tenant_id = None
    access_role = None
    employee_id = None

    chat_client.chat_session(query_input, tenant_id, access_role, employee_id)

if __name__ == "__main__":
    main()