import redis
import json
import ollama

NAME_LLM_MODEL = "qwen2.5:1.5b"

class RedisChatMemory:
    def __init__(self, host='localhost', port=6379, db=0, password=None):
        self.redis_client = redis.Redis(
            host=host, 
            port=port, 
            db=db, 
            password=password, 
            decode_responses=True
        )
        self.ttl = 86400  # 24 hour

    def _generate_key(self, tenant_id, employee_id):
        return f"chat_history:{tenant_id}:{employee_id}"

    def add_message(self, tenant_id, employee_id, role, content):
        key = self._generate_key(tenant_id, employee_id)
        message = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        
        self.redis_client.rpush(key, message)

        self.redis_client.expire(key, self.ttl)

    def get_history(self, tenant_id, employee_id, limit=2):
        key = self._generate_key(tenant_id, employee_id)
        raw_history = self.redis_client.lrange(key, -limit, -1)
        
        return [json.loads(msg) for msg in raw_history]

    def clear_history(self, tenant_id, employee_id):
        key = self._generate_key(tenant_id, employee_id)
        self.redis_client.delete(key) 

    def contextualize_query(self, user_query, chat_history):
        if not chat_history:
            return user_query

        # Json -> String
        history_str = ""
        for msg in chat_history:
            role = "user" if msg['role'] == 'user' else "assistant"
            history_str += f"{role}: {msg['content']}\n"

        context_prompt = f"""
        ### VAI TRÒ
        Bạn là một chuyên gia phân tích truy vấn. Nhiệm vụ của bạn là kiểm tra xem "CÂU HỎI MỚI" có cần thêm ngữ cảnh từ "LỊCH SỬ" để trở nên rõ nghĩa khi tìm kiếm tài liệu hay không.

        ### QUY TẮC CỐT LÕI (NGHIÊM NGẶT)
        1. GIỮ NGUYÊN câu hỏi gốc nếu:
        - Nó đã đủ rõ ràng (có đầy đủ chủ ngữ, vị ngữ, thực thể).
        - Nó là một chủ đề mới hoàn toàn, không liên quan đến lịch sử.
        2. VIẾT LẠI câu hỏi nếu:
        - Có chứa đại từ thay thế (nó, họ, đó, quy trình này, ông ấy...).
        - Câu hỏi bị cụt, thiếu chủ thể đã được nhắc tới ở phía trên.
        3. PHONG CÁCH VIẾT:
        - Phải là câu hỏi TRỰC TIẾP của người dùng (ví dụ: "Quy trình A là gì?" thay vì "Người dùng muốn biết quy trình A là gì").
        - Tuyệt đối KHÔNG sử dụng các cụm từ dẫn chuyện như: "Bạn đang hỏi về...", "Câu hỏi được viết lại là...", "Nghĩa là...".
        4. ĐẦU RA: Chỉ trả về duy nhất nội dung câu hỏi sau khi xử lý. Không giải thích.

        ### VÍ DỤ MINH HỌA
        - Lịch sử: "Công ty A có chính sách bảo hiểm gì?" -> Câu hỏi mới: "Nó áp dụng cho ai?" 
        => Kết quả: Chính sách bảo hiểm của công ty A áp dụng cho đối tượng nào?
        - Lịch sử: "Hướng dẫn cài đặt VPN." -> Câu hỏi mới: "Tại sao tôi không kết nối được?"
        => Kết quả: Tại sao tôi không kết nối được VPN sau khi cài đặt?
        - Lịch sử: "Quy định nghỉ phép." -> Câu hỏi mới: "Thời tiết hôm nay thế nào?"
        => Kết quả: Thời tiết hôm nay thế nào? (Giữ nguyên vì chủ đề mới)

        ### DỮ LIỆU ĐẦU VÀO
        [LỊCH SỬ]
        {history_str}

        [CÂU HỎI MỚI]
        {user_query}

        KẾT QUẢ:
        """
        
        response = ollama.chat(
            model=NAME_LLM_MODEL,
            messages=[{'role': 'user', 'content': context_prompt}],
            options={'temperature': 0} 
        )

        return response['message']['content'].strip()