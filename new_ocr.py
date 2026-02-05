# from transformers import pipeline

# pipe = pipeline("image-to-text", model = "zai-org/GLM-OCR")

# load model directly
from transformers import AutoTokenizer, AutoModelForImageTextToText, AutoProcessor
import torch

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# tokenizer = AutoTokenizer.from_pretrained("zai-org/GLM-OCR")
model = AutoModelForImageTextToText.from_pretrained("zai-org/GLM-OCR")
model.to(device)

# import fitz
# import os

# doc = fitz.open("./data/raw/cv.pdf")
# output_dir = "./data/markdown"

# if not os.path.exists(output_dir):
#     os.makedirs(output_dir)

# for page_num in range(doc.page_count):
#     page = doc.load_page(page_num)
#     pix = page.get_pixmap(dpi=300)
#     image_path = os.path.join(output_dir, f"page_{page_num + 1}.png")
#     pix.save(image_path)
#     print(f"Saved {image_path}")

# doc.close()

MODEL_PATH = "zai-org/GLM-OCR"
messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image",
                "url": "./data/markdown/page_1.png"
            },
            {
                "type": "text",
                "text": "Text Recognition:"
            }
        ],
    }
]

processor = AutoProcessor.from_pretrained(MODEL_PATH)
# model = AutoModelForImageTextToText.from_pretrained(
#     pretrained_model_name_or_path = MODEL_PATH,
#     torch_dtype = "auto",
#     device_map = "auto"
# )
inputs = processor.apply_chat_template(
    messages,
    tokenize = True,
    add_generation_prompt = True,
    return_dict = True,
    return_tensors = "pt"
).to(model.device)
inputs.pop("token_type_ids", None)
generated_ids = model.generate(**inputs, max_new_tokens = 8192)
output_text = processor.decode(generated_ids[0][inputs["input_ids"].shape[1]:], skip_special_tokens = False)
print(output_text)