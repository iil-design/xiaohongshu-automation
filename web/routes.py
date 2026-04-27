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
