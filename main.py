import asyncio
import os
import subprocess
import threading
import time
import urllib.request
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.routes import router
from scheduler.scheduler import start_scheduler, shutdown_scheduler
from config import UPLOAD_DIR, BASE_DIR, MCP_SERVER_URL

os.makedirs(UPLOAD_DIR, exist_ok=True)

_mcp_proc = None
_mcp_lock = threading.Lock()
_MCP_HEALTH_URL = MCP_SERVER_URL.replace("/mcp", "/health")


def _start_mcp_server():
    global _mcp_proc
    bin_path = os.path.join(BASE_DIR, "mcp-server", "xiaohongshu-mcp-windows-amd64.exe")
    print(f"[MCP] 启动MCP服务器: {bin_path}")
    if not os.path.exists(bin_path):
        print(f"[错误] MCP二进制文件不存在: {bin_path}")
        return None

    with _mcp_lock:
        if _mcp_proc and _mcp_proc.poll() is None:
            try:
                _mcp_proc.terminate()
                _mcp_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                _mcp_proc.kill()
            except Exception:
                pass
            _mcp_proc = None

        proc = subprocess.Popen(
            [bin_path, "-port", ":28002", "-headless=false",
             "-bin", "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding="utf-8", errors="replace",
        )
        _mcp_proc = proc
    return proc


def _stop_mcp_server(proc):
    global _mcp_proc
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception as e:
            print(f"[警告] 停止MCP服务器失败: {e}")
    with _mcp_lock:
        if _mcp_proc and _mcp_proc.pid == proc.pid:
            _mcp_proc = None


async def _wait_for_mcp(proc, timeout=30):
    if proc is None:
        return False

    def _check():
        try:
            req = urllib.request.Request(_MCP_HEALTH_URL)
            resp = urllib.request.urlopen(req, timeout=5)
            return resp.status == 200
        except Exception:
            return False

    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if proc.poll() is not None:
            stdout = proc.stdout.read() if proc.stdout else ""
            print(f"[错误] MCP进程异常退出，返回码: {proc.returncode}")
            if stdout:
                print(f"[MCP输出] {stdout[:500]}")
            return False

        ok = await loop.run_in_executor(None, _check)
        if ok:
            print(f"[MCP] MCP服务器已就绪，PID: {proc.pid}")
            return True

        await asyncio.sleep(1)

    print(f"[错误] MCP服务器启动超时 ({timeout}s)")
    return False


def restart_mcp_server():
    """重启 MCP 服务器"""
    print("[MCP] 正在重启MCP服务器...")
    with _mcp_lock:
        old_proc = _mcp_proc
    if old_proc:
        _stop_mcp_server(old_proc)

    new_proc = _start_mcp_server()
    if new_proc is None:
        return False

    deadline = time.time() + 30
    while time.time() < deadline:
        if new_proc.poll() is not None:
            return False
        try:
            req = urllib.request.Request(_MCP_HEALTH_URL)
            urllib.request.urlopen(req, timeout=5)
            print(f"[MCP] MCP服务器已重启，PID: {new_proc.pid}")
            return True
        except Exception:
            time.sleep(1)
    return False


def check_mcp_health():
    """检查 MCP 服务器是否响应"""
    try:
        req = urllib.request.Request(_MCP_HEALTH_URL)
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status == 200
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    mcp_proc = _start_mcp_server()
    ready = await _wait_for_mcp(mcp_proc)
    if not ready:
        print("[警告] MCP 服务未就绪，扫码登录等功能将不可用")
    start_scheduler()
    yield
    shutdown_scheduler()
    _stop_mcp_server(mcp_proc)


app = FastAPI(title="小红书发帖助手", lifespan=lifespan)

templates = Jinja2Templates(directory="templates")
app.state.templates = templates

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8890, reload=False)
