import torch
import pypdfium2 as pdfium
from PIL import Image
from transformers import AutoModel, AutoProcessor

device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float32 if device == "mps" else torch.bfloat16

model = AutoModel.from_pretrained("lightonai/LightOnOCR-2-1B", torch_dtype = dtype).to(device)
processor = AutoProcessor.from_pretrained("lightonai/LightOnOCR-2-1B")

path = "./data/raw/cv.pdf"
pdf = pdfium.PdfDocument(path)
page = pdf[0]
pil_image = page.render(scale = 2.77).to_pil()

inputs = processor(images = pil_image, return_tensors = "pt").to(device, torch.bfloat16)
generated_ids = model.generate(**inputs, max_new_tokens = 4096)
generated_text = processor.batch_decode(generated_ids, skip_special_tokens = False)[0]

print(generated_text)