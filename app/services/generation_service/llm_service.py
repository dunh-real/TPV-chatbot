import ollama
import json
from typing import List
from langchain_core.messages import BaseMessage, AIMessage, SystemMessage

MODEL_NAME = "qwen2.5:7b"

class OllamaChatLLM:
    def __init__(self, model_name: str = MODEL_NAME):
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