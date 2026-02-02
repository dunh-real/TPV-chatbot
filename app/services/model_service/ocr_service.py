import os
import io
import base64
import torch
import pypdfium2 as pdfium
from transformers import LightOnOcrForConditionalGeneration, LightOnOcrProcessor

MODEL_OCR_NAME = "lightonai/LightOnOCR-2-1B-base"
MODEL_CACHE_FOLDER = os.path.join(os.path.dirname(__file__), "models_cache")
os.makedirs(MODEL_CACHE_FOLDER, exist_ok=True)

class OCRService:
    def __init__(self, model_name = MODEL_OCR_NAME, cache_folder = MODEL_CACHE_FOLDER):
        self.device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.float32 if self.device == "mps" else torch.bfloat16
        
        self.model = LightOnOcrForConditionalGeneration.from_pretrained(model_name, torch_dtype=self.dtype, cache_dir=cache_folder).to(self.device)
        self.processor = LightOnOcrProcessor.from_pretrained(model_name, cache_dir=cache_folder)

    def ocr_image(self, PATH_INPUT_FILE, PATH_OUTPUT_FILE):

        pages= pdfium.PdfDocument(PATH_INPUT_FILE)

        for page_number in range(len(pages)):
            page = pages[page_number]
        
            pil_image = page.render(scale=2.77).to_pil()
            buffer = io.BytesIO()
            pil_image.save(buffer, format="PNG")
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            conversation = [{
                            "role": "user", 
                            "content": [
                                {"type": "image", "url": f"data:image/png;base64,{image_base64}"},
                                {"type": "text", "text": "Extract all text from this document and convert to markdown format."}
                                ]
                            }]

            inputs = self.processor.apply_chat_template(
                conversation,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
            )

            inputs = {k: v.to(device=self.device, dtype=self.dtype) if v.is_floating_point() else v.to(device=self.device) for k, v in inputs.items()}

            output_ids = self.model.generate(**inputs, max_new_tokens=1024)
            generated_ids = output_ids[0, inputs["input_ids"].shape[1]:]
            output_text = self.processor.decode(generated_ids, skip_special_tokens=True)
            
            with open(PATH_OUTPUT_FILE, "a", encoding="utf-8") as f:
                f.write(output_text)

            pil_image.close()
