import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'data.db')}"

UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
MAX_IMAGES = 9
MAX_IMAGE_SIZE_MB = 10

LLM_CONFIG = {
    "provider": "openai_compatible",
    "model_name": "qwen-coder-turbo-0919",
    "api_key": "sk-2779612cd26547fab22f55d641926d9f",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "stream": False,
}
