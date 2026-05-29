"""
全书下载服务 v1
功能：
  - 把一本书所有章节正文批量抓取并缓存进 SQLite
  - 限速并发（默认 3 个协程同时跑，避免被封）
  - 实时进度追踪（写入 download_tasks 表）
  - 支持暂停 / 继续 / 取消
  - 跳过已缓存章节（断点续传）

用法：
    task_id = await start_download(book_id)
    status  = await get_task(book_id)
    await pause_download(book_id)
    await resume_download(book_id)
    await cancel_download(book_id)
"""
import asyncio
import logging
from typing import Optional

from app.database import get_db
from app.services.cache import (
    get_chapters, is_content_cached, save_content, get_book_by_id
)
from app.sources.manager import source_manager

logger = logging.getLogger(__name__)

# 并发限制：同时下载的章节数
CONCURRENCY = 3
# 每章下载完后的等待（秒），避免过快触发反爬
CHAPTER_DELAY = 0.8

# 内存中追踪「暂停信号」：book_id → asyncio.Event
# Event 被 clear() 时下载协程会暂停等待
_pause_events: dict[int, asyncio.Event] = {}
# 取消信号
_cancel_flags: dict[int, bool] = {}


# ── 公开接口 ─────────────────────────────────────────────────────

async def start_download(book_id: int) -> dict:
    """
    启动全书下载任务。
    - 若已有 running 任务，直接返回当前状态
    - 若已有 paused 任务，恢复继续
    - 否则新建任务并在后台启动协程
    """
    task = await get_task(book_id)

    if task and task["status"] == "running":
        return task

    if task and task["status"] == "paused":
        return await resume_download(book_id)

    # 计算总章节数
    chapters = await get_chapters(book_id)
    total    = len(chapters)
    if total == 0:
        return {"status": "error", "message": "该书没有章节，请先在书籍页加载目录"}

    # 写入 / 重置任务记录
    await _upsert_task(book_id, "running", total=total, done=0, failed=0)
    task = await get_task(book_id)

    # 初始化暂停和取消信号
    ev = asyncio.Event()
    ev.set()   # 默认不暂停
    _pause_events[book_id] = ev
    _cancel_flags[book_id] = False

    # 后台启动，不阻塞 HTTP 响应
    asyncio.create_task(_download_worker(book_id, chapters))
    logger.info(f"[Downloader] 开始下载 book {book_id}，共 {total} 章")
    return task


async def pause_download(book_id: int) -> dict:
    """暂停下载"""
    ev = _pause_events.get(book_id)
    if ev:
        ev.clear()   # 下载协程会在 await ev.wait() 处阻塞
    await _set_status(book_id, "paused")
    return await get_task(book_id)


async def resume_download(book_id: int) -> dict:
    """恢复已暂停的下载"""
    task = await get_task(book_id)
    if not task:
        return {"status": "not_found"}

    ev = _pause_events.get(book_id)
    if ev is None:
        # 进程重启后内存状态丢失，需要重新拉起协程
        ev = asyncio.Event()
        _pause_events[book_id] = ev

    ev.set()
    _cancel_flags[book_id] = False
    await _set_status(book_id, "running")

    # 重新拉起后台协程（从未缓存的章节继续）
    chapters = await get_chapters(book_id)
    asyncio.create_task(_download_worker(book_id, chapters))
    logger.info(f"[Downloader] 恢复下载 book {book_id}")
    return await get_task(book_id)


async def cancel_download(book_id: int) -> dict:
    """取消下载（清除任务记录）"""
    _cancel_flags[book_id] = True
    ev = _pause_events.get(book_id)
    if ev:
        ev.set()   # 先解除暂停，让协程跑起来然后检测取消
    await _delete_task(book_id)
    _pause_events.pop(book_id, None)
    _cancel_flags.pop(book_id, None)
    return {"status": "cancelled"}


async def get_task(book_id: int) -> Optional[dict]:
    """获取下载任务状态"""
    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM download_tasks WHERE book_id=?", (book_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_all_tasks() -> list[dict]:
    """获取所有下载任务（用于管理页展示）"""
    async with get_db() as db:
        cur = await db.execute("""
            SELECT dt.*, b.title, b.author, b.source, b.source_url
            FROM download_tasks dt
            JOIN books b ON b.id = dt.book_id
            ORDER BY dt.updated_at DESC
        """)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ── 下载核心协程 ──────────────────────────────────────────────────

async def _download_worker(book_id: int, chapters: list[dict]):
    """
    实际执行下载的后台协程。
    使用 asyncio.Semaphore 控制并发，每章下载后更新进度。
    """
    ev      = _pause_events.get(book_id)
    book    = await get_book_by_id(book_id)
    if not book:
        return

    sem     = asyncio.Semaphore(CONCURRENCY)
    done    = 0
    failed  = 0

    # 只下载还没缓存的章节
    pending = []
    for ch in chapters:
        if not await is_content_cached(ch["id"]):
            pending.append(ch)
        else:
            done += 1

    total = len(chapters)
    # 先把已缓存数量同步上去
    await _update_progress(book_id, done, failed, total)

    logger.info(f"[Downloader] book {book_id}: {len(pending)} 章待下载，{done} 章已缓存")

    async def fetch_one(ch: dict):
        nonlocal done, failed
        # 暂停检测
        if ev:
            await ev.wait()
        # 取消检测
        if _cancel_flags.get(book_id):
            return

        async with sem:
            if _cancel_flags.get(book_id):
                return
            try:
                content = await source_manager.get_content(
                    book["source"], ch["chapter_url"]
                )
                if content:
                    await save_content(ch["id"], content)
                    done += 1
                    logger.debug(f"[DL] ✅ [{done}/{total}] {ch['title']}")
                else:
                    failed += 1
                    logger.warning(f"[DL] ❌ {ch['title']} 抓取失败")
            except Exception as e:
                failed += 1
                logger.warning(f"[DL] 异常 {ch['title']}: {e}")

            await _update_progress(book_id, done, failed, total)
            await asyncio.sleep(CHAPTER_DELAY)

    # 并发跑所有待下载章节
    await asyncio.gather(*[fetch_one(ch) for ch in pending])

    # 判断最终状态
    if _cancel_flags.get(book_id):
        logger.info(f"[Downloader] book {book_id} 已取消")
        return

    final_status = "done" if failed == 0 else (
        "failed" if done == 0 else "done"   # 部分失败也算完成
    )
    await _set_status(book_id, final_status)
    logger.info(f"[Downloader] book {book_id} 完成: {done} 成功, {failed} 失败")
    _pause_events.pop(book_id, None)
    _cancel_flags.pop(book_id, None)


# ── DB 工具 ───────────────────────────────────────────────────────

async def _upsert_task(book_id: int, status: str,
                        total: int = 0, done: int = 0, failed: int = 0):
    async with get_db() as db:
        await db.execute("""
            INSERT INTO download_tasks (book_id, status, total, done, failed, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))
            ON CONFLICT(book_id) DO UPDATE SET
                status=excluded.status,
                total=excluded.total,
                done=excluded.done,
                failed=excluded.failed,
                updated_at=excluded.updated_at
        """, (book_id, status, total, done, failed))
        await db.commit()


async def _update_progress(book_id: int, done: int, failed: int, total: int):
    async with get_db() as db:
        await db.execute("""
            UPDATE download_tasks
            SET done=?, failed=?, updated_at=datetime('now','localtime')
            WHERE book_id=?
        """, (done, failed, book_id))
        await db.commit()


async def _set_status(book_id: int, status: str):
    async with get_db() as db:
        await db.execute("""
            UPDATE download_tasks
            SET status=?, updated_at=datetime('now','localtime')
            WHERE book_id=?
        """, (status, book_id))
        await db.commit()


async def _delete_task(book_id: int):
    async with get_db() as db:
        await db.execute(
            "DELETE FROM download_tasks WHERE book_id=?", (book_id,))
        await db.commit()
