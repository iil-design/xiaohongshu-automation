import copy
import json
import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'data.db')}"
CONTENT_DB_URL = f"sqlite:///{os.path.join(BASE_DIR, 'content.db')}"

UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
MAX_IMAGES = 9
MAX_IMAGE_SIZE_MB = 10
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")

CONTENT_MODEL_CONFIG = {
    "provider": "openai_compatible",
    "model_name": "qwen2.5-vl-72b-instruct",
    "api_key": DASHSCOPE_API_KEY,
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "stream": False,
}

MCP_SERVER_URL = "http://localhost:28002/mcp"

SYSTEM_PROMPT_FILE = os.path.join(BASE_DIR, "agent", "system_prompt.md")
AI_CONFIG_FILE = os.path.join(BASE_DIR, "config", "ai_settings.json")

os.makedirs(os.path.dirname(AI_CONFIG_FILE), exist_ok=True)

DEFAULT_AI_SETTINGS = {
    "active_model": "CONTENT_MODEL_CONFIG",
    "temperature": 0.7,
    "models": {
        "CONTENT_MODEL_CONFIG": dict(CONTENT_MODEL_CONFIG),
    },
    "image_gen": {
        "api_key": DASHSCOPE_API_KEY,
        "model": "wan2.6-t2i",
        "size": "1280*1280",
        "watermark": False,
        "prompt_extend": True,
    },
}


def load_ai_settings():
    if os.path.exists(AI_CONFIG_FILE):
        with open(AI_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return dict(DEFAULT_AI_SETTINGS)


def save_ai_settings(settings: dict):
    with open(AI_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def get_active_model_config():
    settings = load_ai_settings()
    active = settings.get("active_model", "CONTENT_MODEL_CONFIG")
    model = copy.deepcopy(settings.get("models", {}).get(active, CONTENT_MODEL_CONFIG))
    model["temperature"] = settings.get("temperature", 0.7)
    return model
