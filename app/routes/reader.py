"""
阅读路由 v3
GET  /read/{chapter_id}          → 阅读页
GET  /api/prefetch/{chapter_id}  → 后台预缓存（JS 静默调用）
GET  /history                    → 历史页
"""
import asyncio
import logging

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from app.config import templates

from app.sources.manager import source_manager
from app.services import cache

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/read/{chapter_id}", response_class=HTMLResponse)
async def read_chapter(request: Request, chapter_id: int):

    # ── 1. 基础数据 ───────────────────────────────────────────────
    chapter = await cache.get_chapter_by_id(chapter_id)
    if not chapter:
        raise HTTPException(404, "章节不存在")

    book = await cache.get_book_by_id(chapter["book_id"])
    if not book:
        raise HTTPException(404, "书籍不存在")

    # ── 2. 正文（缓存优先）────────────────────────────────────────
    content = await cache.get_cached_content(chapter_id)
    from_cache = bool(content)

    if not content:
        content = await source_manager.get_content(
            book["source"], chapter["chapter_url"]
        )
        if content:
            await cache.save_content(chapter_id, content)
        else:
            content = "⚠️ 正文获取失败，请稍后重试或换个来源。"

    # ── 3. 上/下章（一次查询）──────────────────────────────────────
    prev_ch, next_ch = await cache.get_adjacent_chapters(
        book["id"], chapter["idx"]
    )

    # ── 4. 进度计算 ────────────────────────────────────────────────
    total_chapters = await cache.get_chapter_count(book["id"])
    progress = 0
    if total_chapters > 1:
        progress = round(chapter["idx"] / (total_chapters - 1) * 100)

    # ── 5. 书架状态 ────────────────────────────────────────────────
    on_shelf = await cache.is_on_shelf(book["id"])

    # ── 6. 更新历史（异步，不阻塞渲染）──────────────────────────────
    asyncio.create_task(cache.update_history(book["id"], chapter_id))

    return templates.TemplateResponse(request, "reader.html", {
            "book":           book,
        "chapter":        chapter,
        "content":        content,
        "prev_chapter":   prev_ch,
        "next_chapter":   next_ch,
        "from_cache":     from_cache,
        "source":         book["source"],
        "progress":       progress,
        "total_chapters": total_chapters,
        "on_shelf":       on_shelf
        })


@router.get("/api/prefetch/{chapter_id}")
async def prefetch_chapter(chapter_id: int):
    """
    预缓存接口——阅读页 JS 在后台悄悄调用，
    把下一章内容提前存入 SQLite，翻页时秒开。
    """
    # 已缓存直接返回
    if await cache.is_content_cached(chapter_id):
        return JSONResponse({"status": "cached"})

    chapter = await cache.get_chapter_by_id(chapter_id)
    if not chapter:
        return JSONResponse({"status": "not_found"}, status_code=404)

    book = await cache.get_book_by_id(chapter["book_id"])
    if not book:
        return JSONResponse({"status": "no_book"}, status_code=404)

    content = await source_manager.get_content(
        book["source"], chapter["chapter_url"]
    )
    if content:
        await cache.save_content(chapter_id, content)
        logger.info(f"[prefetch] 预缓存成功: chapter {chapter_id}")
        return JSONResponse({"status": "ok"})

    return JSONResponse({"status": "fetch_failed"}, status_code=502)


# ── 书架操作 ─────────────────────────────────────────────────────

@router.post("/api/shelf/{book_id}")
async def shelf_add(book_id: int):
    await cache.add_to_shelf(book_id)
    return JSONResponse({"status": "added"})


@router.delete("/api/shelf/{book_id}")
async def shelf_remove(book_id: int):
    await cache.remove_from_shelf(book_id)
    return JSONResponse({"status": "removed"})


# ── 历史 & 书架页 ─────────────────────────────────────────────────

@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    records = await cache.get_history()
    return templates.TemplateResponse(request, "history.html", {
            "records": records
        })


@router.get("/shelf", response_class=HTMLResponse)
async def shelf_page(request: Request):
    books = await cache.get_shelf()
    return templates.TemplateResponse(request, "bookshelf.html", {
            "books":   books
        })
