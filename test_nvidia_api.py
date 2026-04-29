import os
import requests

from dotenv import load_dotenv
load_dotenv()

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
if not DASHSCOPE_API_KEY:
    raise RuntimeError("请设置环境变量 DASHSCOPE_API_KEY")

url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {DASHSCOPE_API_KEY}"
}

payload = {
    "model": "wan2.6-t2i",
    "input": {
        "messages": [
            {
                "role": "user",
                "content": [{"text": "一间有着精致窗户的花店，漂亮的木质门，摆放着花朵"}]
            }
        ]
    },
    "parameters": {
        "negative_prompt": "",
        "prompt_extend": True,
        "watermark": False,
        "n": 1,
        "size": "1280*1280"
    }
}

try:
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        import json
        data = resp.json()
        # 打印顶层 key
        print("Top-level keys:", list(data.keys()))
        # 打印 output 结构
        if "output" in data:
            out = data["output"]
            print("output keys:", list(out.keys()) if isinstance(out, dict) else type(out).__name__)
            # 深度探索
            print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
    else:
        print(resp.text[:1000])
except Exception as e:
    print(f"Connection failed: {e}")
