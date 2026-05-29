"""
缓存服务 v3
新增：书架 CRUD、预缓存下一章、章节总数查询
"""
import logging
from typing import Optional

import aiosqlite

from app.database import get_db
from app.sources.base import BookInfo, ChapterInfo

logger = logging.getLogger(__name__)


# ── 书籍 ─────────────────────────────────────────────────────────

async def get_or_create_book(info: BookInfo) -> int:
    async with get_db() as db:
        row = await _fetchone(db,
            "SELECT id FROM books WHERE source_url=?", (info.source_url,))
        if row:
            await db.execute("""
                UPDATE books SET title=?,author=?,cover=?,intro=?,
                    updated_at=datetime('now','localtime')
                WHERE id=?
            """, (info.title, info.author, info.cover, info.intro, row["id"]))
            await db.commit()
            return row["id"]
        cur = await db.execute("""
            INSERT INTO books (title,author,cover,intro,source,source_url)
            VALUES (?,?,?,?,?,?)
        """, (info.title, info.author, info.cover, info.intro,
              info.source, info.source_url))
        await db.commit()
        return cur.lastrowid


async def get_book_by_id(book_id: int) -> Optional[dict]:
    async with get_db() as db:
        row = await _fetchone(db, "SELECT * FROM books WHERE id=?", (book_id,))
        return dict(row) if row else None


async def get_book_by_url(source_url: str) -> Optional[dict]:
    async with get_db() as db:
        row = await _fetchone(db,
            "SELECT * FROM books WHERE source_url=?", (source_url,))
        return dict(row) if row else None


# ── 章节 ─────────────────────────────────────────────────────────

async def save_chapters(book_id: int, chapters: list[ChapterInfo]):
    async with get_db() as db:
        await db.executemany("""
            INSERT OR IGNORE INTO chapters (book_id,title,chapter_url,idx)
            VALUES (?,?,?,?)
        """, [(book_id, c.title, c.chapter_url, c.index) for c in chapters])
        await db.commit()
    logger.info(f"[Cache] book {book_id}: 存 {len(chapters)} 章节")


async def get_chapters(book_id: int) -> list[dict]:
    async with get_db() as db:
        rows = await _fetchall(db,
            "SELECT * FROM chapters WHERE book_id=? ORDER BY idx ASC", (book_id,))
        return [dict(r) for r in rows]


async def get_chapter_by_id(chapter_id: int) -> Optional[dict]:
    async with get_db() as db:
        row = await _fetchone(db,
            "SELECT * FROM chapters WHERE id=?", (chapter_id,))
        return dict(row) if row else None


async def get_chapter_by_url(chapter_url: str) -> Optional[dict]:
    async with get_db() as db:
        row = await _fetchone(db,
            "SELECT * FROM chapters WHERE chapter_url=?", (chapter_url,))
        return dict(row) if row else None


async def get_chapter_count(book_id: int) -> int:
    async with get_db() as db:
        row = await _fetchone(db,
            "SELECT COUNT(*) as cnt FROM chapters WHERE book_id=?", (book_id,))
        return row["cnt"] if row else 0


async def get_adjacent_chapters(
    book_id: int, current_idx: int
) -> tuple[Optional[dict], Optional[dict]]:
    """一次查询获取上一章和下一章，减少 DB 往返"""
    async with get_db() as db:
        prev_row = await _fetchone(db, """
            SELECT * FROM chapters
            WHERE book_id=? AND idx < ?
            ORDER BY idx DESC LIMIT 1
        """, (book_id, current_idx))
        next_row = await _fetchone(db, """
            SELECT * FROM chapters
            WHERE book_id=? AND idx > ?
            ORDER BY idx ASC LIMIT 1
        """, (book_id, current_idx))
        return (dict(prev_row) if prev_row else None,
                dict(next_row) if next_row else None)


# ── 正文缓存 ─────────────────────────────────────────────────────

async def get_cached_content(chapter_id: int) -> Optional[str]:
    async with get_db() as db:
        row = await _fetchone(db,
            "SELECT content FROM contents WHERE chapter_id=?", (chapter_id,))
        return row["content"] if row else None


async def save_content(chapter_id: int, content: str):
    async with get_db() as db:
        await db.execute("""
            INSERT INTO contents (chapter_id, content, updated_at)
            VALUES (?,?,datetime('now','localtime'))
            ON CONFLICT(chapter_id) DO UPDATE SET
                content=excluded.content,
                updated_at=excluded.updated_at
        """, (chapter_id, content))
        await db.commit()


async def is_content_cached(chapter_id: int) -> bool:
    async with get_db() as db:
        row = await _fetchone(db,
            "SELECT 1 FROM contents WHERE chapter_id=?", (chapter_id,))
        return row is not None


# ── 阅读历史 ─────────────────────────────────────────────────────



async def get_cached_count(book_id: int) -> int:
    """统计已缓存正文的章节数（用于书籍页显示下载进度）"""
    async with get_db() as db:
        row = await _fetchone(db, """
            SELECT COUNT(*) as cnt FROM contents
            WHERE chapter_id IN (
                SELECT id FROM chapters WHERE book_id=?
            )
        """, (book_id,))
        return row["cnt"] if row else 0

async def update_history(book_id: int, chapter_id: int):
    async with get_db() as db:
        await db.execute("""
            INSERT INTO history (book_id,chapter_id,read_time)
            VALUES (?,?,datetime('now','localtime'))
            ON CONFLICT(book_id) DO UPDATE SET
                chapter_id=excluded.chapter_id,
                read_time=excluded.read_time
        """, (book_id, chapter_id))
        await db.commit()


async def get_history() -> list[dict]:
    async with get_db() as db:
        rows = await _fetchall(db, """
            SELECT h.*, b.title, b.author, b.cover, b.source_url,
                   c.title as chapter_title
            FROM history h
            JOIN books b ON b.id=h.book_id
            JOIN chapters c ON c.id=h.chapter_id
            ORDER BY h.read_time DESC LIMIT 30
        """)
        return [dict(r) for r in rows]


async def get_book_history(book_id: int) -> Optional[dict]:
    """获取某本书的阅读进度，附带章节标题"""
    async with get_db() as db:
        row = await _fetchone(db, """
            SELECT h.*, c.title as chapter_title
            FROM history h
            LEFT JOIN chapters c ON c.id = h.chapter_id
            WHERE h.book_id=?
        """, (book_id,))
        return dict(row) if row else None


# ── 书架 ─────────────────────────────────────────────────────────

async def add_to_shelf(book_id: int):
    async with get_db() as db:
        await db.execute("""
            INSERT OR IGNORE INTO bookshelf (book_id) VALUES (?)
        """, (book_id,))
        await db.commit()


async def remove_from_shelf(book_id: int):
    async with get_db() as db:
        await db.execute(
            "DELETE FROM bookshelf WHERE book_id=?", (book_id,))
        await db.commit()


async def is_on_shelf(book_id: int) -> bool:
    async with get_db() as db:
        row = await _fetchone(db,
            "SELECT 1 FROM bookshelf WHERE book_id=?", (book_id,))
        return row is not None


async def get_shelf() -> list[dict]:
    """返回书架列表，附带阅读进度"""
    async with get_db() as db:
        rows = await _fetchall(db, """
            SELECT bs.added_at,
                   b.id as book_id, b.title, b.author, b.cover,
                   b.source, b.source_url,
                   h.chapter_id as last_chapter_id,
                   c.title      as last_chapter_title,
                   h.read_time
            FROM bookshelf bs
            JOIN books b ON b.id=bs.book_id
            LEFT JOIN history h ON h.book_id=b.id
            LEFT JOIN chapters c ON c.id=h.chapter_id
            ORDER BY COALESCE(h.read_time, bs.added_at) DESC
        """)
        return [dict(r) for r in rows]


# ── 工具 ─────────────────────────────────────────────────────────

async def _fetchone(db: aiosqlite.Connection, sql: str,
                    params: tuple = ()) -> Optional[aiosqlite.Row]:
    cur = await db.execute(sql, params)
    return await cur.fetchone()


async def _fetchall(db: aiosqlite.Connection, sql: str,
                    params: tuple = ()) -> list[aiosqlite.Row]:
    cur = await db.execute(sql, params)
    return await cur.fetchall()
