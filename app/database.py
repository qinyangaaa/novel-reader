"""
数据库模块 v4-fix
get_db() 改为异步上下文管理器，彻底解决 "threads can only be started once" 问题
"""
import aiosqlite
import logging
from contextlib import asynccontextmanager
from app.config import DB_PATH

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_db():
    """
    正确用法：
        async with get_db() as db:
            ...
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        yield conn


async def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS books (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                author      TEXT    DEFAULT '',
                cover       TEXT    DEFAULT '',
                intro       TEXT    DEFAULT '',
                source      TEXT    NOT NULL,
                source_url  TEXT    NOT NULL UNIQUE,
                created_at  TEXT    DEFAULT (datetime('now','localtime')),
                updated_at  TEXT    DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS chapters (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                title       TEXT    NOT NULL,
                chapter_url TEXT    NOT NULL,
                idx         INTEGER DEFAULT 0,
                UNIQUE(book_id, chapter_url)
            );

            CREATE TABLE IF NOT EXISTS contents (
                chapter_id  INTEGER PRIMARY KEY REFERENCES chapters(id) ON DELETE CASCADE,
                content     TEXT    NOT NULL,
                updated_at  TEXT    DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                chapter_id  INTEGER NOT NULL REFERENCES chapters(id),
                read_time   TEXT    DEFAULT (datetime('now','localtime')),
                UNIQUE(book_id)
            );

            CREATE TABLE IF NOT EXISTS bookshelf (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE UNIQUE,
                added_at    TEXT    DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS download_tasks (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id      INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE UNIQUE,
                status       TEXT    NOT NULL DEFAULT 'pending',
                total        INTEGER DEFAULT 0,
                done         INTEGER DEFAULT 0,
                failed       INTEGER DEFAULT 0,
                created_at   TEXT    DEFAULT (datetime('now','localtime')),
                updated_at   TEXT    DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS search_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword     TEXT    NOT NULL,
                searched_at TEXT    DEFAULT (datetime('now','localtime')),
                UNIQUE(keyword)
            );

            CREATE INDEX IF NOT EXISTS idx_chapters_book  ON chapters(book_id, idx);
            CREATE INDEX IF NOT EXISTS idx_history_book   ON history(book_id);
            CREATE INDEX IF NOT EXISTS idx_history_time   ON history(read_time DESC);
            CREATE INDEX IF NOT EXISTS idx_shelf_added    ON bookshelf(added_at DESC);
            CREATE INDEX IF NOT EXISTS idx_dl_status      ON download_tasks(status);
            CREATE INDEX IF NOT EXISTS idx_search_hist    ON search_history(searched_at DESC);
        """)
        await db.commit()
        logger.info(f"[DB] 初始化完成: {DB_PATH}")
