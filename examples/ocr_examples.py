"""
Example: Sử dụng OCR Service
Các ví dụ thực tế về cách sử dụng OCR Service
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.ocr_service import get_ocr_service, OCRService
from app.utils.logger import get_logger
from PIL import Image

logger = get_logger(__name__)


def example_1_basic_usage():
    """
    Example 1: Basic Usage - Process một PDF file
    """
    print("\n" + "="*80)
    print("EXAMPLE 1: Basic PDF Processing")
    print("="*80)
    
    # Get OCR service (singleton)
    ocr_service = get_ocr_service()
    
    # Giả sử bạn có file: data/raw/sample.pdf
    pdf_filename = "sample.pdf"
    
    try:
        # Process PDF
        markdown_content, markdown_path, num_pages = ocr_service.process_pdf_from_raw_folder(
            pdf_filename
        )
        
        print(f"\n✅ Processed successfully!")
        print(f"Input: data/raw/{pdf_filename}")
        print(f"Output: {markdown_path}")
        print(f"Pages: {num_pages}")
        
        # Print preview
        print(f"\nPreview (first 300 chars):")
        print("-" * 80)
        print(markdown_content[:300])
        print("-" * 80)
        
    except FileNotFoundError:
        print(f"\n⚠️  Please create data/raw/{pdf_filename} first")


def example_2_batch_processing():
    """
    Example 2: Batch Processing - Process nhiều PDFs cùng lúc
    """
    print("\n" + "="*80)
    print("EXAMPLE 2: Batch Processing")
    print("="*80)
    
    ocr_service = get_ocr_service()
    
    # Process all PDFs in data/raw/
    results = ocr_service.batch_process_folder()
    
    if not results:
        print("\n⚠️  No PDF files found in data/raw/")
        return
    
    # Summary
    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful
    total_pages = sum(r["num_pages"] for r in results if r["success"])
    
    print(f"\n📊 Summary:")
    print(f"  Total files: {len(results)}")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Total pages: {total_pages}")
    
    # Detailed results
    print(f"\n📄 Detailed Results:")
    for i, result in enumerate(results, 1):
        status = "✅" if result["success"] else "❌"
        pdf_name = Path(result["pdf_file"]).name
        
        print(f"\n{i}. {status} {pdf_name}")
        if result["success"]:
            print(f"   Pages: {result['num_pages']}")
            print(f"   Time: {result['processing_time']:.2f}s")
            print(f"   Output: {result['markdown_file']}")
        else:
            print(f"   Error: {result['error']}")


def example_3_custom_paths():
    """
    Example 3: Custom Paths - Process từ custom folders
    """
    print("\n" + "="*80)
    print("EXAMPLE 3: Custom Paths")
    print("="*80)
    
    ocr_service = get_ocr_service()
    
    # Custom input/output folders
    custom_input = "path/to/my/pdfs"  # Change this
    custom_output = "path/to/my/markdowns"  # Change this
    
    print(f"Input folder: {custom_input}")
    print(f"Output folder: {custom_output}")
    
    try:
        results = ocr_service.batch_process_folder(
            input_folder=custom_input,
            output_folder=custom_output,
            file_pattern="*.pdf"  # Có thể filter: "invoice_*.pdf"
        )
        
        print(f"\nProcessed {len(results)} files")
        
    except Exception as e:
        print(f"⚠️  Error: {e}")


def example_4_process_custom_pdf():
    """
    Example 4: Process PDF từ bất kỳ đường dẫn nào
    """
    print("\n" + "="*80)
    print("EXAMPLE 4: Custom PDF Path")
    print("="*80)
    
    ocr_service = get_ocr_service()
    
    # Specify full paths
    pdf_path = "/absolute/path/to/document.pdf"
    output_path = "/absolute/path/to/output.md"
    
    try:
        markdown_content, num_pages = ocr_service.process_pdf(
            pdf_path=pdf_path,
            output_markdown_path=output_path
        )
        
        print(f"✅ Processed {num_pages} pages")
        print(f"Saved to: {output_path}")
        
    except FileNotFoundError:
        print(f"⚠️  File not found: {pdf_path}")
    except Exception as e:
        print(f"❌ Error: {e}")


def example_5_process_single_image():
    """
    Example 5: OCR trực tiếp từ image (không cần PDF)
    """
    print("\n" + "="*80)
    print("EXAMPLE 5: Process Single Image")
    print("="*80)
    
    ocr_service = get_ocr_service()
    
    # Load một image
    image_path = "path/to/image.png"  # Change this
    
    try:
        with Image.open(image_path) as img:
            # Resize nếu quá lớn (longest dimension = 1540px)
            if max(img.size) > 1540:
                ratio = 1540 / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # OCR
            text = ocr_service.ocr_image(img)
            
            print(f"\n✅ OCR completed!")
            print(f"Image size: {img.size}")
            print(f"\nExtracted text:")
            print("-" * 80)
            print(text[:500])  # First 500 chars
            print("-" * 80)
            
    except FileNotFoundError:
        print(f"⚠️  Image not found: {image_path}")
    except Exception as e:
        print(f"❌ Error: {e}")


def example_6_custom_configuration():
    """
    Example 6: Custom Configuration - Thay đổi settings
    """
    print("\n" + "="*80)
    print("EXAMPLE 6: Custom Configuration")
    print("="*80)
    
    # Create custom OCR service với custom settings
    custom_ocr = OCRService(
        model_name="lightonai/LightOnOCR-2-1B",
        device="cuda",  # hoặc "cpu", "mps"
    )
    
    # Thay đổi generation parameters
    custom_ocr.max_new_tokens = 8192  # More tokens cho documents dài
    custom_ocr.temperature = 0.1  # Even more deterministic
    custom_ocr.top_p = 0.95
    
    print(f"Configuration:")
    print(f"  Model: {custom_ocr.model_name}")
    print(f"  Device: {custom_ocr.device}")
    print(f"  Max tokens: {custom_ocr.max_new_tokens}")
    print(f"  Temperature: {custom_ocr.temperature}")
    print(f"  Top-p: {custom_ocr.top_p}")
    
    # Use it
    # custom_ocr.process_pdf(...)


def example_7_monitoring_progress():
    """
    Example 7: Monitor Processing Progress
    """
    print("\n" + "="*80)
    print("EXAMPLE 7: Monitoring Progress")
    print("="*80)
    
    from tqdm import tqdm
    import time
    
    ocr_service = get_ocr_service()
    
    # Get list of PDFs
    input_folder = Path(settings.data_raw_path)
    pdf_files = list(input_folder.glob("*.pdf"))
    
    if not pdf_files:
        print("⚠️  No PDF files found")
        return
    
    print(f"Found {len(pdf_files)} PDF files to process")
    
    results = []
    
    # Process với progress bar
    for pdf_path in tqdm(pdf_files, desc="Processing PDFs"):
        try:
            start = time.time()
            
            markdown_content, num_pages = ocr_service.process_pdf(
                str(pdf_path),
                str(Path(settings.data_markdown_path) / f"{pdf_path.stem}.md")
            )
            
            elapsed = time.time() - start
            
            results.append({
                "file": pdf_path.name,
                "pages": num_pages,
                "time": elapsed,
                "success": True
            })
            
        except Exception as e:
            results.append({
                "file": pdf_path.name,
                "error": str(e),
                "success": False
            })
    
    # Summary
    print(f"\n✅ Completed!")
    successful = sum(1 for r in results if r["success"])
    total_pages = sum(r.get("pages", 0) for r in results)
    total_time = sum(r.get("time", 0) for r in results)
    
    print(f"Successful: {successful}/{len(results)}")
    print(f"Total pages: {total_pages}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Average: {total_time/len(results):.2f}s per file")


def main():
    """Run all examples"""
    print("\n" + "="*80)
    print("🚀 OCR SERVICE EXAMPLES")
    print("="*80)
    
    examples = [
        ("Basic Usage", example_1_basic_usage),
        ("Batch Processing", example_2_batch_processing),
        ("Custom Paths", example_3_custom_paths),
        ("Custom PDF Path", example_4_process_custom_pdf),
        ("Single Image", example_5_process_single_image),
        ("Custom Configuration", example_6_custom_configuration),
        ("Monitoring Progress", example_7_monitoring_progress),
    ]
    
    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    print("  0. Run all")
    print("  q. Quit")
    
    choice = input("\nSelect example to run (0-7, q): ").strip().lower()
    
    if choice == 'q':
        return
    elif choice == '0':
        for name, func in examples:
            try:
                func()
            except Exception as e:
                logger.error(f"Error in {name}: {e}", exc_info=True)
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(examples):
                examples[idx][1]()
            else:
                print("Invalid choice!")
        except ValueError:
            print("Invalid input!")


if __name__ == "__main__":
    from app.core.config import settings
    
    main()