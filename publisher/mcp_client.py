import json
import subprocess
import os
import uuid

MCP_BINARY = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mcp-server", "xiaohongshu-mcp-windows-amd64.exe")


class MCPClient:
    def __init__(self):
        self.process = None
        self.request_id = 0
        self.protocol_version = "2024-11-05"

    def start(self):
        if self.process is not None:
            return
        self.process = subprocess.Popen(
            [MCP_BINARY],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._send_request("initialize", {
            "protocolVersion": self.protocol_version,
            "capabilities": {},
            "clientInfo": {"name": "xiaohongshu-poster", "version": "1.0.0"},
        })
        self._read_response()

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process = None

    def _send_request(self, method, params=None):
        self.request_id += 1
        req = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {},
        }
        body = json.dumps(req) + "\n"
        self.process.stdin.write(body)
        self.process.stdin.flush()

    def _read_response(self):
        line = self.process.stdout.readline()
        if line:
            return json.loads(line)
        return None

    def call_tool(self, tool_name, arguments):
        self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        resp = self._read_response()
        if resp and "result" in resp:
            content = resp["result"].get("content", [])
            if content:
                text_parts = [c["text"] for c in content if c.get("type") == "text"]
                return "\n".join(text_parts)
        if resp and "error" in resp:
            return f"Error: {resp['error'].get('message', str(resp['error']))}"
        return str(resp)

    def check_login(self):
        result = self.call_tool("check_login_status", {})
        return "已登录" in result

    def publish_content(self, title, content, images, tags=None, schedule_at=None):
        args = {
            "title": title,
            "content": content,
            "images": images or [],
        }
        if tags:
            args["tags"] = tags
        if schedule_at:
            args["schedule_at"] = schedule_at
        return self.call_tool("publish_content", args)
