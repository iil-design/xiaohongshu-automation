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
                    message="未登录小红书，请先运行 mcp-server/xiaohongshu-login-windows-amd64.exe 扫码登录",
                )

            # Convert image URLs back to absolute paths
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
            )

            success = "失败" not in result_text and "Error" not in result_text
            return PublishResult(success=success, message=result_text)
        except Exception as e:
            return PublishResult(success=False, message=f"MCP 发布异常: {e}")

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
