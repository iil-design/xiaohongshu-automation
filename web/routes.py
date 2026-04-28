import os
import uuid
import sys
import threading
from datetime import datetime

from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse

from fastapi.responses import JSONResponse
from models.models import SessionLocal, Post, PublishLog
from models.content import SessionLocal as ContentSessionLocal, Content
from scheduler.scheduler import add_schedule, remove_schedule
from agent.poster_agent import review_content
from agent.image_generator import generate_images
from publisher.publisher import get_publisher
from config import UPLOAD_DIR, MAX_IMAGES, MAX_IMAGE_SIZE_MB

router = APIRouter()

os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/")
def index(request: Request):
    db = SessionLocal()
    try:
        posts = db.query(Post).order_by(Post.created_at.desc()).all()
        return request.app.state.templates.TemplateResponse(request, "index.html", {
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
    return request.app.state.templates.TemplateResponse(request, "editor.html", {
        "post": post.to_dict() if post else None,
    })


@router.post("/posts/create")
async def create_post(
    request: Request,
    title: str = Form(default=""),
    body: str = Form(default=""),
    tags: str = Form(default=""),
    scheduled_at: str = Form(default=""),
    action: str = Form(default="draft"),
    images: list[UploadFile] = File(default=[]),
):
    # Convert datetime-local format (YYYY-MM-DDTHH:MM) to expected
    if scheduled_at and "T" in scheduled_at:
        scheduled_at = scheduled_at.replace("T", " ") + ":00"

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
            if len(content) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
                continue
            with open(filepath, "wb") as f:
                f.write(content)
            image_paths.append(f"/static/uploads/{filename}")

    db = SessionLocal()
    post_id = None
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
        # 解析标签：逗号分隔
        tag_list = [t.strip() for t in tags.replace("，", ",").split(",") if t.strip()]
        post.set_tags(tag_list)
        db.add(post)
        db.commit()
        db.refresh(post)
        post_id = post.id

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
        if post_id:
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
        if post:
            if post.status == "scheduled":
                remove_schedule(post_id)
            for path in post.get_images():
                filepath = os.path.join(
                    os.path.dirname(UPLOAD_DIR),
                    path.lstrip("/").replace("static/", "", 1),
                )
                full_path = os.path.join(os.path.dirname(UPLOAD_DIR), filepath)
                if os.path.exists(full_path):
                    os.remove(full_path)
            db.delete(post)
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
                from publisher.publisher import get_publisher
                pub = get_publisher()
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


@router.post("/posts/retry")
def retry_post(post_id: int = Form(...)):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post and post.status == "failed":
            from publisher.publisher import get_publisher
            pub = get_publisher()
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
        return request.app.state.templates.TemplateResponse(request, "history.html", {
            "logs": log_list,
        })
    finally:
        db.close()


@router.get("/api/login-status")
def get_login_status():
    try:
        pub = get_publisher()
        is_logged_in = pub._get_client().check_login()
        return JSONResponse({
            "logged_in": is_logged_in,
            "message": "已登录" if is_logged_in else "未登录",
        })
    except Exception as e:
        return JSONResponse({
            "logged_in": False,
            "message": f"检查登录状态失败: {str(e)}",
        })


@router.post("/api/delete-cookies")
def delete_cookies_endpoint():
    try:
        pub = get_publisher()
        result = pub._get_client().delete_cookies()
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": f"调用失败: {str(e)}"
        })


@router.post("/api/login")
def login_endpoint():
    """获取登录二维码（MCP扫码登录）"""
    try:
        pub = get_publisher()
        result = pub._get_client().login()
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": f"获取二维码失败: {str(e)}"
        })


@router.post("/api/scrapers/github-trending")
def run_github_trending_scraper():
    """执行 GitHub Trending 爬虫脚本"""
    import subprocess

    def run_scraper():
        try:
            script_path = os.path.join(os.path.dirname(__file__), "..", "内容脚本", "github_trending_rpa.py")
            print(f"[GitHub Trending] 执行脚本: {script_path}")
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                encoding="utf-8", errors="replace",
                timeout=600,
                cwd=os.path.dirname(os.path.dirname(__file__))
            )
            print(f"[GitHub Trending] 返回码: {result.returncode}")
            print(f"[GitHub Trending] stdout:\n{result.stdout}")
            if result.stderr:
                print(f"[GitHub Trending] stderr:\n{result.stderr}")
        except Exception as e:
            print(f"[Error] GitHub Trending 爬虫执行失败: {e}")

    # 后台线程执行，避免阻塞 HTTP 响应
    thread = threading.Thread(target=run_scraper, daemon=True)
    thread.start()

    return JSONResponse({
        "success": True,
        "message": "GitHub Trending 爬虫已启动，后台运行中..."
    })


@router.post("/api/scrapers/douchacha")
def run_douchacha_scraper():
    """执行抖查查爬虫脚本"""
    import subprocess

    def run_scraper():
        try:
            script_path = os.path.join(os.path.dirname(__file__), "..", "内容脚本", "scrape_douchacha.py")
            print(f"[Douchacha] 执行脚本: {script_path}")
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                encoding="utf-8", errors="replace",
                timeout=300,
                cwd=os.path.dirname(os.path.dirname(__file__))
            )
            print(f"[Douchacha] 返回码: {result.returncode}")
            print(f"[Douchacha] stdout:\n{result.stdout}")
            if result.stderr:
                print(f"[Douchacha] stderr:\n{result.stderr}")
        except Exception as e:
            print(f"[Error] Douchacha 爬虫执行失败: {e}")

    # 后台线程执行
    thread = threading.Thread(target=run_scraper, daemon=True)
    thread.start()

    return JSONResponse({
        "success": True,
        "message": "抖查查爬虫已启动，后台运行中..."
    })


@router.get("/library")
def library(request: Request):
    db = ContentSessionLocal()
    try:
        items = db.query(Content).order_by(Content.created_at.desc()).all()
        return request.app.state.templates.TemplateResponse(request, "library.html", {
            "items": [item.to_dict() for item in items],
        })
    finally:
        db.close()


@router.post("/library/import")
def library_import(request: Request, content_id: int = Form(...), processed_id: int = Form(default=0)):
    content_db = ContentSessionLocal()
    post_db = SessionLocal()
    try:
        item = content_db.query(Content).filter(Content.id == content_id).first()
        if not item:
            return RedirectResponse(url="/library", status_code=303)

        # 如果有 AI 加工结果，使用加工后的内容
        if processed_id:
            from models.content import ProcessedContent
            processed = content_db.query(ProcessedContent).filter(ProcessedContent.id == processed_id).first()
            if processed:
                post = Post(
                    title=processed.title,
                    body=processed.body,
                    status="draft",
                )
                post.set_images(item.get_images())
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

        post_db.add(post)
        post_db.commit()
        post_db.refresh(post)

        item.imported = True
        item.imported_to = post.id
        content_db.commit()

        return RedirectResponse(url=f"/editor?post_id={post.id}", status_code=303)
    finally:
        content_db.close()
        post_db.close()


# ==================== AI 创作 API ====================

@router.get("/settings")
def settings_page(request: Request):
    from config import load_ai_settings
    ai_settings = load_ai_settings()
    return request.app.state.templates.TemplateResponse(request, "settings.html", {
        "ai_settings": ai_settings,
        "request": request,
    })


@router.post("/api/ai/process")
def ai_process(content_id: int = Form(...)):
    """对指定素材运行 AI agent，返回处理结果并自动保存到 processed_contents 表"""
    from models.content import SessionLocal as ContentSessionLocal, Content, ProcessedContent
    from agent.content_agent import process_content_json

    db = ContentSessionLocal()
    try:
        item = db.query(Content).filter(Content.id == content_id).first()
        if not item:
            return JSONResponse({"success": False, "error": "素材不存在"}, status_code=404)

        user_input = f"标题：{item.title}\n\n正文：\n{item.body}"
        result = process_content_json(user_input)

        if "error" in result:
            return JSONResponse({
                "success": False,
                "source": {"id": item.id, "title": item.title},
                "raw": result,
            })

        # 保存 AI 加工结果到 processed_contents 表
        processed = ProcessedContent(
            original_content_id=item.id,
            title=result.get("title", ""),
            body=result.get("body", ""),
        )
        processed.set_tags(result.get("tags", []))
        processed.set_image_prompts(result.get("image_prompts", []))
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
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
    finally:
        db.close()


@router.get("/api/ai/config")
def get_ai_config():
    """获取当前 AI 配置"""
    from config import load_ai_settings
    return JSONResponse(load_ai_settings())


@router.post("/api/ai/save-config")
async def save_ai_config(request: Request):
    """保存 AI 配置"""
    from config import save_ai_settings
    data = await request.json()
    save_ai_settings(data)
    return JSONResponse({"success": True})


@router.get("/api/ai/system-prompt")
def get_system_prompt():
    """获取系统提示词"""
    from config import SYSTEM_PROMPT_FILE
    if os.path.exists(SYSTEM_PROMPT_FILE):
        with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
            return JSONResponse({"content": f.read()})
    return JSONResponse({"content": ""})


@router.post("/api/ai/save-system-prompt")
async def save_system_prompt(request: Request):
    """保存系统提示词"""
    from config import SYSTEM_PROMPT_FILE
    data = await request.json()
    with open(SYSTEM_PROMPT_FILE, "w", encoding="utf-8") as f:
        f.write(data.get("content", ""))
    return JSONResponse({"success": True})
