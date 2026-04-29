"""
MCP 客户端 — 使用官方 mcp Python SDK 以 Streamable HTTP 协议
连接 Go MCP Server，调用 publish_content 等工具。
"""
import asyncio
import json
import os
import time
import logging

import requests

from config import MCP_SERVER_URL

logger = logging.getLogger(__name__)
COOKIES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cookies.json")


def _run_async(coro):
    """在同步上下文中安全地运行 async 协程（新建 event loop）"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class MCPClient:
    """通过 MCP Streamable HTTP 协议与 Go MCP Server 通信"""

    def __init__(self, server_url=MCP_SERVER_URL):
        self._server_url = server_url

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        self.stop()

    # ─── MCP 核心通信 ────────────────────────────────────────────

    async def _call_tool_async(self, tool_name, arguments, timeout=120):
        """Async: 通过 MCP 协议调用工具"""
        from mcp.client.streamable_http import streamablehttp_client
        from mcp.client.session import ClientSession

        async with streamablehttp_client(self._server_url, timeout=timeout) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return result

    def _call_tool(self, tool_name, arguments, timeout=120):
        """同步封装：调用 MCP 工具并返回文本"""
        result = _run_async(self._call_tool_async(tool_name, arguments, timeout))

        if result.isError:
            text = result.content[0].text if result.content else "Unknown error"
            return f"Error: {text}"

        texts = []
        for item in result.content:
            if hasattr(item, 'text'):
                texts.append(item.text)
        return "\n".join(texts) if texts else str(result)

    # ─── 健康检查 ────────────────────────────────────────────────

    def health_check(self, timeout=8):
        """快速健康检查 — 使用 REST /health 端点（比 MCP ping 更快）"""
        try:
            resp = requests.get(
                self._server_url.replace("/mcp", "/health"),
                timeout=timeout,
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def _health_check_mcp_async(self, timeout=10):
        """通过 MCP ping 检查（较重，用于精确诊断）"""
        from mcp.client.streamable_http import streamablehttp_client
        from mcp.client.session import ClientSession

        async with streamablehttp_client(self._server_url, timeout=timeout) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await session.send_ping()
                return True

    # ─── 登录相关 ────────────────────────────────────────────────

    def check_login(self):
        """检查登录状态"""
        try:
            if os.path.exists(COOKIES_FILE):
                with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                if isinstance(cookies, list):
                    names = {c.get('name') for c in cookies if isinstance(c, dict)}
                    required = {'web_session', 'id_token', 'a1'}
                    if required & names:
                        now = time.time()
                        for c in cookies:
                            if isinstance(c, dict):
                                if c.get('name') in required:
                                    exp = c.get('expires')
                                    if exp and exp < now:
                                        return False
                        return True
        except Exception:
            pass

        # Fallback: try MCP check_login_status tool
        try:
            result = self._call_tool("check_login_status", {}, timeout=30)
            if "已登录" in result or "✅" in result:
                return True
        except Exception:
            pass
        return False

    def login(self):
        """获取登录二维码 — 使用 MCP get_login_qrcode 工具"""
        try:
            result = _run_async(self._call_tool_async("get_login_qrcode", {}, timeout=60))
            if result.isError:
                return {"success": False, "message": result.content[0].text if result.content else "获取失败"}

            # 提取二维码 base64
            qrcode_b64 = ""
            for item in result.content:
                if hasattr(item, 'data') and hasattr(item, 'mimeType'):
                    if 'image' in item.mimeType:
                        import base64
                        # item.data might be bytes or base64 string
                        data = item.data
                        if isinstance(data, str):
                            qrcode_b64 = data
                        elif isinstance(data, bytes):
                            qrcode_b64 = base64.b64encode(data).decode()
                        break
                if hasattr(item, 'text'):
                    txt = item.text
                    import re
                    match = re.search(r'data:image/png;base64,([A-Za-z0-9+/=]+)', txt)
                    if match:
                        qrcode_b64 = match.group(1)
                        break

            if qrcode_b64:
                return {"success": True, "qrcode": qrcode_b64, "message": "请扫码登录"}
            return {"success": False, "message": "未能解析登录二维码"}
        except Exception as e:
            return {"success": False, "message": f"获取二维码失败: {e}"}

    def delete_cookies(self):
        """删除 cookies 退出登录 — 使用 MCP delete_cookies 工具"""
        try:
            result = self._call_tool("delete_cookies", {}, timeout=30)
            if result.startswith("Error:"):
                return {"success": False, "message": result}
            return {"success": True, "message": "已退出登录"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ─── 核心发布 ────────────────────────────────────────────────

    def publish_content(self, title, content, images, tags=None, schedule_at=None):
        """通过 MCP publish_content 工具发布小红书图文内容"""
        args = {
            "title": title,
            "content": content,
            "images": images or [],
        }
        if tags:
            args["tags"] = tags
        if schedule_at:
            args["schedule_at"] = schedule_at

        try:
            return self._call_tool("publish_content", args, timeout=300)
        except Exception as e:
            return f"发布异常: {e}"

    # ─── 调试辅助 ────────────────────────────────────────────────

    def list_tools(self):
        """列出 MCP 服务器所有工具（调试用）"""
        async def _list():
            from mcp.client.streamable_http import streamablehttp_client
            from mcp.client.session import ClientSession

            async with streamablehttp_client(self._server_url, timeout=30) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    tools = []
                    for t in result.tools:
                        tools.append({
                            "name": t.name,
                            "description": t.description,
                        })
                    return tools

        try:
            return _run_async(_list())
        except Exception as e:
            return [{"error": str(e)}]
