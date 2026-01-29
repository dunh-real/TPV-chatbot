# 📄 Hướng Dẫn Sử Dụng OCR Service

## 🎯 Tổng Quan

OCR Service sử dụng **LightOnOCR-2-1B** - model OCR state-of-the-art từ LightOn AI để convert PDF files thành Markdown format.

### ⭐ Highlights của LightOnOCR-2-1B:
- ⚡ **Nhanh**: 5.71 pages/s trên H100 GPU
- 💰 **Tiết kiệm**: < $0.01 / 1,000 pages
- 🎯 **Chính xác**: State-of-the-art trên OlmOCR-Bench
- 🌍 **Đa ngôn ngữ**: Hỗ trợ 11+ ngôn ngữ
- 📊 **Đa dạng**: Tables, forms, multi-column layouts, math notation

---

## 🚀 Cài Đặt

### 1. Cài Transformers từ Source

**QUAN TRỌNG**: LightOnOCR-2 yêu cầu transformers version từ source (chưa có trong stable release)

```bash
# Option 1: Sử dụng uv (nhanh hơn)
uv pip install git+https://github.com/huggingface/transformers

# Option 2: Sử dụng pip thông thường
pip install git+https://github.com/huggingface/transformers

# Cài các dependencies khác
pip install pillow pypdfium2
```

### 2. Cài PyTorch với CUDA 12.1

```bash
# Nếu dùng CUDA 12.1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Nếu dùng CPU only
pip install torch torchvision
```

### 3. Cài các dependencies còn lại

```bash
pip install -r requirements.txt
```

### 4. Verify Installation

```bash
# Test model loading
python tests/test_ocr_service.py
```

---

## 📖 Sử Dụng Cơ Bản

### 1. Import Service

```python
from app.services.ocr_service import get_ocr_service

# Get singleton instance (model chỉ load một lần)
ocr_service = get_ocr_service()
```

### 2. Xử Lý Single PDF

#### Method 1: Từ folder data/raw/ (Recommended)

```python
# Đặt file PDF vào data/raw/
# Ví dụ: data/raw/employee_handbook.pdf

markdown_content, markdown_path, num_pages = ocr_service.process_pdf_from_raw_folder(
    "employee_handbook.pdf"
)

print(f"Processed {num_pages} pages")
print(f"Markdown saved to: {markdown_path}")
# Output: data/markdown/employee_handbook.md
```

#### Method 2: Từ bất kỳ đường dẫn nào

```python
markdown_content, num_pages = ocr_service.process_pdf(
    pdf_path="/path/to/document.pdf",
    output_markdown_path="/path/to/output.md"  # Optional
)

print(markdown_content)  # Xem nội dung markdown
```

### 3. Batch Processing Nhiều PDFs

```python
# Xử lý tất cả PDF files trong data/raw/
results = ocr_service.batch_process_folder()

# Xem kết quả
for result in results:
    if result["success"]:
        print(f"✅ {result['pdf_file']}: {result['num_pages']} pages")
    else:
        print(f"❌ {result['pdf_file']}: {result['error']}")
```

### 4. Batch Processing Custom Folder

```python
results = ocr_service.batch_process_folder(
    input_folder="path/to/pdfs",
    output_folder="path/to/markdowns",
    file_pattern="*.pdf"  # Hoặc "invoice_*.pdf" để filter
)
```

---

## 🔧 Configuration

Các cấu hình có thể thay đổi trong file `.env`:

```env
# OCR Configuration
OCR_DEVICE=cuda              # cuda, cpu, hoặc mps (Mac)

# Data Paths
DATA_RAW_PATH=./data/raw
DATA_MARKDOWN_PATH=./data/markdown
```

### Advanced Configuration (trong code)

```python
from app.services.ocr_service import OCRService

# Custom configuration
ocr_service = OCRService(
    model_name="lightonai/LightOnOCR-2-1B",  # Hoặc variant khác
    device="cuda",
    dtype=torch.bfloat16
)

# Thay đổi generation parameters
ocr_service.max_new_tokens = 4096
ocr_service.temperature = 0.2
ocr_service.top_p = 0.9
```

---

## 📊 Output Format

### Markdown Structure

```markdown
# document_name

*Extracted from: document_name.pdf*
*Total pages: 15*
*Processed at: 2026-01-30 10:30:00*


<!-- Page 1 -->

# Main Title

## Section 1

Content from page 1...


<!-- Page 2 -->

## Section 2

Content from page 2...

...
```

### Features của Output:
- ✅ **Headers**: Tự động detect và giữ nguyên cấu trúc headers
- ✅ **Tables**: Preserved trong markdown table format
- ✅ **Lists**: Bullet points và numbered lists
- ✅ **Math**: LaTeX notation cho công thức toán học
- ✅ **Page markers**: Comments đánh dấu từng page
- ✅ **Metadata**: Thông tin document ở đầu file

---

## 🎯 Use Cases

### 1. Upload Endpoint Integration

```python
from fastapi import UploadFile
from app.services.ocr_service import get_ocr_service
import shutil

async def upload_pdf(file: UploadFile):
    # Save uploaded file
    pdf_path = f"data/raw/{file.filename}"
    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Process with OCR
    ocr_service = get_ocr_service()
    markdown_content, markdown_path, num_pages = ocr_service.process_pdf_from_raw_folder(
        file.filename
    )
    
    return {
        "filename": file.filename,
        "pages": num_pages,
        "markdown_path": markdown_path
    }
```

### 2. Scheduled Batch Processing

```python
import schedule
import time
from app.services.ocr_service import get_ocr_service

def process_new_pdfs():
    ocr_service = get_ocr_service()
    results = ocr_service.batch_process_folder()
    # Send notification hoặc log results
    
# Chạy mỗi giờ
schedule.every().hour.do(process_new_pdfs)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### 3. Custom Preprocessing

```python
from PIL import Image
from app.services.ocr_service import get_ocr_service

ocr_service = get_ocr_service()

# Process custom image
with Image.open("custom_scan.png") as img:
    # Resize nếu cần
    if max(img.size) > 1540:
        img.thumbnail((1540, 1540))
    
    # OCR
    text = ocr_service.ocr_image(img)
    print(text)
```

---

## 🐛 Troubleshooting

### 1. Import Error: transformers

**Lỗi**: `ImportError: cannot import name 'LightOnOcrForConditionalGeneration'`

**Giải pháp**:
```bash
# Uninstall transformers từ PyPI
pip uninstall transformers

# Cài từ source
pip install git+https://github.com/huggingface/transformers
```

### 2. CUDA Out of Memory

**Lỗi**: `RuntimeError: CUDA out of memory`

**Giải pháp**:
```python
# Option 1: Dùng CPU
ocr_service = OCRService(device="cpu")

# Option 2: Reduce batch size (trong batch processing)
# Process từng file một thay vì batch

# Option 3: Clear cache
import torch
torch.cuda.empty_cache()
```

### 3. Slow Processing

**Kiểm tra**:
```python
ocr_service = get_ocr_service()
print(f"Device: {ocr_service.device}")  # Should be "cuda" not "cpu"
print(f"Dtype: {ocr_service.dtype}")    # Should be bfloat16 on CUDA
```

**Tối ưu**:
- Đảm bảo đang dùng GPU
- Check CUDA driver và PyTorch compatibility
- Monitor GPU usage: `nvidia-smi -l 1`

### 4. Poor OCR Quality

**Tips**:
- Đảm bảo PDF quality tốt (không quá nhoè)
- Check resolution sau render (should be ~1540px longest dimension)
- Try với các model variants:
  - `lightonai/LightOnOCR-2-1B` - Best general performance
  - `lightonai/LightOnOCR-2-1B-ocr-soup` - Extra robustness

---

## 📈 Performance Benchmarks

### Expected Performance (Single H100):
- **Speed**: ~5.7 pages/second
- **Cost**: < $0.01 per 1,000 pages
- **Throughput**: ~493,000 pages/day

### Typical Processing Times:

| Pages | GPU (H100) | GPU (A100) | GPU (RTX 3090) | CPU |
|-------|-----------|-----------|----------------|-----|
| 1     | ~0.18s    | ~0.25s    | ~0.40s         | ~5s |
| 10    | ~1.8s     | ~2.5s     | ~4s            | ~50s|
| 100   | ~18s      | ~25s      | ~40s           | ~500s|

*Note: Times vary based on document complexity*

---

## 🔍 Model Variants

LightOnOCR-2 có nhiều variants cho different use cases:

| Model | Use Case |
|-------|----------|
| **LightOnOCR-2-1B** | ⭐ Best for production (RLVR refined) |
| LightOnOCR-2-1B-base | For fine-tuning |
| LightOnOCR-2-1B-bbox | Includes image bounding boxes |
| LightOnOCR-2-1B-ocr-soup | Extra robustness |

Để thay đổi variant:
```python
ocr_service = OCRService(
    model_name="lightonai/LightOnOCR-2-1B-bbox"  # Example
)
```

---

## 📚 Tham Khảo

- [LightOnOCR-2 Model Card](https://huggingface.co/lightonai/LightOnOCR-2-1B)
- [Paper](https://huggingface.co/papers/lightonocr-2)
- [Blog Post](https://huggingface.co/blog/lightonai/lightonocr-2)
- [Demo](https://huggingface.co/spaces/lightonai/LightOnOCR-2-1B-Demo)

---

## ✅ Next Steps

Sau khi có markdown từ OCR:
1. ✅ OCR Service → **DONE**
2. 🔄 Chunking Service → Chia markdown thành chunks (next step)
3. 🔄 Vector Service → Embed và store vào Qdrant
4. 🔄 RAG Pipeline → Kết nối tất cả

**Ready to move to next step:** [Chunking Service](../services/chunking_service.py)