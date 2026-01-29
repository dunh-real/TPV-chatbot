"""
OCR Service sử dụng LightOnOCR-2-1B
Xử lý file PDF và convert thành Markdown
"""

import os
import io
import time
from pathlib import Path
from typing import List, Optional, Tuple
import torch
import pypdfium2 as pdfium
from PIL import Image
from transformers import LightOnOcrForConditionalGeneration, LightOnOcrProcessor

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OCRService:
    """
    Service xử lý OCR cho PDF files sử dụng LightOnOCR-2-1B
    
    Features:
    - Load model một lần, cache để tái sử dụng
    - Render PDF pages thành images (1540px longest dimension)
    - OCR từng page và kết hợp thành markdown
    - Xử lý batch nhiều pages cho hiệu quả
    """
    
    def __init__(
        self,
        model_name: str = "lightonai/LightOnOCR-2-1B",
        device: Optional[str] = None,
        dtype: Optional[torch.dtype] = None
    ):
        """
        Khởi tạo OCR Service
        
        Args:
            model_name: Tên model trên HuggingFace (default: lightonai/LightOnOCR-2-1B)
            device: Device để chạy model (cuda/cpu/mps), auto-detect nếu None
            dtype: Data type cho model (bfloat16/float32), auto-select nếu None
        """
        self.model_name = model_name
        
        # Auto-detect device nếu không được chỉ định
        if device is None:
            if torch.backends.mps.is_available():
                self.device = "mps"
            elif torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"
        else:
            self.device = device
        
        # Auto-select dtype dựa trên device
        if dtype is None:
            if self.device == "mps":
                self.dtype = torch.float32
            else:
                self.dtype = torch.bfloat16
        else:
            self.dtype = dtype
        
        logger.info(
            f"Initializing OCR Service with model={model_name}, "
            f"device={self.device}, dtype={self.dtype}"
        )
        
        # Model và processor sẽ được load lazy
        self.model = None
        self.processor = None
        
        # Configuration
        self.target_longest_dimension = 1540  # Theo recommendation của LightOnOCR-2
        self.max_new_tokens = 4096  # Max tokens cho output
        self.temperature = 0.2  # Low temperature cho consistency
        self.top_p = 0.9
    
    def load_model(self):
        """
        Load model và processor (lazy loading)
        Chỉ load một lần, sau đó cache lại
        """
        if self.model is not None and self.processor is not None:
            logger.debug("Model already loaded, skipping...")
            return
        
        logger.info(f"Loading model {self.model_name}...")
        start_time = time.time()
        
        try:
            # Load processor
            self.processor = LightOnOcrProcessor.from_pretrained(self.model_name)
            logger.info("Processor loaded successfully")
            
            # Load model
            self.model = LightOnOcrForConditionalGeneration.from_pretrained(
                self.model_name,
                torch_dtype=self.dtype
            ).to(self.device)
            
            # Set to eval mode
            self.model.eval()
            
            load_time = time.time() - start_time
            logger.info(f"Model loaded successfully in {load_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}", exc_info=True)
            raise RuntimeError(f"Failed to load OCR model: {e}")
    
    def render_pdf_page(
        self,
        pdf_document: pdfium.PdfDocument,
        page_number: int
    ) -> Image.Image:
        """
        Render một page từ PDF thành PIL Image
        
        Args:
            pdf_document: PDF document object
            page_number: Page number (0-indexed)
            
        Returns:
            PIL Image của page
        """
        try:
            page = pdf_document[page_number]
            
            # Tính scale factor để có longest dimension = 1540px
            # LightOnOCR-2 recommend: 1540px longest dimension
            width, height = page.get_size()
            longest = max(width, height)
            scale = self.target_longest_dimension / longest
            
            # Render page với scale factor
            # Note: pypdfium2 scale = DPI / 72, vì vậy scale=2.77 ≈ 200 DPI
            pil_image = page.render(scale=scale).to_pil()
            
            logger.debug(
                f"Rendered page {page_number}: "
                f"original={width}x{height}, "
                f"rendered={pil_image.size}, "
                f"scale={scale:.2f}"
            )
            
            return pil_image
            
        except Exception as e:
            logger.error(f"Failed to render page {page_number}: {e}", exc_info=True)
            raise
    
    def ocr_image(self, image: Image.Image) -> str:
        """
        Thực hiện OCR trên một image
        
        Args:
            image: PIL Image
            
        Returns:
            Extracted text (markdown format)
        """
        # Ensure model is loaded
        self.load_model()
        
        try:
            # Prepare conversation format
            conversation = [
                {
                    "role": "user",
                    "content": [{"type": "image", "image": image}]
                }
            ]
            
            # Apply chat template
            inputs = self.processor.apply_chat_template(
                conversation,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
            )
            
            # Move inputs to device
            inputs = {
                k: v.to(device=self.device, dtype=self.dtype)
                if v.is_floating_point()
                else v.to(self.device)
                for k, v in inputs.items()
            }
            
            # Generate
            with torch.no_grad():
                output_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=self.max_new_tokens,
                    temperature=self.temperature,
                    top_p=self.top_p,
                )
            
            # Decode output
            generated_ids = output_ids[0, inputs["input_ids"].shape[1]:]
            output_text = self.processor.decode(generated_ids, skip_special_tokens=True)
            
            return output_text
            
        except Exception as e:
            logger.error(f"OCR failed: {e}", exc_info=True)
            raise RuntimeError(f"OCR processing failed: {e}")
    
    def process_pdf(
        self,
        pdf_path: str,
        output_markdown_path: Optional[str] = None
    ) -> Tuple[str, int]:
        """
        Xử lý toàn bộ PDF file và convert thành markdown
        
        Args:
            pdf_path: Đường dẫn đến file PDF
            output_markdown_path: Đường dẫn lưu markdown (optional)
            
        Returns:
            Tuple of (markdown_content, num_pages)
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        logger.info(f"Processing PDF: {pdf_path}")
        start_time = time.time()
        
        try:
            # Open PDF
            with open(pdf_path, 'rb') as f:
                pdf_data = f.read()
            
            pdf_document = pdfium.PdfDocument(pdf_data)
            num_pages = len(pdf_document)
            
            logger.info(f"PDF has {num_pages} pages")
            
            # Process each page
            markdown_parts = []
            
            for page_num in range(num_pages):
                logger.info(f"Processing page {page_num + 1}/{num_pages}...")
                page_start = time.time()
                
                # Render page to image
                image = self.render_pdf_page(pdf_document, page_num)
                
                # OCR the image
                page_text = self.ocr_image(image)
                
                # Add page separator và page number
                page_header = f"\n\n<!-- Page {page_num + 1} -->\n\n"
                markdown_parts.append(page_header + page_text)
                
                page_time = time.time() - page_start
                logger.info(f"Page {page_num + 1} processed in {page_time:.2f}s")
            
            # Combine all pages
            full_markdown = "\n\n".join(markdown_parts)
            
            # Add document header
            document_header = f"# {pdf_path.stem}\n\n"
            document_header += f"*Extracted from: {pdf_path.name}*\n"
            document_header += f"*Total pages: {num_pages}*\n"
            document_header += f"*Processed at: {time.strftime('%Y-%m-%d %H:%M:%S')}*\n"
            
            full_markdown = document_header + full_markdown
            
            # Save to file if output path is provided
            if output_markdown_path:
                output_path = Path(output_markdown_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(full_markdown)
                
                logger.info(f"Markdown saved to: {output_path}")
            
            total_time = time.time() - start_time
            pages_per_second = num_pages / total_time
            
            logger.info(
                f"PDF processing completed: "
                f"{num_pages} pages in {total_time:.2f}s "
                f"({pages_per_second:.2f} pages/s)"
            )
            
            return full_markdown, num_pages
            
        except Exception as e:
            logger.error(f"Failed to process PDF: {e}", exc_info=True)
            raise RuntimeError(f"PDF processing failed: {e}")
    
    def process_pdf_from_raw_folder(
        self,
        filename: str
    ) -> Tuple[str, str, int]:
        """
        Xử lý PDF từ folder data/raw và lưu markdown vào data/markdown
        
        Args:
            filename: Tên file PDF trong folder data/raw
            
        Returns:
            Tuple of (markdown_content, markdown_path, num_pages)
        """
        # Construct paths
        pdf_path = Path(settings.data_raw_path) / filename
        
        # Tạo tên file markdown (giữ nguyên tên, chỉ đổi extension)
        markdown_filename = pdf_path.stem + ".md"
        markdown_path = Path(settings.data_markdown_path) / markdown_filename
        
        # Process PDF
        markdown_content, num_pages = self.process_pdf(
            str(pdf_path),
            str(markdown_path)
        )
        
        return markdown_content, str(markdown_path), num_pages
    
    def batch_process_folder(
        self,
        input_folder: Optional[str] = None,
        output_folder: Optional[str] = None,
        file_pattern: str = "*.pdf"
    ) -> List[dict]:
        """
        Xử lý batch tất cả PDF files trong một folder
        
        Args:
            input_folder: Folder chứa PDF files (default: data/raw)
            output_folder: Folder lưu markdown (default: data/markdown)
            file_pattern: Pattern để filter files (default: *.pdf)
            
        Returns:
            List of dicts chứa thông tin processing của từng file
        """
        input_folder = Path(input_folder or settings.data_raw_path)
        output_folder = Path(output_folder or settings.data_markdown_path)
        
        # Find all PDF files
        pdf_files = list(input_folder.glob(file_pattern))
        
        if not pdf_files:
            logger.warning(f"No PDF files found in {input_folder}")
            return []
        
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        results = []
        
        for pdf_path in pdf_files:
            try:
                logger.info(f"Processing: {pdf_path.name}")
                
                # Determine output path
                markdown_filename = pdf_path.stem + ".md"
                markdown_path = output_folder / markdown_filename
                
                # Process
                start_time = time.time()
                markdown_content, num_pages = self.process_pdf(
                    str(pdf_path),
                    str(markdown_path)
                )
                processing_time = time.time() - start_time
                
                results.append({
                    "pdf_file": str(pdf_path),
                    "markdown_file": str(markdown_path),
                    "num_pages": num_pages,
                    "processing_time": processing_time,
                    "success": True,
                    "error": None
                })
                
            except Exception as e:
                logger.error(f"Failed to process {pdf_path.name}: {e}", exc_info=True)
                results.append({
                    "pdf_file": str(pdf_path),
                    "markdown_file": None,
                    "num_pages": 0,
                    "processing_time": 0,
                    "success": False,
                    "error": str(e)
                })
        
        # Summary
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful
        total_pages = sum(r["num_pages"] for r in results)
        total_time = sum(r["processing_time"] for r in results)
        
        logger.info(
            f"Batch processing completed: "
            f"{successful} succeeded, {failed} failed, "
            f"{total_pages} total pages in {total_time:.2f}s"
        )
        
        return results
    
    def __del__(self):
        """Cleanup khi object bị destroy"""
        if self.model is not None:
            logger.debug("Cleaning up OCR model...")
            del self.model
            del self.processor
            
            # Clear CUDA cache if using GPU
            if self.device == "cuda":
                torch.cuda.empty_cache()


# Singleton instance để reuse model
_ocr_service_instance = None

def get_ocr_service() -> OCRService:
    """
    Get singleton instance của OCR Service
    Đảm bảo model chỉ được load một lần
    
    Returns:
        OCRService instance
    """
    global _ocr_service_instance
    
    if _ocr_service_instance is None:
        _ocr_service_instance = OCRService(
            device=settings.ocr_device
        )
    
    return _ocr_service_instance