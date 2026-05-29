"""
搜索历史服务
保存/读取/删除搜索关键词
"""
import logging
from app.database import get_db

logger = logging.getLogger(__name__)
MAX_HISTORY = 20   # 最多保留条数


async def add_search(keyword: str):
    """记录一次搜索（同关键词覆盖时间戳，最多保留 MAX_HISTORY 条）"""
    kw = keyword.strip()
    if not kw:
        return
    async with get_db() as db:
        await db.execute("""
            INSERT INTO search_history (keyword, searched_at)
            VALUES (?, datetime('now','localtime'))
            ON CONFLICT(keyword) DO UPDATE SET
                searched_at = datetime('now','localtime')
        """, (kw,))
        # 超出上限则删掉最旧的
        await db.execute("""
            DELETE FROM search_history
            WHERE id NOT IN (
                SELECT id FROM search_history
                ORDER BY searched_at DESC
                LIMIT ?
            )
        """, (MAX_HISTORY,))
        await db.commit()


async def get_search_history() -> list[str]:
    """返回最近搜索关键词列表（最新在前）"""
    async with get_db() as db:
        cur = await db.execute(
            "SELECT keyword FROM search_history ORDER BY searched_at DESC LIMIT ?",
            (MAX_HISTORY,)
        )
        rows = await cur.fetchall()
        return [r["keyword"] for r in rows]


async def delete_keyword(keyword: str):
    async with get_db() as db:
        await db.execute(
            "DELETE FROM search_history WHERE keyword=?", (keyword,))
        await db.commit()


async def clear_history():
    async with get_db() as db:
        await db.execute("DELETE FROM search_history")
        await db.commit()
