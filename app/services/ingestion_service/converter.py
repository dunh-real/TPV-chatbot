from pathlib import Path
from model_service.ocr_service import OCRService

PATH_INPUT_DIR = ""
PATH_OUTPUT_DIR = ""

ocr_client = OCRService()

class DocumentConverter:
    def __init__(self):
        pass

    def convert(self, path_input_dir=PATH_INPUT_DIR, path_output_dir=PATH_OUTPUT_DIR):
            """
            Chuyển đổi file sang Markdown. Đầu vào cho phép: file pdf scan
            """
            pdf_files = list(Path(path_input_dir).glob("*.pdf"))

            for pdf_file in pdf_files:
                md_file = path_output_dir / (pdf_file.stem + ".md")

                ocr_client.ocr_image(pdf_file, md_file)