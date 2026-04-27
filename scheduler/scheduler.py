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
