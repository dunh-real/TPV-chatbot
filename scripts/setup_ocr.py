#!/usr/bin/env python3
"""
Setup script cho OCR Service
Tự động cài đặt dependencies và download model
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a shell command với logging"""
    print(f"\n{'='*80}")
    print(f"⚙️  {description}")
    print(f"{'='*80}")
    print(f"Running: {cmd}\n")
    
    result = subprocess.run(cmd, shell=True, capture_output=False, text=True)
    
    if result.returncode != 0:
        print(f"\n❌ Failed: {description}")
        return False
    
    print(f"\n✅ Success: {description}")
    return True


def main():
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║             OCR SERVICE SETUP SCRIPT                          ║
║                                                               ║
║  This script will:                                            ║
║  1. Install transformers from source (required)               ║
║  2. Install PyTorch with CUDA support                         ║
║  3. Install other dependencies                                ║
║  4. Download LightOnOCR-2-1B model (optional)                 ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required!")
        sys.exit(1)
    
    print(f"✅ Python version: {sys.version}")
    
    # 1. Install transformers from source
    if not run_command(
        "pip install git+https://github.com/huggingface/transformers",
        "Installing transformers from source"
    ):
        print("\n⚠️  Warning: Transformers installation might have issues.")
        print("You can try manually:")
        print("  pip install git+https://github.com/huggingface/transformers")
    
    # 2. Install PyTorch
    print("\n" + "="*80)
    print("Installing PyTorch...")
    print("="*80)
    
    choice = input("\nSelect PyTorch version:\n"
                   "  1. CUDA 12.1 (Recommended for GPU)\n"
                   "  2. CUDA 11.8\n"
                   "  3. CPU only\n"
                   "Enter choice (1-3): ").strip()
    
    if choice == "1":
        cmd = "pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121"
    elif choice == "2":
        cmd = "pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118"
    elif choice == "3":
        cmd = "pip install torch torchvision"
    else:
        print("Invalid choice. Installing CPU version...")
        cmd = "pip install torch torchvision"
    
    run_command(cmd, "Installing PyTorch")
    
    # 3. Install other dependencies
    run_command(
        "pip install pillow pypdfium2",
        "Installing PIL and pypdfium2"
    )
    
    # 4. Optional: Pre-download model
    print("\n" + "="*80)
    print("Model Download (Optional)")
    print("="*80)
    
    download = input("\nDo you want to download LightOnOCR-2-1B model now? (y/n): ").strip().lower()
    
    if download == 'y':
        print("\nDownloading model... (this might take a few minutes)")
        
        try:
            from transformers import LightOnOcrForConditionalGeneration, LightOnOcrProcessor
            
            print("Loading processor...")
            processor = LightOnOcrProcessor.from_pretrained("lightonai/LightOnOCR-2-1B")
            
            print("Loading model...")
            model = LightOnOcrForConditionalGeneration.from_pretrained("lightonai/LightOnOCR-2-1B")
            
            print("✅ Model downloaded successfully!")
            print("Model will be cached for future use.")
            
        except Exception as e:
            print(f"⚠️  Failed to download model: {e}")
            print("You can download it later when first using the service.")
    
    # 5. Verify installation
    print("\n" + "="*80)
    print("Verifying Installation...")
    print("="*80)
    
    try:
        import torch
        print(f"✅ PyTorch: {torch.__version__}")
        print(f"   CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"   CUDA version: {torch.version.cuda}")
            print(f"   GPU: {torch.cuda.get_device_name(0)}")
        
        import transformers
        print(f"✅ Transformers: {transformers.__version__}")
        
        from PIL import Image
        print(f"✅ Pillow: {Image.__version__}")
        
        import pypdfium2
        print(f"✅ pypdfium2 installed")
        
    except ImportError as e:
        print(f"⚠️  Import error: {e}")
    
    # Summary
    print("\n" + "="*80)
    print("SETUP COMPLETED!")
    print("="*80)
    print("""
Next steps:
1. Place PDF files in data/raw/
2. Run test: python tests/test_ocr_service.py
3. Check docs: docs/OCR_SERVICE_GUIDE.md

Quick test:
    from app.services.ocr_service import get_ocr_service
    ocr_service = get_ocr_service()
    ocr_service.load_model()
    """)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)