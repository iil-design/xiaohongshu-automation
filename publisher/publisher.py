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
