import json
from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

from config import CONTENT_DB_URL

engine = create_engine(CONTENT_DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Content(Base):
    __tablename__ = "contents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_plat = Column(String(50), nullable=False, default="")
    title = Column(String(200), nullable=False, default="")
    body = Column(Text, nullable=False, default="")
    images = Column(Text, nullable=False, default="[]")
    tags = Column(Text, nullable=False, default="[]")
    imported = Column(Boolean, nullable=False, default=False)
    imported_to = Column(Integer, nullable=True)
    created_at = Column(String(30), nullable=False, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def get_images(self):
        return json.loads(self.images) if self.images else []

    def set_images(self, urls):
        self.images = json.dumps(urls or [], ensure_ascii=False)

    def get_tags(self):
        return json.loads(self.tags) if self.tags else []

    def set_tags(self, tags_list):
        self.tags = json.dumps(tags_list or [], ensure_ascii=False)

    def to_dict(self):
        return {
            "id": self.id,
            "source_plat": self.source_plat,
            "title": self.title,
            "body": self.body,
            "images": self.get_images(),
            "tags": self.get_tags(),
            "imported": self.imported,
            "imported_to": self.imported_to,
            "created_at": self.created_at,
        }


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


Base.metadata.create_all(bind=engine)
