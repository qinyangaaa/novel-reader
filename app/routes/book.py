"""
书籍路由 v4
GET  /book                      → 章节目录页
GET  /api/toc/{book_id}         → 目录 JSON（阅读页浮窗用）
POST /api/download/{book_id}    → 启动全书下载
POST /api/download/{book_id}/pause   → 暂停
POST /api/download/{book_id}/resume  → 恢复
DELETE /api/download/{book_id}  → 取消
GET  /api/download/{book_id}    → 查询进度
GET  /api/switch-source         → 换源搜索（同书名在其他站找）
"""
import asyncio
from urllib.parse import unquote

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from app.config import templates

from app.sources.manager import source_manager
from app.services import cache
from app.services.downloader import (
    start_download, pause_download, resume_download,
    cancel_download, get_task, get_all_tasks
)

router = APIRouter()


# ── 书籍详情 + 目录 ───────────────────────────────────────────────

@router.get("/book", response_class=HTMLResponse)
async def book_detail(
    request: Request,
    source:  str = Query(...),
    url:     str = Query(...),
    refresh: int = Query(default=0),
):
    source_url = unquote(url)

    book_row = await cache.get_book_by_url(source_url)
    chapters  = []

    if book_row and not refresh:
        chapters = await cache.get_chapters(book_row["id"])

    if not book_row or not chapters or refresh:
        book_info = await source_manager.get_book(source, source_url)
        if not book_info:
            raise HTTPException(404, "获取书籍信息失败，请返回重试")

        book_id  = await cache.get_or_create_book(book_info)
        book_row = await cache.get_book_by_id(book_id)

        chapter_list = await source_manager.get_chapters(source, source_url)
        if chapter_list:
            await cache.save_chapters(book_id, chapter_list)
            chapters = await cache.get_chapters(book_id)

    history      = await cache.get_book_history(book_row["id"])
    on_shelf     = await cache.is_on_shelf(book_row["id"])
    dl_task      = await get_task(book_row["id"])
    cached_count = await cache.get_cached_count(book_row["id"])

    return templates.TemplateResponse(request, "book.html", {
            "book":         book_row,
        "chapters":     chapters,
        "history":      history,
        "source":       source,
        "on_shelf":     on_shelf,
        "dl_task":      dl_task,
        "cached_count": cached_count
        })


# ── 目录 JSON ─────────────────────────────────────────────────────

@router.get("/api/toc/{book_id}")
async def api_toc(book_id: int):
    chapters = await cache.get_chapters(book_id)
    if not chapters:
        raise HTTPException(404, "无章节数据")
    return [{"id": c["id"], "idx": c["idx"], "title": c["title"]}
            for c in chapters]


# ── 下载任务接口 ──────────────────────────────────────────────────

@router.post("/api/download/{book_id}")
async def download_start(book_id: int):
    book = await cache.get_book_by_id(book_id)
    if not book:
        raise HTTPException(404, "书籍不存在")
    result = await start_download(book_id)
    return JSONResponse(result)


@router.post("/api/download/{book_id}/pause")
async def download_pause(book_id: int):
    result = await pause_download(book_id)
    return JSONResponse(result)


@router.post("/api/download/{book_id}/resume")
async def download_resume(book_id: int):
    result = await resume_download(book_id)
    return JSONResponse(result)


@router.delete("/api/download/{book_id}")
async def download_cancel(book_id: int):
    result = await cancel_download(book_id)
    return JSONResponse(result)


@router.get("/api/download/{book_id}")
async def download_status(book_id: int):
    task = await get_task(book_id)
    if not task:
        return JSONResponse({"status": "none"})
    return JSONResponse(dict(task))


# ── 换源接口 ──────────────────────────────────────────────────────

@router.get("/api/switch-source")
async def switch_source(
    book_id: int = Query(...),
    title:   str = Query(...),
):
    """
    用书名重新搜索，返回其他站点的结果
    前端展示列表供用户选择换源
    """
    results = await source_manager.search_all(title)
    # 排除当前已有的来源 URL
    current_book = await cache.get_book_by_id(book_id)
    current_url  = current_book["source_url"] if current_book else ""

    alternatives = [
        {
            "title":      r.title,
            "author":     r.author,
            "source":     r.source,
            "source_url": r.source_url,
            "intro":      r.intro[:100],
        }
        for r in results
        if r.source_url != current_url
    ]
    return JSONResponse({"results": alternatives[:12]})


# ── 下载管理页 ────────────────────────────────────────────────────

@router.get("/downloads", response_class=HTMLResponse)
async def downloads_page(request: Request):
    tasks = await get_all_tasks()
    return templates.TemplateResponse(request, "downloads.html", {
            "tasks":   tasks
        })
