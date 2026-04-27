import json
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
    updated_at = Column(
        String(30),
        nullable=False,
        default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        onupdate=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

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
