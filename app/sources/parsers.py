"""
站点解析器集合 v2
每个解析器负责一种页面结构的书籍详情 + 章节目录 + 正文抓取

设计原则：
  - BiqugeParser 作为"默认/通用"解析器，覆盖大多数仿笔趣阁站
  - 其他解析器继承 BiqugeParser，只重写有差异的方法
  - 工具方法统一放在 BiqugeParser 里复用
"""
import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from app.sources.base import BaseSource, BookInfo, ChapterInfo, SearchResult
from app.services.cleaner import clean_content
from app.utils.http import fetch_html

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════
# 通用基础解析器（笔趣阁族）
# ════════════════════════════════════════════════════════════════════

class BiqugeParser(BaseSource):
    """
    笔趣阁系列通用解析器
    适用于 biquge.com / xbiquge.so / 81zw.com 等同源站
    """
    SOURCE_ID   = "biquge"
    SOURCE_NAME = "笔趣阁"
    BASE_URL    = "https://www.biquge.com"

    # 书籍信息选择器（按优先级）
    SEL_TITLE   = "#info h1, .bookname h1, h1.bookname, .book-info h1"
    SEL_AUTHOR  = "#info p:first-of-type, .bookinfo .author, .info-author, .book-info .author"
    SEL_COVER   = "#fmimg img, .bookimg img, .cover img, .book-cover img"
    SEL_INTRO   = "#intro, .intro, .desc, .book-intro, .synopsis"
    SEL_LIST    = "#list, .listmain, #chapterlist, .chapter-list, .list-chapter"
    # 正文选择器
    SEL_CONTENT = "#content, .content, #booktxt, .read-content, #chapter-content"

    async def search(self, keyword: str) -> list[SearchResult]:
        return []   # 通过搜索引擎聚合，不直接搜索

    async def get_book(self, source_url: str) -> Optional[BookInfo]:
        html = await fetch_html(source_url)
        if not html:
            return None
        soup = BeautifulSoup(html, "lxml")
        base = self._base(source_url)

        title  = self._text(soup, self.SEL_TITLE)
        author = self._extract_author(soup)
        cover  = self._attr(soup, self.SEL_COVER, "src")
        intro  = self._text(soup, self.SEL_INTRO)

        return BookInfo(
            title      = title  or "未知书名",
            author     = author or "未知作者",
            cover      = self._abs(cover, base),
            intro      = intro[:600],
            source     = self.SOURCE_ID,
            source_url = source_url,
        )

    async def get_chapters(self, source_url: str) -> list[ChapterInfo]:
        html = await fetch_html(source_url)
        if not html:
            return []
        soup = BeautifulSoup(html, "lxml")
        base = self._base(source_url)

        list_div = soup.select_one(self.SEL_LIST)
        if not list_div:
            logger.warning(f"[{self.SOURCE_ID}] 未找到章节列表: {source_url}")
            return []

        chapters = []
        for idx, a in enumerate(list_div.select("a")):
            href  = a.get("href", "").strip()
            title = a.get_text(strip=True)
            if not href or not title:
                continue
            # 过滤掉"VIP章节"等付费链接（通常跳到购买页）
            if any(kw in title for kw in ("VIP", "vip", "付费", "购买")):
                continue
            chapters.append(ChapterInfo(
                title       = title,
                chapter_url = self._abs(href, base),
                index       = idx,
            ))

        return chapters

    async def get_content(self, chapter_url: str) -> Optional[str]:
        html = await fetch_html(chapter_url, referer=self._base(chapter_url) + "/")
        if not html:
            return None
        soup = BeautifulSoup(html, "lxml")

        content_div = soup.select_one(self.SEL_CONTENT)
        if not content_div:
            logger.warning(f"[{self.SOURCE_ID}] 未找到正文: {chapter_url}")
            return None

        # 删除正文内的干扰标签
        for tag in content_div.select("script, style, .ad, .ads, [class*='ad']"):
            tag.decompose()

        return clean_content(str(content_div))

    # ── 工具方法（子类可复用）──────────────────────────────────────

    def _text(self, soup: BeautifulSoup | Tag, selector: str) -> str:
        tag = soup.select_one(selector)
        return tag.get_text(strip=True) if tag else ""

    def _attr(self, soup: BeautifulSoup | Tag, selector: str, attr: str) -> str:
        tag = soup.select_one(selector)
        return tag.get(attr, "") if tag else ""

    def _abs(self, url: str, base: str) -> str:
        if not url:
            return ""
        if url.startswith("http"):
            return url
        return urljoin(base, url)

    def _base(self, url: str) -> str:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}"

    def _extract_author(self, soup: BeautifulSoup) -> str:
        """多策略提取作者名"""
        raw = self._text(soup, self.SEL_AUTHOR)
        # 格式 "作者：张三" 或 "作 者:张三"
        m = re.search(r"作\s*者[：:]\s*(.+)", raw)
        if m:
            return m.group(1).strip()[:30]
        # 某些站把作者放在 <a> 标签
        a = soup.select_one(".author a, #info a")
        if a:
            return a.get_text(strip=True)[:30]
        return raw[:30]


# ════════════════════════════════════════════════════════════════════
# 各站点专用解析器
# ════════════════════════════════════════════════════════════════════

class XBiqugeParser(BiqugeParser):
    """新笔趣阁 xbiquge.so 等 - 结构与笔趣阁基本一致"""
    SOURCE_ID   = "xbiquge"
    SOURCE_NAME = "新笔趣阁"
    BASE_URL    = "https://www.xbiquge.so"
    SEL_CONTENT = "#content, .content, #nr1, #BookContent"


class SixtyNineShuParser(BiqugeParser):
    """69书吧 69shu.com"""
    SOURCE_ID   = "69shu"
    SOURCE_NAME = "69书吧"
    BASE_URL    = "https://www.69shu.com"
    SEL_TITLE   = ".booknav2 h1, #info h1, .bookname"
    SEL_AUTHOR  = ".booknav2 p a, #info p:first-of-type"
    SEL_COVER   = ".bookimg2 img, #fmimg img"
    SEL_INTRO   = ".navtxt, #intro"
    SEL_LIST    = ".catalog, #chapterlist, .listmain"
    SEL_CONTENT = ".txtnav, #content, .yd_text2, #BookText"

    async def get_content(self, chapter_url: str) -> Optional[str]:
        html = await fetch_html(chapter_url, referer=self.BASE_URL + "/")
        if not html:
            return None
        soup = BeautifulSoup(html, "lxml")
        div = soup.select_one(self.SEL_CONTENT)
        if not div:
            return None
        # 69shu 喜欢在正文里放章节标题 h1，删掉
        for tag in div.select("h1, h2, .title, p.title"):
            tag.decompose()
        return clean_content(str(div))


class QulaParser(BiqugeParser):
    """趣啦 qu.la"""
    SOURCE_ID   = "qu"
    SOURCE_NAME = "趣啦"
    BASE_URL    = "https://www.qu.la"
    SEL_CONTENT = "#content, .content, .read-content, #chaptercontent"


class DingdianParser(BiqugeParser):
    """顶点小说 ddxs.com / 23us.com 系列"""
    SOURCE_ID   = "dingdian"
    SOURCE_NAME = "顶点小说"
    BASE_URL    = "https://www.ddxs.com"
    SEL_TITLE   = ".bookinfo h1, #info h1, h1"
    SEL_AUTHOR  = ".bookinfo .author, #info p:first-of-type"
    SEL_COVER   = ".bookinfo .cover img, #fmimg img"
    SEL_INTRO   = ".bookinfo .intro, #intro"
    SEL_LIST    = "#list, .chapter-list, .chapterlist"
    SEL_CONTENT = "#content, .content, #chaptercontent"

    async def get_chapters(self, source_url: str) -> list[ChapterInfo]:
        """顶点有时把目录放在单独的 /chapters/ 页"""
        chapters = await super().get_chapters(source_url)
        if chapters:
            return chapters
        # 尝试 /chapters/ 子页
        alt_url = source_url.rstrip("/") + "/chapters/"
        html = await fetch_html(alt_url)
        if not html:
            return []
        soup = BeautifulSoup(html, "lxml")
        base = self._base(source_url)
        result = []
        for idx, a in enumerate(soup.select(".chapter-list a, #chapterlist a")):
            href  = a.get("href", "").strip()
            title = a.get_text(strip=True)
            if href and title:
                result.append(ChapterInfo(
                    title=title, chapter_url=self._abs(href, base), index=idx
                ))
        return result


class PiaotianParser(BiqugeParser):
    """飘天文学 ptwxz.com"""
    SOURCE_ID   = "piaotian"
    SOURCE_NAME = "飘天文学"
    BASE_URL    = "https://www.ptwxz.com"
    # 飘天正文用 GBK，需强制指定编码
    SEL_CONTENT = "#content, .content, #booktext"

    async def get_content(self, chapter_url: str) -> Optional[str]:
        html = await fetch_html(chapter_url, encoding="gbk")
        if not html:
            return None
        soup = BeautifulSoup(html, "lxml")
        div = soup.select_one(self.SEL_CONTENT)
        if not div:
            return None
        return clean_content(str(div))

    async def get_book(self, source_url: str) -> Optional[BookInfo]:
        html = await fetch_html(source_url, encoding="gbk")
        if not html:
            return None
        soup = BeautifulSoup(html, "lxml")
        base = self._base(source_url)
        title  = self._text(soup, "h1, .bookname")
        author = self._extract_author(soup)
        cover  = self._attr(soup, "img.cover, #fmimg img", "src")
        intro  = self._text(soup, "#intro, .intro")
        return BookInfo(
            title=title or "未知书名", author=author or "未知作者",
            cover=self._abs(cover, base), intro=intro[:600],
            source=self.SOURCE_ID, source_url=source_url,
        )


class ShuquParser(BiqugeParser):
    """书趣阁 shuqu.net"""
    SOURCE_ID   = "shuqu"
    SOURCE_NAME = "书趣阁"
    BASE_URL    = "https://www.shuqu.net"
    SEL_CONTENT = "#content, .content, .book-content"


class EightOneZwParser(BiqugeParser):
    """81中文 81zw.com"""
    SOURCE_ID   = "81zw"
    SOURCE_NAME = "81中文"
    BASE_URL    = "https://www.81zw.com"
    SEL_LIST    = "#list, .listmain, .chapters"
    SEL_CONTENT = "#content, .content"


class BixiaParser(BiqugeParser):
    """笔下文学 bxwx.net"""
    SOURCE_ID   = "bixia"
    SOURCE_NAME = "笔下文学"
    BASE_URL    = "https://www.bxwx.net"
    SEL_CONTENT = "#content, .content, #chapterContent"

    async def get_content(self, chapter_url: str) -> Optional[str]:
        """笔下部分站用 GBK"""
        html = await fetch_html(chapter_url, encoding="gbk")
        if not html:
            # 回退 UTF-8
            html = await fetch_html(chapter_url)
        if not html:
            return None
        soup = BeautifulSoup(html, "lxml")
        div  = soup.select_one(self.SEL_CONTENT)
        return clean_content(str(div)) if div else None


class Xs18Parser(BiqugeParser):
    """小说18 xs18.net"""
    SOURCE_ID   = "xs18"
    SOURCE_NAME = "小说18"
    BASE_URL    = "https://www.xs18.net"
    SEL_CONTENT = "#content, .content, .chapter-content"


# ── 解析器注册表：parser_id → 解析器类 ────────────────────────────
PARSER_REGISTRY: dict[str, type[BiqugeParser]] = {
    "biquge":   BiqugeParser,
    "xbiquge":  XBiqugeParser,
    "69shu":    SixtyNineShuParser,
    "qu":       QulaParser,
    "dingdian": DingdianParser,
    "piaotian": PiaotianParser,
    "shuqu":    ShuquParser,
    "81zw":     EightOneZwParser,
    "bixia":    BixiaParser,
    "xs18":     Xs18Parser,
}


def get_parser(parser_id: str) -> Optional[BiqugeParser]:
    """根据 parser_id 返回对应解析器实例"""
    cls = PARSER_REGISTRY.get(parser_id)
    return cls() if cls else None


def get_parser_by_url(url: str) -> Optional[BiqugeParser]:
    """根据 URL 自动选择解析器"""
    from app.sources.registry import detect_parser_id
    pid = detect_parser_id(url)
    return get_parser(pid) if pid else None
