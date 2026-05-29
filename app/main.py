"""
小说聚合阅读器 — 主入口 v4
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import templates, STATIC_DIR
from app.database import init_db
from app.utils.http import close_client
from app.routes import search, book, reader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 启动中…")
    await init_db()
    logger.info("✅ 数据库就绪")
    yield
    await close_client()
    logger.info("👋 已关闭")


app = FastAPI(
    title="小说聚合阅读器",
    version="0.4.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(search.router)
app.include_router(book.router)
app.include_router(reader.router)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    from app.services.cache import get_history
    records = await get_history()
    return templates.TemplateResponse(request, "index.html", {
            "records": records
        })


@app.get("/health")
async def health():
    from app.services.downloader import get_all_tasks
    tasks   = await get_all_tasks()
    running = sum(1 for t in tasks if t["status"] == "running")
    return {"status": "ok", "version": "0.4.0", "downloads_running": running}
