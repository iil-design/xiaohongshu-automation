# 小红书自动发帖助手 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal web app for scheduling and posting Xiaohongshu content — upload images + text, set publish time, Agent auto-posts at scheduled time.

**Architecture:** FastAPI monolith with Jinja2 server-side templates, Tailwind CSS CDN, SQLite database, APScheduler for timed jobs, LangChain Agent for content-review orchestration. Single process, no auth, flat 3-page structure.

**Tech Stack:** FastAPI, Jinja2, Tailwind CSS CDN, SQLite (via SQLAlchemy), APScheduler, LangChain + langchain-openai (qwen-coder-turbo-0919 via DashScope)

---

### Task 1: Install Dependencies

**Files:**
- Modify: `.venv/` (install packages)

- [ ] **Step 1: Install required packages**

```bash
"d:/桌面/agent/.venv/Scripts/pip.exe" install fastapi uvicorn[standard] apscheduler sqlalchemy python-multipart langchain-openai
```

Expected: All packages install successfully.

- [ ] **Step 2: Verify installations**

```bash
"d:/桌面/agent/.venv/Scripts/pip.exe" list | grep -E "fastapi|uvicorn|APScheduler|SQLAlchemy|python-multipart|langchain-openai"
```

Expected: See all 6 packages with versions.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "chore: install project dependencies"
```

---

### Task 2: Configuration Module

**Files:**
- Create: `config.py`

- [ ] **Step 1: Write config.py**

```python
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'data.db')}"

UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
MAX_IMAGES = 9
MAX_IMAGE_SIZE_MB = 10

LLM_CONFIG = {
    "provider": "openai_compatible",
    "model_name": "qwen-coder-turbo-0919",
    "api_key": "从环境变量 DASHSCOPE_API_KEY 读取",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "stream": False,
}
```

- [ ] **Step 2: Verify the file looks correct**

```bash
"d:/桌面/agent/.venv/Scripts/python.exe" -c "import config; print(config.DATABASE_URL); print(config.UPLOAD_DIR)"
```

Expected: Print database URL and upload directory without errors.

- [ ] **Step 3: Commit**

```bash
git add config.py && git commit -m "feat: add configuration module"
```

---

### Task 3: Database Models

**Files:**
- Create: `models/__init__.py`
- Create: `models/models.py`

- [ ] **Step 1: Write models/models.py**

```python
import json
import os
from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, default="")
    body = Column(Text, nullable=False, default="")
    images = Column(Text, nullable=False, default="[]")
    status = Column(String(20), nullable=False, default="draft")
    scheduled_at = Column(String(30), nullable=True)
    published_at = Column(String(30), nullable=True)
    error_msg = Column(Text, nullable=True)
    created_at = Column(String(30), nullable=False, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at = Column(String(30), nullable=False, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    schedules = relationship("Schedule", back_populates="post", cascade="all, delete-orphan")
    logs = relationship("PublishLog", back_populates="post", cascade="all, delete-orphan")

    def get_images(self):
        return json.loads(self.images)

    def set_images(self, paths):
        self.images = json.dumps(paths, ensure_ascii=False)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "images": self.get_images(),
            "status": self.status,
            "scheduled_at": self.scheduled_at,
            "published_at": self.published_at,
            "error_msg": self.error_msg,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    run_at = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    job_id = Column(String(100), nullable=True)

    post = relationship("Post", back_populates="schedules")


class PublishLog(Base):
    __tablename__ = "publish_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    action = Column(String(20), nullable=False)
    result = Column(String(20), nullable=False)
    message = Column(Text, nullable=True)
    created_at = Column(String(30), nullable=False, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    post = relationship("Post", back_populates="logs")


Base.metadata.create_all(bind=engine)
```

- [ ] **Step 2: Write models/__init__.py**

```python
from .models import engine, SessionLocal, Post, Schedule, PublishLog
```

- [ ] **Step 3: Verify models create tables**

```bash
"d:/桌面/agent/.venv/Scripts/python.exe" -c "from models import engine, Base; print('OK')"
```

- [ ] **Step 4: Verify data.db was created and has tables**

```bash
"d:/桌面/agent/.venv/Scripts/python.exe" -c "
from models import engine
from sqlalchemy import inspect
inspector = inspect(engine)
print(inspector.get_table_names())
"
```

Expected: `['posts', 'schedules', 'publish_logs']`

- [ ] **Step 5: Commit**

```bash
git add models/ data.db && git commit -m "feat: add database models"
```

---

### Task 4: Publisher Interface

**Files:**
- Create: `publisher/__init__.py`
- Create: `publisher/publisher.py`

- [ ] **Step 1: Write publisher/publisher.py**

```python
from dataclasses import dataclass
from models.models import Post


@dataclass
class PublishResult:
    success: bool
    message: str


class BasePublisher:
    def publish(self, post: Post) -> PublishResult:
        raise NotImplementedError


class MockPublisher(BasePublisher):
    def publish(self, post: Post) -> PublishResult:
        return PublishResult(success=True, message=f"模拟发布成功: {post.title}")
```

- [ ] **Step 2: Write publisher/__init__.py**

```python
from .publisher import BasePublisher, MockPublisher, PublishResult
```

- [ ] **Step 3: Verify publisher works**

```bash
"d:/桌面/agent/.venv/Scripts/python.exe" -c "
from publisher import MockPublisher
from models import SessionLocal, Post
import json

db = SessionLocal()
p = Post(title='test', body='test body', images=json.dumps([]))
db.add(p)
db.commit()

pub = MockPublisher()
result = pub.publish(p)
print(result.success, result.message)
db.close()
"
```

Expected: `True 模拟发布成功: test`

- [ ] **Step 4: Commit**

```bash
git add publisher/ && git commit -m "feat: add publisher interface with mock implementation"
```

---

### Task 5: Scheduler Module

**Files:**
- Create: `scheduler/__init__.py`
- Create: `scheduler/scheduler.py`

- [ ] **Step 1: Write scheduler/scheduler.py**

```python
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from models.models import SessionLocal, Schedule, Post
from publisher.publisher import MockPublisher

_scheduler = BackgroundScheduler()
_publisher = MockPublisher()


def _publish_post(post_id: int):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return
        result = _publisher.publish(post)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        post.status = "published" if result.success else "failed"
        post.published_at = now if result.success else None
        post.error_msg = result.message if not result.success else None
        post.updated_at = now

        # Update schedule status
        sched = db.query(Schedule).filter(
            Schedule.post_id == post_id,
            Schedule.status == "pending"
        ).first()
        if sched:
            sched.status = "done" if result.success else "failed"

        db.commit()
    finally:
        db.close()


def add_schedule(post_id: int, run_at_str: str):
    db = SessionLocal()
    try:
        run_at = datetime.strptime(run_at_str, "%Y-%m-%d %H:%M:%S")
        job = _scheduler.add_job(
            _publish_post,
            trigger=DateTrigger(run_date=run_at),
            args=[post_id],
            id=f"post_{post_id}_{run_at_str}",
            replace_existing=True,
        )
        schedule = Schedule(
            post_id=post_id,
            run_at=run_at_str,
            status="pending",
            job_id=job.id,
        )
        db.add(schedule)
        db.commit()
    finally:
        db.close()


def remove_schedule(post_id: int):
    db = SessionLocal()
    try:
        schedules = db.query(Schedule).filter(
            Schedule.post_id == post_id,
            Schedule.status == "pending"
        ).all()
        for s in schedules:
            if s.job_id:
                try:
                    _scheduler.remove_job(s.job_id)
                except Exception:
                    pass
            s.status = "cancelled"
        db.commit()
    finally:
        db.close()


def start_scheduler():
    _scheduler.start()


def shutdown_scheduler():
    _scheduler.shutdown(wait=False)
```

- [ ] **Step 2: Write scheduler/__init__.py**

```python
from .scheduler import add_schedule, remove_schedule, start_scheduler, shutdown_scheduler
```

- [ ] **Step 3: Verify scheduler starts and schedules a job**

```bash
"d:/桌面/agent/.venv/Scripts/python.exe" -c "
from scheduler import start_scheduler, add_schedule, shutdown_scheduler
from models import SessionLocal, Post
import json

db = SessionLocal()
p = Post(title='test', body='test', images=json.dumps([]))
db.add(p)
db.commit()
post_id = p.id
db.close()

start_scheduler()
add_schedule(post_id, '2099-01-01 00:00:00')
print('Schedule added OK')

shutdown_scheduler()
"
```

Expected: `Schedule added OK` (no errors)

- [ ] **Step 4: Commit**

```bash
git add scheduler/ && git commit -m "feat: add APScheduler module"
```

---

### Task 6: LangChain Agent

**Files:**
- Create: `agent/__init__.py`
- Create: `agent/poster_agent.py`

- [ ] **Step 1: Write agent/poster_agent.py**

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import LLM_CONFIG


def _build_llm():
    return ChatOpenAI(
        model=LLM_CONFIG["model_name"],
        api_key=LLM_CONFIG["api_key"],
        base_url=LLM_CONFIG["base_url"],
        temperature=0.3,
    )


def review_content(title: str, body: str) -> dict:
    llm = _build_llm()
    messages = [
        SystemMessage(content=(
            "你是小红书内容审核助手。检查帖子是否适合发布，返回 JSON："
            '{"ok": true/false, "reason": "简短说明"}。'
            "检查项：标题不为空，正文不为空，内容合理。"
        )),
        HumanMessage(content=f"标题：{title}\n正文：{body}"),
    ]
    response = llm.invoke(messages)
    import json
    try:
        return json.loads(response.content)
    except json.JSONDecodeError:
        return {"ok": True, "reason": "审核通过（JSON解析失败，默认放行）"}


def summarize_post(title: str, body: str) -> str:
    llm = _build_llm()
    messages = [
        SystemMessage(content="用一句话概括以下小红书帖子内容，不超过30字。"),
        HumanMessage(content=f"标题：{title}\n正文：{body}"),
    ]
    response = llm.invoke(messages)
    return response.content.strip()
```

- [ ] **Step 2: Write agent/__init__.py**

```python
from .poster_agent import review_content, summarize_post
```

- [ ] **Step 3: Verify agent works**

```bash
"d:/桌面/agent/.venv/Scripts/python.exe" -c "
from agent import review_content, summarize_post
result = review_content('夏日穿搭', '今天分享一套清爽的夏日穿搭')
print('Review:', result)
summary = summarize_post('夏日穿搭', '今天分享一套清爽的夏日穿搭')
print('Summary:', summary)
"
```

Expected: JSON review result and a one-sentence summary (API call succeeds).

- [ ] **Step 4: Commit**

```bash
git add agent/ && git commit -m "feat: add LangChain agent with content review"
```

---

### Task 7: FastAPI Routes

**Files:**
- Create: `web/__init__.py`
- Create: `web/routes.py`

- [ ] **Step 1: Write web/routes.py**

```python
import json
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse

from models.models import SessionLocal, Post, PublishLog
from scheduler.scheduler import add_schedule, remove_schedule
from agent.poster_agent import review_content
from config import UPLOAD_DIR, MAX_IMAGES, MAX_IMAGE_SIZE_MB

router = APIRouter()

os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/")
def index(request: Request):
    db = SessionLocal()
    try:
        posts = db.query(Post).order_by(Post.created_at.desc()).all()
        return request.app.state.templates.TemplateResponse("index.html", {
            "request": request,
            "posts": [p.to_dict() for p in posts],
        })
    finally:
        db.close()


@router.get("/editor")
def editor(request: Request, post_id: int = None):
    post = None
    if post_id:
        db = SessionLocal()
        try:
            post = db.query(Post).filter(Post.id == post_id).first()
        finally:
            db.close()
    return request.app.state.templates.TemplateResponse("editor.html", {
        "request": request,
        "post": post.to_dict() if post else None,
    })


@router.post("/posts/create")
async def create_post(
    request: Request,
    title: str = Form(default=""),
    body: str = Form(default=""),
    scheduled_at: str = Form(default=""),
    action: str = Form(default="draft"),
    images: list[UploadFile] = File(default=[]),
):
    # Limit images
    if len(images) > MAX_IMAGES:
        images = images[:MAX_IMAGES]

    # Save images
    image_paths = []
    for img in images:
        if img.filename:
            ext = os.path.splitext(img.filename)[1] or ".jpg"
            filename = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(UPLOAD_DIR, filename)
            content = await img.read()
            # Check size
            if len(content) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
                continue
            with open(filepath, "wb") as f:
                f.write(content)
            image_paths.append(f"/static/uploads/{filename}")

    db = SessionLocal()
    try:
        status = "draft"
        if action == "schedule" and scheduled_at:
            status = "scheduled"

        post = Post(
            title=title,
            body=body,
            scheduled_at=scheduled_at if scheduled_at else None,
            status=status,
        )
        post.set_images(image_paths)
        db.add(post)
        db.commit()
        db.refresh(post)
        post_id = post.id

        # If scheduled, register with scheduler and run agent review
        if status == "scheduled":
            review = review_content(title, body)
            if not review.get("ok", True):
                post.status = "failed"
                post.error_msg = f"内容审核不通过: {review.get('reason', '')}"
                db.commit()
            else:
                add_schedule(post_id, scheduled_at)

        db.close()
    except Exception as e:
        db.close()
        db2 = SessionLocal()
        try:
            post = db2.query(Post).filter(Post.id == post_id).first()
            if post:
                post.status = "failed"
                post.error_msg = str(e)
                db2.commit()
        finally:
            db2.close()

    return RedirectResponse(url="/", status_code=303)


@router.post("/posts/delete")
def delete_post(post_id: int = Form(...)):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post and post.status == "scheduled":
            remove_schedule(post_id)
        if post:
            # Delete image files
            for path in post.get_images():
                filepath = os.path.join(
                    os.path.dirname(UPLOAD_DIR),
                    path.lstrip("/static/"),
                )
                if os.path.exists(filepath):
                    os.remove(filepath)
            db.delete(post)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)


@router.post("/posts/schedule")
def schedule_post(post_id: int = Form(...), scheduled_at: str = Form(...)):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post and scheduled_at:
            review = review_content(post.title, post.body)
            if not review.get("ok", True):
                post.status = "failed"
                post.error_msg = f"内容审核不通过: {review.get('reason', '')}"
            else:
                post.status = "scheduled"
                post.scheduled_at = scheduled_at
                add_schedule(post_id, scheduled_at)
            post.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)


@router.post("/posts/retry")
def retry_post(post_id: int = Form(...)):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post and post.status == "failed":
            from publisher.publisher import MockPublisher
            pub = MockPublisher()
            result = pub.publish(post)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            post.status = "published" if result.success else "failed"
            post.published_at = now if result.success else None
            post.error_msg = result.message if not result.success else None
            post.updated_at = now

            log = PublishLog(
                post_id=post_id,
                action="retry",
                result="success" if result.success else "failed",
                message=result.message,
            )
            db.add(log)
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)


@router.post("/posts/publish_now")
def publish_now(post_id: int = Form(...)):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post:
            review = review_content(post.title, post.body)
            if not review.get("ok", True):
                post.status = "failed"
                post.error_msg = f"内容审核不通过: {review.get('reason', '')}"
                post.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db.commit()
            else:
                from publisher.publisher import MockPublisher
                pub = MockPublisher()
                result = pub.publish(post)
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                post.status = "published" if result.success else "failed"
                post.published_at = now if result.success else None
                post.error_msg = result.message if not result.success else None
                post.updated_at = now

                log = PublishLog(
                    post_id=post_id,
                    action="manual",
                    result="success" if result.success else "failed",
                    message=result.message,
                )
                db.add(log)
                db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)


@router.get("/history")
def history(request: Request):
    db = SessionLocal()
    try:
        logs = db.query(PublishLog).order_by(PublishLog.created_at.desc()).limit(100).all()
        log_list = []
        for log in logs:
            post = db.query(Post).filter(Post.id == log.post_id).first()
            log_list.append({
                "id": log.id,
                "post_title": post.title if post else "(已删除)",
                "action": log.action,
                "result": log.result,
                "message": log.message,
                "created_at": log.created_at,
            })
        return request.app.state.templates.TemplateResponse("history.html", {
            "request": request,
            "logs": log_list,
        })
    finally:
        db.close()
```

- [ ] **Step 2: Write web/__init__.py**

```python
from .routes import router
```

- [ ] **Step 3: Commit**

```bash
git add web/ && git commit -m "feat: add FastAPI routes"
```

---

### Task 8: Jinja2 Templates

**Files:**
- Create: `templates/base.html`
- Create: `templates/index.html`
- Create: `templates/editor.html`
- Create: `templates/history.html`

- [ ] **Step 1: Write templates/base.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>小红书发帖助手</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen">
  <nav class="bg-white shadow-sm border-b">
    <div class="max-w-4xl mx-auto px-4 py-3 flex items-center gap-6">
      <a href="/" class="text-lg font-bold text-red-500">📕 小红书发帖助手</a>
      <a href="/" class="text-sm text-gray-600 hover:text-gray-900">帖子管理</a>
      <a href="/editor" class="text-sm text-gray-600 hover:text-gray-900">新建帖子</a>
      <a href="/history" class="text-sm text-gray-600 hover:text-gray-900">发布历史</a>
    </div>
  </nav>
  <main class="max-w-4xl mx-auto px-4 py-8">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 2: Write templates/index.html**

```html
{% extends "base.html" %}
{% block content %}

<div class="flex items-center justify-between mb-6">
  <h1 class="text-2xl font-bold text-gray-800">帖子管理</h1>
  <a href="/editor" class="bg-red-500 text-white px-4 py-2 rounded-lg hover:bg-red-600 text-sm font-medium">
    + 新建帖子
  </a>
</div>

{% if posts %}
<ul class="space-y-3">
  {% for post in posts %}
  <li class="bg-white rounded-lg shadow-sm border p-4 flex items-start gap-4">
    <!-- Image preview -->
    <div class="w-20 h-20 rounded-md bg-gray-100 flex-shrink-0 overflow-hidden">
      {% if post.images and post.images|length > 0 %}
      <img src="{{ post.images[0] }}" class="w-full h-full object-cover" alt="">
      {% else %}
      <div class="w-full h-full flex items-center justify-center text-gray-300 text-2xl">📷</div>
      {% endif %}
    </div>

    <!-- Content -->
    <div class="flex-1 min-w-0">
      <h3 class="font-medium text-gray-800 truncate">{{ post.title or '(无标题)' }}</h3>
      <p class="text-sm text-gray-500 mt-1 truncate">{{ post.body or '(无正文)' }}</p>
      <div class="flex items-center gap-3 mt-2 text-xs">
        {% if post.status == 'draft' %}
        <span class="bg-gray-100 text-gray-600 px-2 py-0.5 rounded">草稿</span>
        {% elif post.status == 'scheduled' %}
        <span class="bg-blue-100 text-blue-700 px-2 py-0.5 rounded">⏳ {{ post.scheduled_at }}</span>
        {% elif post.status == 'published' %}
        <span class="bg-green-100 text-green-700 px-2 py-0.5 rounded">✅ {{ post.published_at }}</span>
        {% elif post.status == 'failed' %}
        <span class="bg-red-100 text-red-700 px-2 py-0.5 rounded">❌ 失败</span>
        {% endif %}

        {% if post.images %}
        <span class="text-gray-400">{{ post.images|length }} 张图</span>
        {% endif %}
      </div>
      {% if post.error_msg %}
      <p class="text-xs text-red-500 mt-1">{{ post.error_msg }}</p>
      {% endif %}
    </div>

    <!-- Actions -->
    <div class="flex items-center gap-2 flex-shrink-0">
      {% if post.status == 'draft' %}
      <form action="/editor" method="get" class="inline">
        <input type="hidden" name="post_id" value="{{ post.id }}">
        <button class="text-sm text-gray-500 hover:text-gray-700 px-2 py-1">编辑</button>
      </form>
      <form action="/posts/publish_now" method="post" class="inline" onsubmit="return confirm('立即发布这篇帖子？')">
        <input type="hidden" name="post_id" value="{{ post.id }}">
        <button class="text-sm text-red-500 hover:text-red-700 px-2 py-1">▶ 发布</button>
      </form>
      {% elif post.status == 'failed' %}
      <form action="/posts/retry" method="post" class="inline" onsubmit="return confirm('重试发布？')">
        <input type="hidden" name="post_id" value="{{ post.id }}">
        <button class="text-sm text-orange-500 hover:text-orange-700 px-2 py-1">↻ 重试</button>
      </form>
      {% endif %}
      <form action="/posts/delete" method="post" class="inline" onsubmit="return confirm('确定删除？')">
        <input type="hidden" name="post_id" value="{{ post.id }}">
        <button class="text-sm text-gray-400 hover:text-red-500 px-2 py-1">删除</button>
      </form>
    </div>
  </li>
  {% endfor %}
</ul>
{% else %}
<div class="text-center py-20 text-gray-400">
  <p class="text-4xl mb-4">📭</p>
  <p>还没有帖子，点击上方按钮创建第一个</p>
</div>
{% endif %}

{% endblock %}
```

- [ ] **Step 3: Write templates/editor.html**

```html
{% extends "base.html" %}
{% block content %}

<h1 class="text-2xl font-bold text-gray-800 mb-6">
  {% if post %}编辑帖子{% else %}新建帖子{% endif %}
</h1>

<form action="/posts/create" method="post" enctype="multipart/form-data" class="space-y-6">
  <!-- Hidden fields for edit mode -->
  {% if post %}
  <input type="hidden" name="post_id" value="{{ post.id }}">
  {% endif %}

  <!-- Image upload -->
  <div class="bg-white rounded-lg shadow-sm border p-4">
    <label class="block text-sm font-medium text-gray-700 mb-2">上传图片（最多9张）</label>
    <input type="file" name="images" multiple accept="image/*" class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:bg-red-50 file:text-red-600 hover:file:bg-red-100">

    {% if post and post.images %}
    <div class="flex gap-2 mt-3 flex-wrap">
      {% for img in post.images %}
      <img src="{{ img }}" class="w-16 h-16 object-cover rounded-md border" alt="">
      {% endfor %}
    </div>
    {% endif %}
  </div>

  <!-- Title -->
  <div class="bg-white rounded-lg shadow-sm border p-4">
    <label class="block text-sm font-medium text-gray-700 mb-2">标题</label>
    <input type="text" name="title" value="{{ post.title if post else '' }}" maxlength="200"
           class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 focus:border-red-400 outline-none"
           placeholder="输入帖子标题...">
  </div>

  <!-- Body -->
  <div class="bg-white rounded-lg shadow-sm border p-4">
    <label class="block text-sm font-medium text-gray-700 mb-2">正文</label>
    <textarea name="body" rows="5" maxlength="2000"
              class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 focus:border-red-400 outline-none"
              placeholder="输入帖子正文...">{{ post.body if post else '' }}</textarea>
  </div>

  <!-- Schedule time -->
  <div class="bg-white rounded-lg shadow-sm border p-4">
    <label class="block text-sm font-medium text-gray-700 mb-2">⏰ 发布时间（可选）</label>
    <input type="datetime-local" name="scheduled_at"
           value="{{ post.scheduled_at if post and post.scheduled_at else '' }}"
           class="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 focus:border-red-400 outline-none">
  </div>

  <!-- Buttons -->
  <div class="flex gap-3">
    <button type="submit" name="action" value="draft"
            class="px-6 py-2.5 text-sm font-medium rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50">
      保存草稿
    </button>
    <button type="submit" name="action" value="schedule"
            class="px-6 py-2.5 text-sm font-medium rounded-lg bg-red-500 text-white hover:bg-red-600">
      定时发布
    </button>
  </div>
</form>

{% endblock %}
```

- [ ] **Step 4: Write templates/history.html**

```html
{% extends "base.html" %}
{% block content %}

<h1 class="text-2xl font-bold text-gray-800 mb-6">发布历史</h1>

{% if logs %}
<div class="bg-white rounded-lg shadow-sm border overflow-hidden">
  <table class="w-full text-sm">
    <thead>
      <tr class="bg-gray-50 text-left text-gray-600">
        <th class="px-4 py-3 font-medium">帖子</th>
        <th class="px-4 py-3 font-medium">操作</th>
        <th class="px-4 py-3 font-medium">结果</th>
        <th class="px-4 py-3 font-medium">时间</th>
        <th class="px-4 py-3 font-medium">详情</th>
      </tr>
    </thead>
    <tbody class="divide-y">
      {% for log in logs %}
      <tr>
        <td class="px-4 py-3 text-gray-800">{{ log.post_title }}</td>
        <td class="px-4 py-3">
          {% if log.action == 'scheduled' %}
          <span class="text-blue-600">定时发布</span>
          {% elif log.action == 'manual' %}
          <span class="text-green-600">手动发布</span>
          {% else %}
          <span class="text-orange-600">重试</span>
          {% endif %}
        </td>
        <td class="px-4 py-3">
          {% if log.result == 'success' %}
          <span class="text-green-600">✅ 成功</span>
          {% else %}
          <span class="text-red-500">❌ 失败</span>
          {% endif %}
        </td>
        <td class="px-4 py-3 text-gray-500">{{ log.created_at }}</td>
        <td class="px-4 py-3 text-gray-500 text-xs">{{ log.message or '-' }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% else %}
<div class="text-center py-20 text-gray-400">
  <p class="text-4xl mb-4">📋</p>
  <p>暂无发布记录</p>
</div>
{% endif %}

{% endblock %}
```

- [ ] **Step 5: Commit**

```bash
git add templates/ && git commit -m "feat: add Jinja2 templates with Tailwind CSS"
```

---

### Task 9: Application Entry Point

**Files:**
- Create: `main.py`

- [ ] **Step 1: Write main.py**

```python
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.routes import router
from scheduler.scheduler import start_scheduler, shutdown_scheduler
from config import UPLOAD_DIR

os.makedirs(UPLOAD_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="小红书发帖助手", lifespan=lifespan)

templates = Jinja2Templates(directory="templates")
app.state.templates = templates

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
```

- [ ] **Step 2: Start the server to verify it runs**

```bash
"d:/桌面/agent/.venv/Scripts/python.exe" -c "
import uvicorn, sys, os, time, threading

os.chdir('d:/桌面/agent')
sys.path.insert(0, 'd:/桌面/agent')

def start():
    uvicorn.run('main:app', host='127.0.0.1', port=8000)

t = threading.Thread(target=start, daemon=True)
t.start()
time.sleep(2)
print('Server started OK')
"
```

Expected: `Server started OK`

- [ ] **Step 3: Test that the index page returns 200**

```bash
"d:/桌面/agent/.venv/Scripts/python.exe" -c "
import urllib.request, time
time.sleep(1)
resp = urllib.request.urlopen('http://127.0.0.1:8000/')
print(resp.status)
"
```

Expected: `200`

- [ ] **Step 4: Commit**

```bash
git add main.py && git commit -m "feat: add FastAPI entry point"
```

---

### Task 10: Integration Smoke Test

**Files:**
- Create: `test_smoke.py`

- [ ] **Step 1: Write test_smoke.py**

```python
import os
import sys
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"

def test_index():
    resp = urllib.request.urlopen(f"{BASE}/")
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    body = resp.read().decode("utf-8")
    assert "帖子管理" in body
    assert "新建帖子" in body

def test_editor():
    resp = urllib.request.urlopen(f"{BASE}/editor")
    assert resp.status == 200

def test_history():
    resp = urllib.request.urlopen(f"{BASE}/history")
    assert resp.status == 200

def test_create_draft():
    import urllib.parse
    data = urllib.parse.urlencode({
        "title": "测试帖子",
        "body": "这是一条测试内容",
        "action": "draft",
    }).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/posts/create", data=data, method="POST")
    resp = urllib.request.urlopen(req)
    assert resp.status == 200

    resp2 = urllib.request.urlopen(f"{BASE}/")
    body = resp2.read().decode("utf-8")
    assert "测试帖子" in body

if __name__ == "__main__":
    test_index()
    print("PASS: test_index")
    test_editor()
    print("PASS: test_editor")
    test_history()
    print("PASS: test_history")
    test_create_draft()
    print("PASS: test_create_draft")
    print("ALL TESTS PASSED")
```

- [ ] **Step 2: Run smoke tests**

```bash
"d:/桌面/agent/.venv/Scripts/python.exe" test_smoke.py
```

Expected: All 4 tests print `PASS` and final `ALL TESTS PASSED`.

- [ ] **Step 3: Commit**

```bash
git add test_smoke.py && git commit -m "test: add integration smoke tests"
```

---

### Task 11: Static Files Setup

**Files:**
- Create: `static/uploads/.gitkeep`

- [ ] **Step 1: Create uploads directory**

```bash
mkdir -p "d:/桌面/agent/static/uploads" && touch "d:/桌面/agent/static/uploads/.gitkeep"
```

- [ ] **Step 2: Commit**

```bash
git add static/ && git commit -m "chore: add static uploads directory"
```
