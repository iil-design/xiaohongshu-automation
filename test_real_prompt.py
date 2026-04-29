import os
import requests
import time

from dotenv import load_dotenv
load_dotenv()

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
if not DASHSCOPE_API_KEY:
    raise RuntimeError("请设置环境变量 DASHSCOPE_API_KEY")
DASHSCOPE_IMAGE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

# Realistic prompt like what the content agent would produce
prompt = "一位年轻女生坐在书桌前用笔记本电脑编辑小红书，桌上放着咖啡和手账本，温暖的阳光从窗户洒入，日系简约风格，暖黄调，温馨治愈氛围"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
}

payload = {
    "model": "wan2.6-t2i",
    "input": {
        "messages": [{"role": "user", "content": [{"text": prompt}]}]
    },
    "parameters": {
        "n": 1,
        "size": "1280*1280",
        "watermark": False,
        "prompt_extend": True,
    },
}

print(f"Start: {time.strftime('%H:%M:%S')}")
t0 = time.time()
resp = requests.post(DASHSCOPE_IMAGE_URL, headers=headers, json=payload, timeout=120)
t1 = time.time()
print(f"API response: {resp.status_code} ({t1-t0:.1f}s)")

if resp.status_code == 200:
    data = resp.json()
    choices = data.get("output", {}).get("choices", [])
    if choices:
        url = choices[0].get("message", {}).get("content", [{}])[0].get("image", "")
        print(f"Image URL: {url[:80]}...")
        # Download
        t2 = time.time()
        img = requests.get(url, timeout=60)
        t3 = time.time()
        print(f"Download: {img.status_code} ({t3-t2:.1f}s), size={len(img.content)} bytes")
    else:
        print("No choices in response")
        print(resp.text[:500])
else:
    print(resp.text[:500])
