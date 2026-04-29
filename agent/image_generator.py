import json
import os
import uuid
import threading
import requests

from config import UPLOAD_DIR, load_ai_settings

DASHSCOPE_IMAGE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

# module-level status cache: processed_id -> list[{index, prompt, status, url?, error?}]
_status_cache: dict[int, list[dict]] = {}
_lock = threading.Lock()


def get_status(processed_id: int) -> dict | None:
    """Return status list for a processed_id, or None if not found."""
    with _lock:
        entry = _status_cache.get(processed_id)
    if entry is None:
        return None
    return {
        "processed_id": processed_id,
        "prompts": [dict(p) for p in entry],
    }


def _update_prompt(processed_id: int, index: int, updates: dict):
    with _lock:
        prompts = _status_cache.get(processed_id)
        if not prompts or index >= len(prompts):
            return
        prompts[index].update(updates)


def generate_images(processed_id: int, image_prompts: list[str]) -> None:
    """Background thread: generate images for each prompt, save to static/uploads/."""

    try:
        _generate_images_impl(processed_id, image_prompts)
    except Exception as e:
        print(f"[ImageGen] 线程崩溃 processed_id={processed_id}: {e}")
        import traceback
        traceback.print_exc()
        with _lock:
            entry = _status_cache.get(processed_id)
            if entry:
                for p in entry:
                    if p["status"] not in ("done", "failed"):
                        p["status"] = "failed"
                        p["error"] = f"线程异常: {str(e)[:200]}"


def _generate_images_impl(processed_id: int, image_prompts: list[str]) -> None:

    print(f"[ImageGen] 开始生图 processed_id={processed_id}, prompts={len(image_prompts)}")

    settings = load_ai_settings()
    img_cfg = settings.get("image_gen", {})
    api_key = img_cfg.get("api_key") or settings.get("models", {}).get("VL_MODEL_CONFIG", {}).get("api_key", "")
    model = img_cfg.get("model", "wan2.6-t2i")
    size = img_cfg.get("size", "1280*1280")
    watermark = img_cfg.get("watermark", False)
    prompt_extend = img_cfg.get("prompt_extend", True)

    # Initialize status cache
    with _lock:
        _status_cache[processed_id] = [
            {"index": i, "prompt": p, "status": "pending"}
            for i, p in enumerate(image_prompts)
        ]

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    for i, prompt in enumerate(image_prompts):
        _update_prompt(processed_id, i, {"status": "generating"})

        try:
            # Step 1: Call DashScope to generate image
            payload = {
                "model": model,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"text": prompt}]
                        }
                    ]
                },
                "parameters": {
                    "n": 1,
                    "size": size,
                    "watermark": watermark,
                    "prompt_extend": prompt_extend,
                },
            }
            resp = requests.post(DASHSCOPE_IMAGE_URL, headers=headers, json=payload, timeout=120)
            if resp.status_code != 200:
                _update_prompt(processed_id, i, {"status": "failed", "error": f"DashScope {resp.status_code}"})
                continue

            data = resp.json()
            choices = data.get("output", {}).get("choices", [])
            if not choices:
                _update_prompt(processed_id, i, {"status": "failed", "error": "No choices in response"})
                continue

            image_url = choices[0].get("message", {}).get("content", [{}])[0].get("image", "")
            if not image_url:
                _update_prompt(processed_id, i, {"status": "failed", "error": "No image URL in response"})
                continue

            # Step 2: Download image from OSS URL
            img_resp = requests.get(image_url, timeout=60)
            if img_resp.status_code != 200:
                _update_prompt(processed_id, i, {"status": "failed", "error": f"Download {img_resp.status_code}"})
                continue

            # Step 3: Save to static/uploads/
            filename = f"{uuid.uuid4().hex}.png"
            filepath = os.path.join(UPLOAD_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(img_resp.content)

            local_url = f"/static/uploads/{filename}"
            _update_prompt(processed_id, i, {"status": "done", "url": local_url})

        except Exception as e:
            _update_prompt(processed_id, i, {"status": "failed", "error": str(e)[:200]})

    # Step 4: Write final image URLs to ProcessedContent.images in DB
    with _lock:
        final_prompts = _status_cache.get(processed_id, [])
    urls = [p.get("url") for p in final_prompts if p.get("status") == "done"]

    if urls:
        from models.content import SessionLocal, ProcessedContent
        db = SessionLocal()
        try:
            item = db.query(ProcessedContent).filter(ProcessedContent.id == processed_id).first()
            if item:
                item.set_images(urls)
                db.commit()
        finally:
            db.close()
