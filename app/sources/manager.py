"""
小说源管理器 v2
统一入口，整合多引擎搜索 + 多站点解析器

职责：
  - search()   → 调 MultiEngineSearcher，三引擎并发+故障转移
  - get_book()      ┐
  - get_chapters()  ├→ 根据 source_url 自动路由到对应 Parser
  - get_content()   ┘
"""
import logging
from typing import Optional

from app.sources.base import SearchResult, BookInfo, ChapterInfo
from app.sources.search_engines import multi_engine_searcher
from app.sources.parsers import get_parser_by_url, get_parser

logger = logging.getLogger(__name__)


class SourceManager:

    # ── 搜索 ──────────────────────────────────────────────────────
    async def search_all(self, keyword: str) -> list[SearchResult]:
        """三引擎并发搜索，结果按可信度排序"""
        results = await multi_engine_searcher.search(keyword)
        logger.info(f"[Manager] 搜索「{keyword}」→ {len(results)} 条")
        return results

    # ── 书籍详情 ──────────────────────────────────────────────────
    async def get_book(self, source_id: str, source_url: str) -> Optional[BookInfo]:
        """
        根据 source_url 自动选解析器。
        source_id 作为 fallback（直接指定解析器类型）
        """
        parser = get_parser_by_url(source_url) or get_parser(source_id)
        if not parser:
            logger.warning(f"[Manager] 找不到解析器: {source_id} / {source_url}")
            return None
        try:
            return await parser.get_book(source_url)
        except Exception as e:
            logger.error(f"[Manager] get_book 异常: {e}")
            return None

    # ── 章节目录 ──────────────────────────────────────────────────
    async def get_chapters(self, source_id: str, source_url: str) -> list[ChapterInfo]:
        parser = get_parser_by_url(source_url) or get_parser(source_id)
        if not parser:
            return []
        try:
            return await parser.get_chapters(source_url)
        except Exception as e:
            logger.error(f"[Manager] get_chapters 异常: {e}")
            return []

    # ── 章节正文 ──────────────────────────────────────────────────
    async def get_content(self, source_id: str, chapter_url: str) -> Optional[str]:
        parser = get_parser_by_url(chapter_url) or get_parser(source_id)
        if not parser:
            logger.warning(f"[Manager] 找不到解析器: {source_id} / {chapter_url}")
            return None
        try:
            return await parser.get_content(chapter_url)
        except Exception as e:
            logger.error(f"[Manager] get_content 异常: {e}")
            return None


# 全局单例
source_manager = SourceManager()
