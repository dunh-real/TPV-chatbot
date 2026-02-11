import os
import io
import torch
from pathlib import Path
import pypdfium2 as pdfium
from vllm import LLM, SamplingParams

# Cấu hình mặc định
MODEL_NAME = "lightonai/LightOnOCR-2-1B"
INPUT_DIR = "./data/raw_dir"
OUTPUT_DIR = "./data/md_dir"

class OCRService:
    def __init__(self, model_name=MODEL_NAME):
        """
        Khởi tạo model vLLM với các cấu hình tối ưu hóa bộ nhớ.
        Các tham số tương ứng với câu lệnh CLI:
        --limit-mm-per-prompt '{"image": 1}'
        --mm-processor-cache-gb 0
        --no-enable-prefix-caching
        --gpu-memory-utilization 0.25
        """
        print("--- Initializing vLLM Engine ---")
        
        # Thiết lập cấu hình khởi chạy Model
        self.llm = LLM(
            model=model_name,
            trust_remote_code=True,             # Bắt buộc cho model LightOnOCR
            dtype="bfloat16",                   # Khuyên dùng cho model này
            limit_mm_per_prompt={"image": 1},   # Giới hạn 1 ảnh mỗi prompt
            mm_processor_cache_gb=0,            # Tắt cache xử lý ảnh để tiết kiệm RAM
            enable_prefix_caching=False,        # Tương đương --no-enable-prefix-caching
            gpu_memory_utilization=0.25,        # Giới hạn VRAM sử dụng
            enforce_eager=True                  # Thường cần thiết cho các kiến trúc Vision custom
        )

        # Thiết lập tham số sinh văn bản (Sampling Parameters)
        self.sampling_params = SamplingParams(
            temperature=0.2,
            top_p=0.9,
            max_tokens=4096  # Đủ lớn để chứa text của một trang A4 dày đặc
        )

    def process_file(self, file_path):
        """Xử lý một file PDF và lưu kết quả"""
        file_path = Path(file_path)
        output_path = Path(OUTPUT_DIR) / (file_path.stem + ".md")
        
        # Tạo thư mục output nếu chưa có
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Processing: {file_path.name}")
        
        try:
            pdf = pdfium.PdfDocument(file_path)
            num_pages = len(pdf)
            
            full_text = f"# OCR Results: {file_path.name}\n\n"
            
            # Chuẩn bị danh sách inputs cho vLLM (Batch processing nếu muốn tối ưu hơn)
            # Ở đây xử lý từng trang để đảm bảo an toàn bộ nhớ
            for i in range(num_pages):
                print(f"  - Page {i+1}/{num_pages}...", end=" ", flush=True)
                
                # 1. Render trang PDF sang ảnh PIL
                page = pdf[i]
                pil_image = page.render(scale=2.77).to_pil()
                
                # 2. Tạo message format cho vLLM
                # vLLM hỗ trợ truyền trực tiếp đối tượng PIL Image
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "image": pil_image},
                            {"type": "text", "text": "Extract all text from this document and convert to markdown format."}
                        ]
                    }
                ]

                # 3. Gọi hàm chat (Offline inference)
                # vLLM tự động áp dụng chat template của model
                outputs = self.llm.chat(
                    messages=messages, 
                    sampling_params=self.sampling_params,
                    use_tqdm=False # Tắt thanh loading bar của từng request
                )
                
                # 4. Lấy kết quả
                generated_text = outputs[0].outputs[0].text
                print(f"Done ({len(generated_text)} chars)")

                # Append vào nội dung
                full_text += f"## Page {i+1}\n\n{generated_text}\n\n---\n\n"
                
                # Giải phóng tài nguyên ảnh
                pil_image.close()
                page.close() # Quan trọng: đóng page pdfium để tránh leak memory

            # Ghi ra file sau khi xong toàn bộ PDF
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(full_text)
            
            print(f"Saved to: {output_path}")
            
        except Exception as e:
            print(f"\n[ERROR] Failed to process {file_path.name}: {e}")
        finally:
            if 'pdf' in locals():
                pdf.close()