"""
爬虫基类
定义所有小说爬虫必须实现的抽象接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict


class BaseCrawler(ABC):
    """所有小说网站爬虫的抽象基类"""

    @abstractmethod
    def search(self, keyword: str) -> List[Dict[str, str]]:
        """
        搜索小说
        :param keyword: 搜索关键词（书名或作者名）
        :return: 搜索结果列表，每项包含：
            - title: 书名
            - author: 作者
            - url: 书籍详情页URL
            - latest_chapter: 最新章节标题
        """
        pass

    @abstractmethod
    def get_chapters(self, book_url: str) -> List[Dict[str, str | int]]:
        """
        获取小说的章节列表
        :param book_url: 书籍详情页URL
        :return: 章节列表，每项包含：
            - title: 章节标题
            - url: 章节内容页URL
            - index: 章节序号（从1开始）
        """
        pass

    @abstractmethod
    def get_content(self, chapter_url: str) -> Dict[str, str]:
        """
        获取单个章节的正文内容
        :param chapter_url: 章节内容页URL
        :return: 包含章节标题和正文内容的字典：
            - title: 章节标题
            - content: 章节正文（纯文本格式）
        """
        pass
