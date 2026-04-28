# 文生图集成：AI 加工后自动生成图片

## 背景

Content agent 已在 `image_prompts` 中返回 3 条文生图提示词，但未实际生成图片。需要在 AI 加工完成后，自动调用 DashScope wan2.6-t2i 将提示词转化为图片，并传递到草稿。

## 数据流

```
POST /api/ai/process
  ├─ content_agent 生成 {title, body, tags, image_prompts}
  ├─ 写入 ProcessedContent（image_prompts 有值，images 为空）
  ├─ 返回前端 {success, processed_id, result}
  └─ spawn 后台线程 → generate_images(processed_id, image_prompts)
                          ├─ prompt[0] → DashScope → 下载 OSS URL → static/uploads/<uuid>.png → 更新 DB
                          ├─ prompt[1] → ...
                          └─ prompt[2] → ...

GET /api/ai/image-status?processed_id=X → {prompts: [{index, status, prompt, url?}]}

POST /library/import → Post 带生成好的图片
```

## 数据库变更

`models/content.py` — `ProcessedContent` 新增字段：

- `images` (Text, default="[]") — JSON 数组存储本地图片路径

## 新增模块: `agent/image_generator.py`

### `generate_images(processed_id: int, image_prompts: list[str]) -> None`

后台线程入口。

逻辑：
1. 遍历 image_prompts，对每个 index 写入 status="generating"（内存字典）
2. 调用 DashScope wan2.6-t2i API
3. 从响应 `output.choices[0].message.content[0]["image"]` 取临时 OSS URL
4. `requests.get(url)` 下载图片，保存到 `static/uploads/<uuid>.png`
5. 更新 `ProcessedContent.images` JSON 数组（append 新路径），写入 DB
6. 单个 prompt 失败不影响其余

状态通过模块级字典 `_status_cache: dict[int, list[dict]]` 追踪，key 为 processed_id。

### DashScope 调用格式

```
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
  model: "wan2.6-t2i"
  input.messages[0].content[0].text: <prompt>
  parameters: {n: 1, size: "1280*1280", watermark: false, prompt_extend: true}
```

## API 变更

### 修改 `POST /api/ai/process`

在返回响应前，新增一行启动后台线程：

```python
threading.Thread(target=generate_images, args=(processed.id, result["image_prompts"]), daemon=True).start()
```

### 新增 `GET /api/ai/image-status`

参数：`processed_id` (int)

返回：
```json
{
  "processed_id": 1,
  "prompts": [
    {"index": 0, "prompt": "...", "status": "done", "url": "/static/uploads/xxx.png"},
    {"index": 1, "prompt": "...", "status": "generating"},
    {"index": 2, "prompt": "...", "status": "failed", "error": "..."}
  ]
}
```

status 枚举：`pending` → `generating` → `done` / `failed`

### 修改 `POST /library/import`

图片优先级：`ProcessedContent.get_images()` 非空则用，否则 fallback 到 `Content.get_images()`。

## 前端变更

`templates/library.html` — 素材库列表：

- AI 加工完成后，图片区域显示轮询状态
- polling（3s 间隔）：请求 `/api/ai/image-status`
- UI 状态：
  - `pending/generating`: 骨架屏或转圈动画
  - `done`: 显示缩略图
  - `failed`: 红色感叹号
- 全部 done 或全部 resolved 后停止轮询

## 错误处理

- 单个 prompt 生图失败 → 标记 failed，继续处理下一个
- DashScope API 不可达 → 所有 prompt 标记 failed
- 临时 URL 下载失败 → 该 prompt 标记 failed
- 所有失败不影响 AI 加工结果（标题、正文仍可用）
