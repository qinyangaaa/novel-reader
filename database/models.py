"""
数据库表结构定义
使用 SQLite 存储书籍和章节数据
"""

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    func,
)
from sqlalchemy.orm import declarative_base

# 创建 ORM 基类
Base = declarative_base()


class Book(Base):
    """书籍信息表 - 记录书架上的每一本书"""

    __tablename__ = "books"

    # 主键，自增ID
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 书名
    title = Column(String(255), nullable=False, index=True)

    # 作者
    author = Column(String(255), nullable=False, default="未知")

    # 来源网站的URL（书籍详情页）
    source_url = Column(String(512), nullable=False, unique=True)

    # 封面图片URL（可选）
    cover_url = Column(String(512), nullable=True, default="")

    # 最新章节标题
    latest_chapter = Column(String(255), nullable=True, default="")

    # 最后阅读的章节标题
    last_read_chapter = Column(String(255), nullable=True, default="")

    # 最后阅读的章节索引（从1开始）
    last_read_index = Column(Integer, nullable=True, default=0)

    # 记录创建时间（自动取当前时间）
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<Book(id={self.id}, title='{self.title}', author='{self.author}')>"

    def to_dict(self):
        """将书籍对象转为字典，方便序列化"""
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "source_url": self.source_url,
            "cover_url": self.cover_url or "",
            "latest_chapter": self.latest_chapter or "",
            "last_read_chapter": self.last_read_chapter or "",
            "last_read_index": self.last_read_index or 0,
            "created_at": str(self.created_at) if self.created_at else "",
        }


class Chapter(Base):
    """章节内容表 - 存储每本书的所有章节信息"""

    __tablename__ = "chapters"

    # 主键，自增ID
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 外键：关联到书籍表
    book_id = Column(Integer, nullable=False, index=True)

    # 章节标题
    title = Column(String(255), nullable=False)

    # 章节内容页URL
    url = Column(String(512), nullable=False)

    # 章节正文内容（纯文本格式）
    content = Column(Text, nullable=True, default="")

    # 章节序号（从1开始递增）
    chapter_index = Column(Integer, nullable=False)

    # 是否已下载（0=未下载, 1=已下载）
    is_downloaded = Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<Chapter(id={self.id}, book_id={self.book_id}, index={self.chapter_index}, title='{self.title}')>"

    def to_dict(self):
        """将章节对象转为字典，方便序列化"""
        return {
            "id": self.id,
            "book_id": self.book_id,
            "title": self.title,
            "url": self.url,
            "content": self.content or "",
            "chapter_index": self.chapter_index,
            "is_downloaded": self.is_downloaded,
        }
