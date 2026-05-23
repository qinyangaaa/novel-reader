"""
笔趣阁（www.biquge.com.tw）爬虫适配器
继承 BaseCrawler，实现搜索、获取章节列表、获取正文三大功能
"""

import re
import time
import requests
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from .base_crawler import BaseCrawler


class BiqugeCrawler(BaseCrawler):
    """笔趣阁网站爬虫"""

    # 目标网站的基础URL
    BASE_URL = "https://www.shuzhaige.com/"

    # 模拟浏览器的请求头，防止被网站拦截
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.shuzhaige.com/",
        "Connection": "keep-alive",
    }

    # 最大重试次数
    MAX_RETRIES = 3

    # 两次请求之间的最小间隔（秒），避免请求过快被封IP
    REQUEST_INTERVAL = 1

    def __init__(self):
        """初始化爬虫，创建会话对象以复用连接"""
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._last_request_time = 0  # 记录上次请求时间，用于限速

    def _request_with_retry(self, url: str) -> Optional[requests.Response]:
        """
        带重试机制的HTTP请求
        :param url: 请求的目标URL
        :return: Response对象，如果所有重试都失败则返回None
        """
        # 限速：确保两次请求之间至少有 REQUEST_INTERVAL 秒的间隔
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_INTERVAL:
            time.sleep(self.REQUEST_INTERVAL - elapsed)

        last_exception = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                print(f"[爬虫] 正在请求: {url} (第{attempt}次尝试)")
                response = self.session.get(url, timeout=15)
                response.encoding = "utf-8"  # 强制使用UTF-8编码，避免乱码
                response.raise_for_status()  # 检查HTTP状态码
                self._last_request_time = time.time()
                return response
            except requests.exceptions.RequestException as e:
                last_exception = e
                print(f"[爬虫] 请求失败 (第{attempt}次): {e}")
                if attempt < self.MAX_RETRIES:
                    # 指数退避：每次重试等待时间递增
                    wait_time = 2 ** attempt
                    print(f"[爬虫] 等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)

        print(f"[爬虫] 请求最终失败: {url}，错误: {last_exception}")
        return None

    def _parse_book_id_from_url(self, url: str) -> Optional[str]:
        """
        从书籍URL中提取书籍ID
        例如: https://www.biquge.com.tw/0_123/ → 提取 "0_123"
        """
        match = re.search(r'/(\d+_\d+)/?$', url)
        if match:
            return match.group(1)
        return None

    def search(self, keyword: str) -> List[Dict[str, str]]:
        """
        搜索小说（笔趣阁的搜索功能）
        :param keyword: 搜索关键词
        :return: 搜索结果列表
        """
        search_url = f"{self.BASE_URL}/modules/article/search.php"
        # 笔趣阁搜索使用POST请求，表单格式
        data = {"searchkey": keyword, "submit": "搜索"}
        headers = self.HEADERS.copy()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        try:
            response = self.session.post(search_url, data=data, timeout=15, headers=headers)
            response.encoding = "utf-8"
            self._last_request_time = time.time()
        except Exception as e:
            print(f"[爬虫] 搜索请求失败: {e}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        # 搜索结果通常在 <table> 或结果列表中
        # 尝试解析常见的小说搜索结果格式
        book_links = soup.select("a[href*='_']")

        for link in book_links:
            href = link.get("href", "")
            # 过滤出符合书籍URL格式的链接（含有数字_数字的路径）
            if re.search(r'/\d+_\d+/', href):
                # 获取完整的书籍URL
                if href.startswith("/"):
                    book_url = self.BASE_URL + href
                elif href.startswith("http"):
                    book_url = href
                else:
                    book_url = self.BASE_URL + "/" + href

                title = link.get_text().strip()

                # 尝试获取作者和最新章节信息（通常在相邻的td或span中）
                parent = link.parent
                author = ""
                latest_chapter = ""

                # 尝试从父元素中提取作者信息
                author_tag = parent.find_next("td", class_="author")
                if not author_tag:
                    author_tag = parent.find_next("span", class_="author")
                if author_tag:
                    author = author_tag.get_text().strip()

                # 尝试提取最新章节
                latest_tag = parent.find_next("td", class_="latest")
                if not latest_tag:
                    latest_tag = parent.find_next("span", class_="latest")
                if latest_tag:
                    latest_chapter = latest_tag.get_text().strip()

                if title and book_url:
                    results.append({
                        "title": title,
                        "author": author or "未知",
                        "url": book_url,
                        "latest_chapter": latest_chapter or "未知",
                    })

        # 如果搜索结果为空，尝试另一种解析方式（笔趣阁的不同版本）
        if not results:
            print("[爬虫] 搜索结果为空，尝试备用解析方式...")
            rows = soup.select("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    link_tag = cells[0].find("a")
                    if link_tag:
                        href = link_tag.get("href", "")
                        title = link_tag.get_text().strip()
                        if href and title:
                            book_url = self.BASE_URL + href if href.startswith("/") else href
                            author = cells[1].get_text().strip() if len(cells) > 1 else "未知"
                            latest_chapter = cells[2].get_text().strip() if len(cells) > 2 else "未知"
                            results.append({
                                "title": title,
                                "author": author,
                                "url": book_url,
                                "latest_chapter": latest_chapter,
                            })

        print(f"[爬虫] 搜索 \"{keyword}\" 找到 {len(results)} 个结果")
        return results

    def get_chapters(self, book_url: str) -> List[Dict[str, str | int]]:
        """
        获取小说章节列表
        :param book_url: 书籍详情页URL
        :return: 章节列表，按章节序号排序
        """
        response = self._request_with_retry(book_url)
        if not response:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        chapters = []

        # 笔趣阁的章节列表通常在 <dd> 标签中，或者 <ul class="chapter"> 中
        chapter_tags = soup.select("dd a")

        # 如果没找到，尝试其他选择器
        if not chapter_tags:
            chapter_tags = soup.select("ul.chapter li a")
        if not chapter_tags:
            chapter_tags = soup.select("#list a")
        if not chapter_tags:
            chapter_tags = soup.select(".chapter-list a")
        if not chapter_tags:
            chapter_tags = soup.select(".content a[href*='.html']")

        for idx, tag in enumerate(chapter_tags, start=1):
            href = tag.get("href", "")
            title = tag.get_text().strip()

            # 跳过空链接和无效章节
            if not title or not href:
                continue

            # 过滤掉非章节的链接（如"简介"、"目录"等）
            if any(skip in title for skip in ["简介", "目录", "首页", "下一页", "上一页"]):
                continue

            # 构造完整的章节URL
            if href.startswith("http"):
                chapter_url = href
            elif href.startswith("/"):
                chapter_url = self.BASE_URL + href
            else:
                # 相对路径：基于书籍URL拼接
                base = book_url.rstrip("/")
                chapter_url = base + "/" + href.lstrip("/")

            chapters.append({
                "title": title,
                "url": chapter_url,
                "index": idx,
            })

        print(f"[爬虫] 获取到章节列表: {len(chapters)} 章")
        return chapters

    def get_content(self, chapter_url: str) -> Dict[str, str]:
        """
        获取章节正文内容
        :param chapter_url: 章节内容页URL
        :return: 包含标题和正文的字典
        """
        response = self._request_with_retry(chapter_url)
        if not response:
            return {"title": "获取失败", "content": ""}

        soup = BeautifulSoup(response.text, "html.parser")

        # 提取章节标题
        title = ""
        title_tag = soup.find("h1")
        if title_tag:
            title = title_tag.get_text().strip()
        if not title:
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text().strip()

        # 提取正文内容 - 常见容器选择器
        content_div = (
            soup.find("div", id="content")
            or soup.find("div", class_="content")
            or soup.find("div", id="chaptercontent")
            or soup.find("div", id="booktxt")
            or soup.find("div", class_="chapter-content")
        )

        content_text = ""
        if content_div:
            # 获取HTML内容后用正则提取纯文本，保留段落格式
            content_html = str(content_div)
            # 移除HTML标签并保留换行
            content_text = re.sub(r'<br\s*/?>', '\n', content_html)
            content_text = re.sub(r'<[^>]+>', '', content_text)
            content_text = re.sub(r'&nbsp;', ' ', content_text)
            content_text = re.sub(r'&lt;', '<', content_text)
            content_text = re.sub(r'&gt;', '>', content_text)
            content_text = re.sub(r'&amp;', '&', content_text)
            # 清理多余空行
            content_text = re.sub(r'\n{3,}', '\n\n', content_text)
            content_text = content_text.strip()
        else:
            # 备用方案：提取所有文本内容
            print(f"[爬虫] 未找到正文容器，尝试提取所有文本...")
            content_text = soup.get_text(separator="\n", strip=True)

        # 清理章节标题中的站点标识
        title = re.sub(r'[_\-—].*$', '', title).strip()

        print(f"[爬虫] 获取章节: {title} ({len(content_text)} 字符)")
        return {
            "title": title,
            "content": content_text,
        }
