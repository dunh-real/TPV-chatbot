"""
Gemini Service - Gọi Vertex AI Gemini API
Thay thế Ollama local bằng Gemini 2.5 Flash
"""

import os
import json
import logging
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent / ".env")

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiService:
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.model = GEMINI_MODEL
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set in .env")

    def generate(self, prompt: str, json_mode: bool = True, temperature: float = 0.0) -> dict | str:
        """
        Gọi Gemini API và trả về response.
        - json_mode=True: parse response thành dict
        - json_mode=False: trả về raw text
        """
        url = f"{GEMINI_BASE_URL}/{self.model}:generateContent?key={self.api_key}"

        system_instruction = None
        if json_mode:
            system_instruction = "Luôn trả về JSON hợp lệ, không giải thích thêm, không markdown."

        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
            }
        }

        if system_instruction:
            body["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        try:
            resp = requests.post(url, json=body, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            # Extract text from response
            text = data["candidates"][0]["content"]["parts"][0]["text"]

            if json_mode:
                return json.loads(text)
            return text

        except requests.exceptions.HTTPError as e:
            logger.error(f"Gemini API HTTP error: {e} | Response: {e.response.text[:500] if e.response else ''}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Gemini response not valid JSON: {e} | text: {text[:200]}")
            raise
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise


# Singleton
gemini_service = GeminiService()
