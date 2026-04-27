import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.routes import router
from scheduler.scheduler import start_scheduler, shutdown_scheduler
from config import UPLOAD_DIR

os.makedirs(UPLOAD_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="小红书发帖助手", lifespan=lifespan)

templates = Jinja2Templates(directory="templates")
app.state.templates = templates

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
