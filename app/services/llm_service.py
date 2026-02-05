import ollama
import json
import torch
import os
from langchain_core.messages import BaseMessage, AIMessage, SystemMessage, HumanMessage
from typing import List, Any
from transformers import AutoModelForSequenceClassification, AutoTokenizer

NAME_LLM_MODEL = "qwen2.5:7b"
NAME_RERANKER_MODEL = "AITeamVN/Vietnamese_Reranker"
MODEL_CACHE_FOLDER = os.path.join(os.path.dirname(__file__), "models_cache")
os.makedirs(MODEL_CACHE_FOLDER, exist_ok=True) 

# Reranking context result (Top 5) -> Prompt for system -> LLM -> Final answer (JSON)

# LLM service
class OllamaChatLLM:
    def __init__(self, model_name: str = NAME_LLM_MODEL):
        self.model_name = model_name
        self.options = {
            "temperature": 0.2,
            "num_ctx": 8192,    # Context window
        }

    def invoke(self, messages: List[BaseMessage]):
        payload = []
        for m in messages:
            role = "user"
            if isinstance(m, SystemMessage): role = "system"
            elif isinstance(m, AIMessage): role = "assistant"
            
            payload.append({
                "role": role, 
                "content": m.content
            })

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=payload,
                format='json',
                options=self.options
            )
            
            text_result = response['message']['content']

            parsed_json = json.loads(text_result)
            final_answer = parsed_json.get("answer", "")
            citation = parsed_json.get("citation", "")
            
            return AIMessage(content=final_answer), citation
            
        except Exception as e:
            return AIMessage(content=f"Lỗi kết nối Ollama: {str(e)}")
        
# Reranker service
class RerankerService:
    def __init__(self, model_name = NAME_RERANKER_MODEL, cache_folder = MODEL_CACHE_FOLDER):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, 
            cache_dir=cache_folder,
            use_fast=False)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            cache_dir=cache_folder
        ).to(self.device)
        self.model.eval()

    def rerank(self, query: str, documents: List[Any], top_k: int = 5) -> List[Any]:
        """
        Chấm điểm lại danh sách documents dựa trên query.
        
        Args:
            query: Câu hỏi người dùng.
            documents: Danh sách kết quả trả về từ Qdrant (ScoredPoint).
            top_k: Số lượng kết quả tốt nhất muốn giữ lại.
        
        Returns:
            Danh sách documents đã được sắp xếp lại và cắt top_k.
        """
        if not documents:
            return []

        pairs = []
        valid_docs = []

        for doc in documents:
            content = doc.payload.get('content')
            if content:
                pairs.append([query, content])
                valid_docs.append(doc)
        
        if not pairs:
            return []

        with torch.no_grad():
            inputs = self.tokenizer(pairs, padding=True, truncation=True, return_tensors='pt', max_length=2304).to(self.device)
            scores = self.model(**inputs, return_dict=True).logits.view(-1, ).float()

        if isinstance(scores, float):
            scores = [scores]

        results = []
        for doc, score in zip(valid_docs, scores):
            doc.score = score
            results.append(doc)

        results.sort(key=lambda x: x.score, reverse=True)

        return results[:top_k]

# Prompt service
class PromptBuilder:
    def __init__(self):
        # 1. Định nghĩa các thành phần của Prompt
        
        # Persona + Nhiệm vụ
        self.intro_template = """
        Bạn là chuyên gia phân tích dữ liệu và trợ lý AI nội bộ cao cấp.
        NHIỆM VỤ: Trả lời câu hỏi dựa trên các tài liệu doanh nghiệp được cung cấp trong thẻ <context>.
        TONE GIỌNG: Chuyên nghiệp, khách quan, phân tích sâu sắc, dùng ngôn ngữ Tiếng Việt (trừ khi người dùng hỏi bằng ngôn ngữ khác).
        """

        # Phần quy tắc (Gia cố phần trích dẫn và xử lý mâu thuẫn)
        self.rules_template = """
        QUY TẮC BẮT BUỘC (TUÂN THỦ TUYỆT ĐỐI):
        
        1. **NGUYÊN TẮC VÀNG - ANTI-HALLUCINATION**: 
            - Chỉ sử dụng thông tin nằm trong <context>. 
            - Tuyệt đối KHÔNG dùng kiến thức bên ngoài. 
            - Tuyệt đối KHÔNG tự suy diễn số liệu hay tên văn bản nếu không thấy rõ.

        2. **ĐỘ CHI TIẾT & TỔNG HỢP**:
            - Câu trả lời cần thật chi tiết, đầy đủ quy trình/bước (nếu có).
            - Nếu thông tin nằm rải rác ở nhiều chunk (đoạn văn), hãy TỔNG HỢP lại thành một câu trả lời mạch lạc, tránh lặp lại ý.
            - Nếu các tài liệu có thông tin mâu thuẫn nhau: Hãy nêu rõ sự mâu thuẫn đó (Ví dụ: "Tài liệu A nói X, nhưng tài liệu B nói Y").

        3. **TƯƠNG TÁC NGƯỜI DÙNG & XỬ LÝ LỊCH SỬ**:
            - Luôn kiểm tra [LỊCH SỬ TRÒ CHUYỆN] để hiểu các câu hỏi tiếp nối. 
            - Giải mã các đại từ thay thế (ví dụ: "nó", "quy trình này", "ông ấy") dựa trên các thực thể đã nhắc tới trong lịch sử.
            - Nếu người dùng chỉ trò chuyện bình thường (ví dụ: "chào bạn", "cảm ơn", "ok"), hãy trả lời tự nhiên, thân thiện và KHÔNG trích dẫn nguồn tài liệu.
            - Tuyệt đối tuân thủ bảo mật và an toàn thông tin ngay cả khi trò chuyện phiếm.

        4. **QUẢN LÝ LUỒNG HỘI THOẠI (TRÍ NHỚ)**:
            - **Tránh lặp lại vô nghĩa**: Nếu câu hỏi mới của người dùng đã được trả lời chính xác ở ngay câu phía trên trong [LỊCH SỬ], hãy tóm tắt ngắn gọn và hỏi xem họ có cần chi tiết thêm ở khía cạnh nào khác không.
            - **Tính nhất quán**: Đảm bảo câu trả lời hiện tại không mâu thuẫn với các câu trả lời bạn đã đưa ra trong lịch sử (trừ khi thông tin trong <context> mới nhất có sự cập nhật).
            - **Xử lý câu hỏi bổ sung**: Nếu người dùng hỏi "Tại sao?", "Còn gì nữa không?", hãy kết hợp cả [LỊCH SỬ] để biết họ đang hỏi "Tại sao" cho vấn đề gì và dùng <context> để tìm lời giải.

        5. **PHÂN TÁCH NGUỒN TRI THỨC**:
            - Sử dụng [LỊCH SỬ] để hiểu Ý ĐỊNH (Intent) và NGỮ CẢNH (Context) của người hỏi.
            - Sử dụng <context> làm CĂN CỨ DUY NHẤT để đưa ra sự thật (Facts).

        6. **TRÍCH DẪN NGUỒN CHÍNH XÁC**:
            - Cuối mỗi luận điểm quan trọng, BẮT BUỘC ghi nguồn.
            - Định dạng: [Nguồn: Tên file - Tiêu đề mục (nếu có)].
            - **LƯU Ý ĐẶC BIỆT**: `<src_file>` phải lấy CHÍNH XÁC từng ký tự trong ngữ cảnh: "src_file":"document_18_output.md" => trả về nguồn là "document_18_output.md".
            - KHÔNG ĐƯỢC bịa ra tên nguồn, số Điều/Khoản nếu trong đoạn văn không ghi rõ.

        7. **XỬ LÝ THIẾU TIN**: 
            - Nếu không tìm thấy thông tin trong <context>, hãy trả lời: "Dựa trên các tài liệu được cung cấp, không có thông tin về vấn đề này." (Không được tự ý trả lời xã giao hay xin lỗi vòng vo).

        8. **TRÌNH BÀY**: 
            - Câu trả lời là đoạn văn bản mạch lạc, rõ ràng, tuần tự, có đầu cuối.
            - Nếu đầu ra cần xuất dạng bảng biểu hãy dùng Markdown: Headings (#, ##, ###), Bold (**text**), Bullet points (-), Numbered list (1. 2. 3.), Italic (*text*), Blockquote (>).
            - Sử dụng Markdown chuyên nghiệp, ví dụ dùng bảng (Table) nếu so sánh dữ liệu. Dùng Bold (**text**) cho các từ khóa quan trọng.
            - TUYỆT ĐỐI KHÔNG xuất markdown mọi lúc, chỉ dùng khi cần.
        """

        # Phần Reasoning (Thêm bước kiểm tra lại)
        self.reasoning_instructions = """
        HƯỚNG DẪN FORMAT ĐẦU RA (REASONING MODE):
        Bạn cần thực hiện chuỗi suy luận (Chain-of-Thought) trước khi đưa ra kết quả cuối cùng:

        • BƯỚC 1: PHÂN TÍCH & TÌM KIẾM
          - Xác định các từ khóa chính trong câu hỏi.
          - Liệt kê các đoạn (chunks) trong <context> có chứa thông tin liên quan.
          - Đánh giá độ tin cậy và sự liên quan của từng chunk.

        • BƯỚC 2: TỔNG HỢP & GIẢI QUYẾT MÂU THUẪN
          - Sắp xếp thông tin theo trình tự logic.
          - Nếu có mâu thuẫn giữa các file, xác định cách trình bày (nêu cả 2 hoặc chọn file mới hơn nếu có ngày tháng).

        • BƯỚC 3: CÂU TRẢ LỜI CHI TIẾT (FINAL ANSWER)
          - Trình bày câu trả lời hoàn chỉnh dựa trên phân tích trên.

        • BƯỚC 4: DANH SÁCH NGUỒN THAM KHẢO
          - Liệt kê các file `src_file` đã sử dụng.
        """

        # Phần Normal
        self.normal_instructions = """
        HƯỚNG DẪN FORMAT ĐẦU RA:
        - Trả lời thẳng vào vấn đề. Đảm bảo độ chi tiết cao như yêu cầu.
        - Câu trả lời BẮT BUỘC phải viết Tiếng Việt, trừ khi đầu vào là một ngôn ngữ khác.
        - Bạn BẮT BUỘC phải trả về kết quả dưới định dạng JSON hợp lệ, không kèm theo bất kỳ lời dẫn hay giải thích nào khác. Cấu trúc JSON như sau:
            {
                "question": "Câu hỏi gốc hoặc nội dung người dùng vừa nhập",
                "answer": "Nội dung phản hồi",
                "citation": "Tên các file tài liệu dùng để trả lời. Nếu là trò chuyện xã giao hoặc không tìm thấy thông tin, để chuỗi rỗng ''"
            }
            Ví dụ về một câu trả lời đúng cấu trúc:
            {
                "question": "Anh Nguyễn Trọng Bình hiện có bao nhiêu người yêu ?",
                "answer": " Theo thông tin tài liệu được tìm kiếm, hiện tại anh Bình có rất nhiều người yêu. Trong đó đa phần là các diễn viên, ca sĩ hàng đầu Nhật Bản.",
                "citation": "Thông tin bạn gái.pdf"
            }
        """

    def _format_context(self, search_results: List[Any]) -> str:
        """
        Format danh sách documents thành string context.
        """
        if not search_results:
            return "Không có thông tin ngữ cảnh."

        formatted_chunks = []
        for i, point in enumerate(search_results):
            # Lấy payload an toàn
            payload = getattr(point, "payload", {}) if not isinstance(point, dict) else point.get("payload", {})
            content = (payload.get('content') or payload.get('text') or "").strip()
            source = payload.get('src_file', payload.get('filename', 'Không xác định'))
            
            # Thêm header cho từng chunk để LLM phân biệt
            chunk_text = f"--- TÀI LIỆU SỐ [{i+1}] ---\n(Nguồn: {source})\nNội dung:\n{content}\n"
            formatted_chunks.append(chunk_text)

        return "\n\n".join(formatted_chunks)
    
    def _fomat_history(self, chat_history: List[Any]) -> str:
        if not chat_history:
            return "Không có lịch sử trò chuyện"
        
        history_str = ""
        for msg in chat_history:
            role = "user" if msg['role'] == 'user' else "assistant"
            history_str += f"{role}: {msg['content']}\n"

        return history_str
    
    # Respone format
    def build_chat_messages(self, query: str, search_results: List[Any], chat_history: List[Any], reasoning: bool = False) -> List[Any]:
        
        # 1. Chuẩn bị Context
        context_str = self._format_context(search_results)
        history_str = self._fomat_history(chat_history)

        # 2. Chọn hướng dẫn output dựa trên mode reasoning
        output_instruction = self.reasoning_instructions if reasoning else self.normal_instructions

        # 3. Ghép chuỗi System Prompt hoàn chỉnh: Intro -> Rules -> Context -> Output Instructions
        full_system_content = (
            f"{self.intro_template}\n"
            f"{self.rules_template}\n"
            f"\n=== LỊCH SỬ TRÒ CHUYỆN ===\n"
            f"{history_str}\n"
            f"=== KẾT THÚC LỊCH SỬ ===\n"
            f"\n=== BẮT ĐẦU NGỮ CẢNH (CONTEXT) ===\n"
            f"{context_str}\n"
            f"=== KẾT THÚC NGỮ CẢNH ===\n\n"
            f"{output_instruction}"
        )

        # 4. Tạo Messages
        messages = [
            SystemMessage(content=full_system_content),
            HumanMessage(content=query)
        ]

        return messages