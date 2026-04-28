# 文生图集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI 加工完成后自动调用 DashScope wan2.6-t2i 将 3 条 image_prompts 转为图片，存入 ProcessedContent，前端轮询展示生图进度。

**Architecture:** 在 `agent/image_generator.py` 中新增后台生图模块，通过模块级 `_status_cache` 字典追踪每个 processed_id 的生图状态。`/api/ai/process` 返回后 spawn daemon 线程执行生图，新增 `/api/ai/image-status` 供前端 3s 轮询。`/library/import` 优先使用生成图片。

**Tech Stack:** Python requests, DashScope API, threading, FastAPI, Jinja2

---

### Task 1: Add `images` field to ProcessedContent model

**Files:**
- Modify: `models/content.py:52-86`

- [ ] **Step 1: Add `images` column and getter/setter to ProcessedContent**

```python
# models/content.py — in ProcessedContent class, add after image_prompts line:

    images = Column(Text, nullable=False, default="[]")

    def get_images(self):
        return json.loads(self.images) if self.images else []

    def set_images(self, urls):
        self.images = json.dumps(urls or [], ensure_ascii=False)
```

Also add `images` to `to_dict()`:

```python
    def to_dict(self):
        return {
            "id": self.id,
            "original_content_id": self.original_content_id,
            "title": self.title,
            "body": self.body,
            "tags": self.get_tags(),
            "image_prompts": self.get_image_prompts(),
            "images": self.get_images(),
            "created_at": self.created_at,
        }
```

The full ProcessedContent class after editing should read:

```python
class ProcessedContent(Base):
    __tablename__ = "processed_contents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_content_id = Column(Integer, nullable=False, index=True)
    title = Column(String(200), nullable=False, default="")
    body = Column(Text, nullable=False, default="")
    tags = Column(Text, nullable=False, default="[]")
    image_prompts = Column(Text, nullable=False, default="[]")
    images = Column(Text, nullable=False, default="[]")
    created_at = Column(String(30), nullable=False, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def get_tags(self):
        return json.loads(self.tags) if self.tags else []

    def set_tags(self, tags_list):
        self.tags = json.dumps(tags_list or [], ensure_ascii=False)

    def get_image_prompts(self):
        return json.loads(self.image_prompts) if self.image_prompts else []

    def set_image_prompts(self, prompts_list):
        self.image_prompts = json.dumps(prompts_list or [], ensure_ascii=False)

    def get_images(self):
        return json.loads(self.images) if self.images else []

    def set_images(self, urls):
        self.images = json.dumps(urls or [], ensure_ascii=False)

    def to_dict(self):
        return {
            "id": self.id,
            "original_content_id": self.original_content_id,
            "title": self.title,
            "body": self.body,
            "tags": self.get_tags(),
            "image_prompts": self.get_image_prompts(),
            "images": self.get_images(),
            "created_at": self.created_at,
        }
```

- [ ] **Step 2: Verify DB migration works**

Run: `python -c "from models.content import Base, engine; Base.metadata.create_all(bind=engine); print('OK')"`
Expected: `OK` (no error)

- [ ] **Step 3: Commit**

```bash
git add models/content.py
git commit -m "feat: add images field to ProcessedContent model"
```

---

### Task 2: Add `DASHSCOPE_API_KEY` to config and create `agent/image_generator.py`

**Files:**
- Modify: `config.py:14-15`
- Create: `agent/image_generator.py`

- [ ] **Step 1: Add DASHSCOPE_API_KEY to config.py**

In `config.py`, add after `MAX_IMAGE_SIZE_MB = 10` line:

```python
DASHSCOPE_API_KEY = "sk-2779612cd26547fab22f55d641926d9f"
```

- [ ] **Step 2: Write the image_generator module with `generate_images` and `get_status`**

```python
import json
import os
import uuid
import threading
import requests

from config import DASHSCOPE_API_KEY, UPLOAD_DIR

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

    # Initialize status cache
    with _lock:
        _status_cache[processed_id] = [
            {"index": i, "prompt": p, "status": "pending"}
            for i, p in enumerate(image_prompts)
        ]

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
    }

    for i, prompt in enumerate(image_prompts):
        _update_prompt(processed_id, i, {"status": "generating"})

        try:
            # Step 1: Call DashScope to generate image
            payload = {
                "model": "wan2.6-t2i",
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
                    "size": "1280*1280",
                    "watermark": False,
                    "prompt_extend": True,
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
```

- [ ] **Step 3: Run a quick unit test**

```bash
cd "d:/桌面/agent" && python -c "
from agent.image_generator import generate_images, get_status
import time

# Start generation
import threading
t = threading.Thread(target=generate_images, args=(999, ['一只可爱的橘猫坐在窗台上看夕阳，日系温馨风格，暖黄调']), daemon=True)
t.start()

# Poll
for _ in range(30):
    s = get_status(999)
    if s:
        for p in s['prompts']:
            print(f\"  [{p['index']}] {p['status']}\")
        if all(p['status'] in ('done', 'failed') for p in s['prompts']):
            break
    time.sleep(3)
print('Done')
"
```

Expected: Status transitions from `pending` → `generating` → `done`, and image file appears in `static/uploads/`.

- [ ] **Step 4: Commit**

```bash
git add config.py agent/image_generator.py
git commit -m "feat: add image generator module with DashScope wan2.6-t2i"
```

---

### Task 3: Modify `POST /api/ai/process` to spawn background image generation

**Files:**
- Modify: `web/routes.py:423-472`

- [ ] **Step 1: Add import at top of routes.py**

At the top of `web/routes.py`, add the import:

```python
from agent.image_generator import generate_images
```

- [ ] **Step 2: Add background thread spawn in ai_process**

In `web/routes.py`, inside `ai_process()`, right before `return JSONResponse({...})` (after `db.refresh(processed)` at line 455), add:

```python
        image_prompts = result.get("image_prompts", [])
        if image_prompts:
            threading.Thread(
                target=generate_images,
                args=(processed.id, image_prompts),
                daemon=True,
            ).start()
```

The full return block should now read:

```python
        db.add(processed)
        db.commit()
        db.refresh(processed)

        image_prompts = result.get("image_prompts", [])
        if image_prompts:
            threading.Thread(
                target=generate_images,
                args=(processed.id, image_prompts),
                daemon=True,
            ).start()

        return JSONResponse({
            "success": True,
            "source": {"id": item.id, "title": item.title},
            "processed_id": processed.id,
            "result": {
                "title": result.get("title", ""),
                "body": result.get("body", ""),
                "tags": result.get("tags", []),
                "image_prompts": result.get("image_prompts", []),
            },
            "raw": None,
        })
```

- [ ] **Step 3: Verify the route starts correctly**

```bash
cd "d:/桌面/agent" && python -c "from web.routes import router; print('Import OK')"
```

- [ ] **Step 4: Commit**

```bash
git add web/routes.py
git commit -m "feat: spawn background image generation in AI process endpoint"
```

---

### Task 4: Add `GET /api/ai/image-status` endpoint

**Files:**
- Modify: `web/routes.py` (append after existing AI routes, before router close)

- [ ] **Step 1: Import get_status at top of routes.py**

Add `get_status` to the existing image_generator import:

```python
from agent.image_generator import generate_images, get_status
```

- [ ] **Step 2: Add the endpoint after `/api/ai/save-system-prompt`**

```python
@router.get("/api/ai/image-status")
def image_generation_status(processed_id: int = 0):
    """查询指定 processed_id 的图片生成进度"""
    if not processed_id:
        return JSONResponse({"error": "missing processed_id"}, status_code=400)
    data = get_status(processed_id)
    if data is None:
        # Check if the processed_id even exists
        from models.content import SessionLocal as ContentSessionLocal, ProcessedContent
        db = ContentSessionLocal()
        try:
            exists = db.query(ProcessedContent).filter(ProcessedContent.id == processed_id).first()
        finally:
            db.close()
        if not exists:
            return JSONResponse({"error": "processed_id not found"}, status_code=404)
        # Exists but no status yet (edge case: thread hasn't started)
        return JSONResponse({"processed_id": processed_id, "prompts": []})
    return JSONResponse(data)
```

- [ ] **Step 3: Test the endpoint manually**

Start server, then:

```bash
# First trigger an AI process to get a processed_id
# Then poll:
curl "http://127.0.0.1:8890/api/ai/image-status?processed_id=1"
```

Expected JSON with `prompts` array.

- [ ] **Step 4: Commit**

```bash
git add web/routes.py
git commit -m "feat: add GET /api/ai/image-status endpoint for polling"
```

---

### Task 5: Modify `POST /library/import` to use generated images

**Files:**
- Modify: `web/routes.py:359-408`

- [ ] **Step 1: Update image logic in library_import**

In `library_import()`, change line 378 from:

```python
                post.set_images(item.get_images())
```

To:

```python
                post.set_images(processed.get_images())
```

The full block (lines 369-387) should now read:

```python
        if processed_id:
            from models.content import ProcessedContent
            processed = content_db.query(ProcessedContent).filter(ProcessedContent.id == processed_id).first()
            if processed:
                post = Post(
                    title=processed.title,
                    body=processed.body,
                    status="draft",
                )
                post.set_images(processed.get_images())
                post.set_tags(processed.get_tags())
            else:
                post = Post(
                    title=item.title,
                    body=item.body,
                    status="draft",
                )
                post.set_images(item.get_images())
                post.set_tags(item.get_tags())
        else:
            post = Post(
                title=item.title,
                body=item.body,
                status="draft",
            )
            post.set_images(item.get_images())
            post.set_tags(item.get_tags())
```

- [ ] **Step 2: Verify import works**

```bash
cd "d:/桌面/agent" && python -c "from web.routes import router; print('Import OK')"
```

- [ ] **Step 3: Commit**

```bash
git add web/routes.py
git commit -m "feat: use generated images from ProcessedContent when importing to draft"
```

---

### Task 6: Update `templates/library.html` with image generation polling

**Files:**
- Modify: `templates/library.html:105-109` (image prompts display area)
- Modify: `templates/library.html:269-283` (runAI JS function)

- [ ] **Step 1: Replace the static image_prompts display with status-aware cards**

In library.html, replace lines 106-109:

```html
          <!-- 文生图提示词 -->
          <div class="mb-4">
            <label class="text-xs text-gray-400 font-medium">🎨 文生图提示词</label>
            <div class="space-y-2 mt-1" id="out-image-prompts"></div>
          </div>
```

With:

```html
          <!-- 文生图提示词 + 生成状态 -->
          <div class="mb-4">
            <label class="text-xs text-gray-400 font-medium">🎨 文生图提示词 & 生成状态</label>
            <div class="space-y-2 mt-1" id="out-image-prompts"></div>
          </div>
```

- [ ] **Step 2: Update the runAI JS to build status-aware cards and start polling**

Replace the image prompts rendering section in `runAI()` (lines 269-277), and add a polling function.

In the `runAI()` function, replace:

```javascript
    // 文生图提示词
    const promptsDiv = document.getElementById('out-image-prompts');
    promptsDiv.innerHTML = '';
    (result.image_prompts || []).forEach((p, i) => {
      const div = document.createElement('div');
      div.className = 'bg-purple-50 rounded p-3 text-sm text-purple-800 flex items-start gap-2';
      div.innerHTML = '<span class="text-purple-400 font-bold shrink-0">' + (i+1) + '.</span><span>' + p + '</span>';
      promptsDiv.appendChild(div);
    });
```

With:

```javascript
    // 文生图提示词 + 生成状态
    const promptsDiv = document.getElementById('out-image-prompts');
    promptsDiv.innerHTML = '';
    (result.image_prompts || []).forEach((p, i) => {
      const div = document.createElement('div');
      div.className = 'bg-purple-50 rounded p-3';
      div.id = 'img-prompt-' + i;
      div.innerHTML =
        '<div class="flex items-start gap-2">' +
        '<span class="text-purple-400 font-bold shrink-0">' + (i+1) + '.</span>' +
        '<div class="flex-1 min-w-0">' +
        '<p class="text-sm text-purple-800">' + p + '</p>' +
        '<div class="mt-2 flex items-center gap-2" id="img-status-' + i + '">' +
        '<span class="inline-block w-4 h-4 border-2 border-purple-300 border-t-purple-500 rounded-full animate-spin"></span>' +
        '<span class="text-xs text-purple-500">等待生成...</span>' +
        '</div>' +
        '</div>' +
        '</div>';
      promptsDiv.appendChild(div);
    });

    // Start polling image status if we have a processed_id
    if (processedId && (result.image_prompts || []).length > 0) {
      startImagePolling(processedId);
    }
```

- [ ] **Step 3: Add the `startImagePolling` function**

Add this new function before `</script>` closing tag (after the `importResult` function):

```javascript
let imagePollTimer = null;

function startImagePolling(pid) {
  if (imagePollTimer) clearInterval(imagePollTimer);

  imagePollTimer = setInterval(async () => {
    try {
      const resp = await fetch('/api/ai/image-status?processed_id=' + pid);
      const data = await resp.json();
      if (!data.prompts) return;

      let allDone = true;

      data.prompts.forEach(p => {
        const statusEl = document.getElementById('img-status-' + p.index);
        if (!statusEl) return;

        if (p.status === 'done') {
          statusEl.innerHTML =
            '<img src="' + p.url + '" class="w-32 h-32 object-cover rounded border" alt="">';
        } else if (p.status === 'failed') {
          statusEl.innerHTML =
            '<span class="text-xs text-red-500">❌ ' + (p.error || '生成失败') + '</span>';
          allDone = false;
        } else {
          statusEl.innerHTML =
            '<span class="inline-block w-4 h-4 border-2 border-purple-300 border-t-purple-500 rounded-full animate-spin"></span>' +
            '<span class="text-xs text-purple-500">' + (p.status === 'generating' ? '生成中...' : '等待中...') + '</span>';
          allDone = false;
        }
      });

      if (allDone) {
        clearInterval(imagePollTimer);
        imagePollTimer = null;
      }
    } catch (e) {
      // Silently retry on next interval
    }
  }, 3000);
}
```

- [ ] **Step 4: Commit**

```bash
git add templates/library.html
git commit -m "feat: add image generation polling UI in library page"
```

---

### Task 7: Integration smoke test

- [ ] **Step 1: Start the server**

```bash
cd "d:/桌面/agent" && python main.py &
sleep 3
```

- [ ] **Step 2: Verify the status endpoint without a processed_id**

```bash
curl -s "http://127.0.0.1:8890/api/ai/image-status?processed_id=0" | python -m json.tool
```

Expected: `{"error": "missing processed_id"}`

- [ ] **Step 3: Verify the status endpoint with non-existent ID**

```bash
curl -s "http://127.0.0.1:8890/api/ai/image-status?processed_id=999999" | python -m json.tool
```

Expected: `{"error": "processed_id not found"}`

- [ ] **Step 4: Verify templates render without errors**

```bash
curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8890/library"
```

Expected: `200`

- [ ] **Step 5: Stop server**

```bash
pkill -f "python main.py" 2>/dev/null; echo "stopped"
```

- [ ] **Step 6: Commit any fixes if needed, or mark done**

```bash
# If tests pass, no additional commit needed
```

