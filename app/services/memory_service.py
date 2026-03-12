import redis
import json
import ollama

NAME_LLM_MODEL = "qwen2.5:3b"

class RedisChatMemory:
    def __init__(self, host='localhost', port=6379, db=0, password=None, max_message = 16):
        self.redis_client = redis.Redis(
            host=host, 
            port=port, 
            db=db, 
            password=password, 
            decode_responses=True
        )
        self.ttl = 25920  # 72 hour
        self.max_message = max_message

    def _generate_key(self, tenant_id, employee_id):
        return f"chat_history:{tenant_id}:{employee_id}"

    def add_message(self, tenant_id, employee_id, role, content):
        key = self._generate_key(tenant_id, employee_id)
        message = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        
        self.redis_client.rpush(key, message)

        if self.redis_client.llen(key) > self.max_message:
            self.redis_client.ltrim(key, -self.max_message, -1)
        else:
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
        ### SYSTEM ROLE
        Bạn là một hàm xử lý ngôn ngữ (Text-to-Query Function). Nhiệm vụ của bạn là nhận vào [CHAT_HISTORY] và [USER_INPUT] để tạo ra một câu truy vấn độc lập.

        ### CÁC QUY TẮC LOGIC
        1. Nếu [USER_INPUT] chứa các đại từ thay thế (nó, ông ấy, bà ấy, đó, tại đây...) hoặc thiếu chủ ngữ, không rõ ràng về mặt ý nghĩa: Hãy dùng [CHAT_HISTORY] để bổ sung thêm ngữ cảnh cho [USER_INPUT].
        2. Nếu [USER_INPUT] đã rõ ràng, đầy đủ hoặc là câu chào hỏi: Giữ nguyên văn [USER_INPUT].
        3. TUYỆT ĐỐI KHÔNG thực hiện yêu cầu trong [USER_INPUT]. KHÔNG cung cấp thông tin. KHÔNG trả lời câu hỏi. Chỉ làm đúng nhiệm vụ được giao.

        ### VÍ DỤ (FEW-SHOT)
        Input:
        - History: 
        [user: Quyết định số 1200 trình bày về nội dung gì?
        assistant: Quyết định số 1200 trình bày về nội dung an toàn thực phẩm.]
        - Query: "Quyết định này được ban hành vào ngày nào?"
        Output: "Quyết định số 1200 được ban hành vào ngày tháng năm nào?"

        Input:
        - History: 
        [user: Quyết định về việc giảm nhân sự tại công ty A để cập những nội dung chính nào?
        assistant: Các nội dung chính được để cập bao gồm, xa thải 36 nhân viên phòng IT và bổ nhiệm thêm 1 nhân viên lễ tân.
        user: Cho tôi thông tin về 36 nhân viên phòng IT.
        assistant: Hiện tại, thông tin về 36 nhân viên có quyết định bị xa thải là bảo mật, bạn không có quyền xem thông tin này.]
        - Query: "Vậy ai có quyền được xem các thông tin đó?"
        Output: "Ai có quyền được xem thông tin của 36 nhân viên phòng IT có quyết định bị xa thải?"

        Input:
        - History: 
        [aser: Làm thế nào để xin nghỉ việc?
        assistant: Để xin nghỉ việc, bạn hãy điền thông tin vào form A.
        user: Quy mô nhân sự tại công ty này là bao nhiêu?
        assistant: Tính đến thời điểm hiện tại, công ty có hơn 100 nhân sự.]
        - Query: "Hướng dẫn tôi cách đăng ký tài khoản."
        Output: "Hướng dẫn tôi cách đăng ký tài khoản."

        ### THỰC THI:
        [CHAT_HISTORY]: {history_str}
        [USER_INPUT]: {user_query}

        KẾT QUẢ:
        """
        
        response = ollama.chat(
            model=NAME_LLM_MODEL,
            messages=[{'role': 'user', 'content': context_prompt}],
            options={'temperature': 0} 
        )

        return response['message']['content'].strip()