import os
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


class MCPPublisher(BasePublisher):
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            from publisher.mcp_client import MCPClient
            self._client = MCPClient()
            self._client.start()
        return self._client

    def publish(self, post: Post) -> PublishResult:
        try:
            client = self._get_client()
            if not client.check_login():
                return PublishResult(
                    success=False,
                    message="未登录小红书，请先扫码登录",
                )

            # 把 URL 路径转回绝对路径
            image_paths = []
            for img_path in post.get_images():
                if img_path.startswith("/static/uploads/"):
                    abs_path = os.path.join(
                        os.path.dirname(os.path.dirname(__file__)),
                        "static", "uploads",
                        os.path.basename(img_path),
                    )
                    image_paths.append(abs_path)
                else:
                    image_paths.append(img_path)

            result_text = client.publish_content(
                title=post.title,
                content=post.body,
                images=image_paths,
                tags=post.get_tags() if post.get_tags() else None,
            )

            success = not any(kw in result_text for kw in ("失败", "Error", "异常", "超时"))
            return PublishResult(success=success, message=result_text)
        except Exception as e:
            return PublishResult(success=False, message=f"发布异常: {e}")

    def close(self):
        if self._client:
            self._client.stop()
            self._client = None


_mcp_publisher = None


def get_publisher():
    global _mcp_publisher
    if _mcp_publisher is None:
        _mcp_publisher = MCPPublisher()
    return _mcp_publisher
