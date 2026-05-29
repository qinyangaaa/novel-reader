"""
搜索引擎适配器 v2
支持 Yandex / Bing / DuckDuckGo 三引擎，带自动故障转移

使用策略：
  1. 优先 Yandex（对中文内容友好，索引全）
  2. Yandex 失败 → 自动切 Bing
  3. Bing 失败  → 自动切 DuckDuckGo
  4. 三个都失败 → 返回空列表，记录日志

注意：搜索引擎都有反爬机制，失败是正常的，靠 fallback 保证可用性
"""
import logging
import re
from abc import ABC, abstractmethod
from typing import Optional
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup

from app.sources.registry import detect_parser_id, site_filter_query
from app.sources.base import SearchResult
from app.utils.http import fetch_html

logger = logging.getLogger(__name__)


# ── 通用工具 ──────────────────────────────────────────────────────

def _clean_title(title: str, keyword: str) -> str:
    """去掉标题里的网站名后缀"""
    for sep in [" - ", " | ", " – ", " — ", " _ ", "–", "—"]:
        if sep in title:
            title = title.split(sep)[0].strip()
            break
    # 去掉末尾的 "小说" "txt" 等
    title = re.sub(r"\s*(小说|全文|免费|TXT|txt)\s*$", "", title).strip()
    return title or keyword


def _is_valid_novel_url(url: str) -> bool:
    """过滤掉首页/搜索页/非书籍页"""
    try:
        p = urlparse(url)
        path = p.path
        # 路径太短通常是首页或分类页
        if len(path) < 4:
            return False
        # 排除搜索结果页
        if any(kw in url for kw in ("search", "s=", "q=", "keyword", "result")):
            return False
        return True
    except Exception:
        return False


# ════════════════════════════════════════════════════════════════════
# 引擎基类
# ════════════════════════════════════════════════════════════════════

class BaseSearchEngine(ABC):
    NAME = ""

    @abstractmethod
    async def search(self, keyword: str, max_results: int = 15) -> list[SearchResult]:
        pass

    def _make_result(self, url: str, title: str, snippet: str,
                     keyword: str) -> Optional[SearchResult]:
        """构造 SearchResult，不符合条件返回 None"""
        if not url or not url.startswith("http"):
            return None
        parser_id = detect_parser_id(url)
        if not parser_id:
            return None
        if not _is_valid_novel_url(url):
            return None
        return SearchResult(
            title      = _clean_title(title, keyword),
            author     = "",
            cover      = "",
            intro      = snippet[:250],
            source     = parser_id,
            source_url = url,
        )


# ════════════════════════════════════════════════════════════════════
# Yandex
# ════════════════════════════════════════════════════════════════════

class YandexEngine(BaseSearchEngine):
    NAME = "Yandex"

    # 莫斯科区域代码（对中文搜索影响不大，但 Yandex 要求）
    _BASE = "https://yandex.com/search/?text={q}&lr=213&p=0"
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
        "Referer": "https://yandex.com/",
    }

    async def search(self, keyword: str, max_results: int = 15) -> list[SearchResult]:
        site_filter = site_filter_query()
        query = f"{keyword} {site_filter}"
        url = self._BASE.format(q=quote_plus(query))

        logger.info(f"[Yandex] 搜索: {keyword}")
        html = await fetch_html(url, headers=self._HEADERS, retries=2)
        if not html:
            logger.warning("[Yandex] 无响应")
            return []

        return self._parse(html, keyword, max_results)

    def _parse(self, html: str, keyword: str, max_results: int) -> list[SearchResult]:
        soup = BeautifulSoup(html, "lxml")
        results: list[SearchResult] = []
        seen: set[str] = set()

        # Yandex 结果条目选择器（多套兼容不同版本）
        items = (
            soup.select("li.serp-item[data-cid]") or
            soup.select("li.serp-item") or
            soup.select("div.organic") or
            []
        )

        for item in items:
            # 提取 URL
            href = ""
            for sel in ("a.organic__url", "a.link_theme_outer", "h2 a", "a[href]"):
                tag = item.select_one(sel)
                if tag:
                    href = tag.get("href", "")
                    if href.startswith("http"):
                        break

            if not href or href in seen:
                continue
            seen.add(href)

            # 提取标题
            title = ""
            for sel in ("h2", ".organic__title", ".title", "h3"):
                t = item.select_one(sel)
                if t:
                    title = t.get_text(strip=True)
                    break

            # 提取摘要
            snippet = ""
            for sel in (".organic__text", ".text-container", ".organic__content"):
                s = item.select_one(sel)
                if s:
                    snippet = s.get_text(strip=True)
                    break

            r = self._make_result(href, title, snippet, keyword)
            if r:
                results.append(r)
                if len(results) >= max_results:
                    break

        logger.info(f"[Yandex] 命中 {len(results)} 条")
        return results


# ════════════════════════════════════════════════════════════════════
# Bing
# ════════════════════════════════════════════════════════════════════

class BingEngine(BaseSearchEngine):
    NAME = "Bing"

    _BASE = "https://www.bing.com/search?q={q}&setlang=zh-CN&cc=CN"
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.bing.com/",
    }

    async def search(self, keyword: str, max_results: int = 15) -> list[SearchResult]:
        site_filter = site_filter_query()
        query = f"{keyword} {site_filter}"
        url = self._BASE.format(q=quote_plus(query))

        logger.info(f"[Bing] 搜索: {keyword}")
        html = await fetch_html(url, headers=self._HEADERS, retries=2)
        if not html:
            logger.warning("[Bing] 无响应")
            return []

        return self._parse(html, keyword, max_results)

    def _parse(self, html: str, keyword: str, max_results: int) -> list[SearchResult]:
        soup = BeautifulSoup(html, "lxml")
        results: list[SearchResult] = []
        seen: set[str] = set()

        # Bing 结果在 li.b_algo
        for item in soup.select("li.b_algo"):
            # 标题链接
            a = item.select_one("h2 a")
            if not a:
                continue
            href  = a.get("href", "")
            title = a.get_text(strip=True)
            if not href or href in seen:
                continue
            seen.add(href)

            # 摘要
            snippet = ""
            cap = item.select_one(".b_caption p, .b_caption .b_snippet")
            if cap:
                snippet = cap.get_text(strip=True)

            r = self._make_result(href, title, snippet, keyword)
            if r:
                results.append(r)
                if len(results) >= max_results:
                    break

        logger.info(f"[Bing] 命中 {len(results)} 条")
        return results


# ════════════════════════════════════════════════════════════════════
# DuckDuckGo（HTML 版，不需要 API Key）
# ════════════════════════════════════════════════════════════════════

class DuckDuckGoEngine(BaseSearchEngine):
    NAME = "DuckDuckGo"

    _BASE = "https://html.duckduckgo.com/html/?q={q}"
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
            "Gecko/20100101 Firefox/125.0"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://duckduckgo.com/",
        # DDG 需要这个 header 才返回 HTML
        "Content-Type": "application/x-www-form-urlencoded",
    }

    async def search(self, keyword: str, max_results: int = 15) -> list[SearchResult]:
        from app.sources.registry import DOMAIN_REGISTRY
        primary = [domains[0] for domains in DOMAIN_REGISTRY.values()]
        site_q  = " OR ".join(f"site:{d}" for d in primary[:6])
        query   = f"{keyword} ({site_q})"
        url     = self._BASE.format(q=quote_plus(query))

        logger.info(f"[DDG] 搜索: {keyword}")
        html = await fetch_html(url, headers=self._HEADERS, retries=2)
        if not html:
            logger.warning("[DDG] 无响应")
            return []

        return self._parse(html, keyword, max_results)

    def _parse(self, html: str, keyword: str, max_results: int) -> list[SearchResult]:
        soup = BeautifulSoup(html, "lxml")
        results: list[SearchResult] = []
        seen: set[str] = set()

        for item in soup.select(".result, .web-result"):
            a = item.select_one(".result__title a, .result__a")
            if not a:
                continue
            href  = a.get("href", "")
            title = a.get_text(strip=True)

            # DDG 的链接有时是重定向，提取真实 URL
            if "duckduckgo.com/l/" in href:
                m = re.search(r"uddg=([^&]+)", href)
                if m:
                    from urllib.parse import unquote
                    href = unquote(m.group(1))

            if not href or href in seen:
                continue
            seen.add(href)

            snippet_tag = item.select_one(".result__snippet")
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

            r = self._make_result(href, title, snippet, keyword)
            if r:
                results.append(r)
                if len(results) >= max_results:
                    break

        logger.info(f"[DDG] 命中 {len(results)} 条")
        return results


# ════════════════════════════════════════════════════════════════════
# 多引擎搜索器（带故障转移 + 结果合并）
# ════════════════════════════════════════════════════════════════════

class MultiEngineSearcher:
    """
    多引擎搜索器
    - 并发查询所有可用引擎
    - 合并去重
    - 按命中次数排序（多个引擎都找到的结果排前面）
    """

    def __init__(self):
        self._engines: list[BaseSearchEngine] = [
            YandexEngine(),
            BingEngine(),
            DuckDuckGoEngine(),
        ]

    async def search(self, keyword: str) -> list[SearchResult]:
        import asyncio
        tasks = [e.search(keyword) for e in self._engines]
        all_lists = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计每个 URL 被多少引擎命中
        url_count: dict[str, int] = {}
        url_result: dict[str, SearchResult] = {}

        for lst in all_lists:
            if isinstance(lst, Exception):
                logger.warning(f"[MultiEngine] 引擎异常: {lst}")
                continue
            for r in lst:
                url_count[r.source_url] = url_count.get(r.source_url, 0) + 1
                # 保留信息最丰富的那条（有简介的优先）
                if r.source_url not in url_result or (
                    len(r.intro) > len(url_result[r.source_url].intro)
                ):
                    url_result[r.source_url] = r

        # 按命中次数降序排列（多引擎共同找到的更可靠）
        sorted_urls = sorted(url_result.keys(),
                             key=lambda u: url_count[u], reverse=True)
        results = [url_result[u] for u in sorted_urls]

        logger.info(f"[MultiEngine] 合并后共 {len(results)} 条结果")
        return results


# 全局单例
multi_engine_searcher = MultiEngineSearcher()
