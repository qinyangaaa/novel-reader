"""
小说源基类
每个小说源都必须继承这个类并实现所有方法
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class BookInfo:
    """小说基本信息"""
    title: str
    author: str
    cover: str
    intro: str
    source: str        # 来源标识，如 "biquge"
    source_url: str    # 小说在源站的URL


@dataclass
class ChapterInfo:
    """章节信息"""
    title: str
    chapter_url: str
    index: int = 0     # 章节序号，用于排序


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    author: str
    cover: str
    intro: str
    source: str
    source_url: str


class BaseSource(ABC):
    """
    小说源基类
    所有小说源必须继承此类
    """

    # 源的唯一标识符，子类必须定义
    SOURCE_ID: str = ""
    # 源的显示名称
    SOURCE_NAME: str = ""
    # 源的基础URL
    BASE_URL: str = ""

    # 公共请求头，伪装成手机浏览器
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    # 请求超时（秒）
    TIMEOUT = 15

    # 重试次数
    MAX_RETRIES = 3

    @abstractmethod
    async def search(self, keyword: str) -> list[SearchResult]:
        """
        搜索小说
        :param keyword: 搜索关键词
        :return: 搜索结果列表
        """
        pass

    @abstractmethod
    async def get_book(self, source_url: str) -> Optional[BookInfo]:
        """
        获取小说详情
        :param source_url: 小说在源站的URL
        :return: 小说信息
        """
        pass

    @abstractmethod
    async def get_chapters(self, source_url: str) -> list[ChapterInfo]:
        """
        获取章节目录
        :param source_url: 小说在源站的URL
        :return: 章节列表（按顺序）
        """
        pass

    @abstractmethod
    async def get_content(self, chapter_url: str) -> Optional[str]:
        """
        获取章节正文
        :param chapter_url: 章节URL
        :return: 清洗后的正文文本
        """
        pass
