"""
Test script cho OCR Service
Chạy file này để test OCR functionality
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.ocr_service import get_ocr_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


def test_single_pdf():
    """Test xử lý một file PDF"""
    print("=" * 80)
    print("TEST 1: Processing single PDF file")
    print("=" * 80)
    
    # Initialize service
    ocr_service = get_ocr_service()
    
    # Test with a sample PDF (bạn cần đặt file PDF vào data/raw/)
    # Ví dụ: data/raw/sample.pdf
    pdf_filename = "sample.pdf"
    
    try:
        markdown_content, markdown_path, num_pages = ocr_service.process_pdf_from_raw_folder(
            pdf_filename
        )
        
        print(f"\n✅ SUCCESS!")
        print(f"PDF: {pdf_filename}")
        print(f"Pages: {num_pages}")
        print(f"Markdown saved to: {markdown_path}")
        print(f"\nFirst 500 characters of output:")
        print("-" * 80)
        print(markdown_content[:500])
        print("-" * 80)
        
    except FileNotFoundError:
        print(f"\n⚠️  File not found: data/raw/{pdf_filename}")
        print("Please place a PDF file in data/raw/ folder first")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


def test_batch_processing():
    """Test xử lý batch nhiều PDF files"""
    print("\n" + "=" * 80)
    print("TEST 2: Batch processing all PDFs in data/raw/")
    print("=" * 80)
    
    # Initialize service
    ocr_service = get_ocr_service()
    
    try:
        results = ocr_service.batch_process_folder()
        
        print(f"\n✅ Batch processing completed!")
        print(f"Total files processed: {len(results)}")
        
        # Print results
        for i, result in enumerate(results, 1):
            status = "✅" if result["success"] else "❌"
            print(f"\n{status} File {i}:")
            print(f"  PDF: {Path(result['pdf_file']).name}")
            if result["success"]:
                print(f"  Markdown: {Path(result['markdown_file']).name}")
                print(f"  Pages: {result['num_pages']}")
                print(f"  Time: {result['processing_time']:.2f}s")
            else:
                print(f"  Error: {result['error']}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


def test_model_loading():
    """Test loading model"""
    print("\n" + "=" * 80)
    print("TEST 0: Model Loading Test")
    print("=" * 80)
    
    try:
        ocr_service = get_ocr_service()
        ocr_service.load_model()
        
        print("\n✅ Model loaded successfully!")
        print(f"Device: {ocr_service.device}")
        print(f"Dtype: {ocr_service.dtype}")
        print(f"Model: {ocr_service.model_name}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nNote: LightOnOCR-2 requires transformers from source:")
        print("  pip install git+https://github.com/huggingface/transformers")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n🚀 OCR Service Test Suite\n")
    
    # Test 0: Model loading
    test_model_loading()
    
    # Test 1: Single PDF
    # test_single_pdf()  # Uncomment khi có file PDF trong data/raw/
    
    # Test 2: Batch processing
    # test_batch_processing()  # Uncomment khi có files trong data/raw/
    
    print("\n" + "=" * 80)
    print("Tests completed!")
    print("=" * 80)