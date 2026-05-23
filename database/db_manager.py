"""
数据库管理器
封装书籍和章节的常用增删改查操作
"""

import os
from typing import List, Optional, Dict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models import Base, Book, Chapter


class DatabaseManager:
    """数据库管理器，提供对书籍和章节的CRUD操作"""

    def __init__(self, db_path: str = None):
        """
        初始化数据库连接
        :param db_path: 数据库文件路径，默认为项目根目录下的 novels.db
        """
        if db_path is None:
            # 默认数据库文件存放在项目根目录的 data 文件夹中
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "novels.db")

        # 创建数据库引擎，SQLite 连接
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        # 创建所有表（如果不存在）
        Base.metadata.create_all(self.engine)
        # 创建会话工厂
        self.Session = sessionmaker(bind=self.engine)

        print(f"[数据库] 初始化完成，数据库路径: {db_path}")

    def _get_session(self) -> Session:
        """获取一个新的数据库会话"""
        return self.Session()

    # ==================== 书籍操作 ====================

    def add_book(self, book_info: Dict) -> Optional[Book]:
        """
        添加一本书到书架
        如果同一 source_url 的书已存在，则跳过（不重复添加）
        :param book_info: 书籍信息字典，包含：
            - title: 书名
            - author: 作者
            - source_url: 来源URL
            - cover_url: 封面URL（可选）
            - latest_chapter: 最新章节（可选）
        :return: 新增的 Book 对象，如果已存在则返回现有的
        """
        session = self._get_session()
        try:
            # 检查是否已存在（根据 source_url 去重）
            existing = (
                session.query(Book)
                .filter(Book.source_url == book_info.get("source_url"))
                .first()
            )
            if existing:
                print(f"[数据库] 书籍已存在，跳过添加: {existing.title}")
                return existing

            # 创建新书籍记录
            book = Book(
                title=book_info.get("title", "").strip(),
                author=book_info.get("author", "未知").strip(),
                source_url=book_info.get("source_url", "").strip(),
                cover_url=book_info.get("cover_url", "").strip(),
                latest_chapter=book_info.get("latest_chapter", "").strip(),
            )
            session.add(book)
            session.commit()
            print(f"[数据库] 添加书籍成功: {book.title}")
            return book
        except Exception as e:
            session.rollback()
            print(f"[数据库] 添加书籍失败: {e}")
            return None
        finally:
            session.close()

    def get_all_books(self) -> List[Book]:
        """
        获取书架上的所有书籍
        :return: 书籍对象列表，按创建时间倒序排列
        """
        session = self._get_session()
        try:
            books = (
                session.query(Book)
                .order_by(Book.created_at.desc())
                .all()
            )
            return books
        except Exception as e:
            print(f"[数据库] 获取书籍列表失败: {e}")
            return []
        finally:
            session.close()

    def get_book_by_id(self, book_id: int) -> Optional[Book]:
        """
        根据书籍ID获取书籍信息
        :param book_id: 书籍ID
        :return: Book 对象，不存在则返回 None
        """
        session = self._get_session()
        try:
            book = session.query(Book).filter(Book.id == book_id).first()
            return book
        except Exception as e:
            print(f"[数据库] 获取书籍失败: {e}")
            return None
        finally:
            session.close()

    def get_book_by_url(self, source_url: str) -> Optional[Book]:
        """
        根据来源URL获取书籍信息
        :param source_url: 书籍详情页URL
        :return: Book 对象，不存在则返回 None
        """
        session = self._get_session()
        try:
            book = (
                session.query(Book)
                .filter(Book.source_url == source_url)
                .first()
            )
            return book
        except Exception as e:
            print(f"[数据库] 获取书籍失败: {e}")
            return None
        finally:
            session.close()

    def delete_book(self, book_id: int) -> bool:
        """
        删除一本书及其所有章节
        :param book_id: 书籍ID
        :return: 是否删除成功
        """
        session = self._get_session()
        try:
            # 先删除所有关联的章节
            session.query(Chapter).filter(Chapter.book_id == book_id).delete()
            # 再删除书籍
            book = session.query(Book).filter(Book.id == book_id).first()
            if book:
                session.delete(book)
                session.commit()
                print(f"[数据库] 删除书籍成功: {book.title}")
                return True
            else:
                print(f"[数据库] 书籍不存在，ID: {book_id}")
                return False
        except Exception as e:
            session.rollback()
            print(f"[数据库] 删除书籍失败: {e}")
            return False
        finally:
            session.close()

    def update_book_latest(self, book_id: int, latest_chapter: str) -> bool:
        """
        更新书籍的最新章节信息
        :param book_id: 书籍ID
        :param latest_chapter: 最新章节标题
        :return: 是否更新成功
        """
        session = self._get_session()
        try:
            book = session.query(Book).filter(Book.id == book_id).first()
            if book:
                book.latest_chapter = latest_chapter
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            print(f"[数据库] 更新最新章节失败: {e}")
            return False
        finally:
            session.close()

    # ==================== 章节操作 ====================

    def save_chapter(self, chapter_info: Dict) -> Optional[Chapter]:
        """
        保存章节内容
        如果同一本书的同一章节索引已存在，则更新内容
        :param chapter_info: 章节信息字典，包含：
            - book_id: 所属书籍ID
            - title: 章节标题
            - url: 章节URL
            - content: 正文内容
            - chapter_index: 章节序号
        :return: 保存后的 Chapter 对象
        """
        session = self._get_session()
        try:
            # 检查是否已存在同书的同索引章节
            existing = (
                session.query(Chapter)
                .filter(
                    Chapter.book_id == chapter_info.get("book_id"),
                    Chapter.chapter_index == chapter_info.get("chapter_index"),
                )
                .first()
            )

            if existing:
                # 更新已有章节
                existing.title = chapter_info.get("title", existing.title)
                existing.content = chapter_info.get("content", existing.content)
                existing.url = chapter_info.get("url", existing.url)
                existing.is_downloaded = 1
                session.commit()
                print(f"[数据库] 更新章节: {existing.title}")
                return existing
            else:
                # 新建章节
                chapter = Chapter(
                    book_id=chapter_info.get("book_id"),
                    title=chapter_info.get("title", ""),
                    url=chapter_info.get("url", ""),
                    content=chapter_info.get("content", ""),
                    chapter_index=chapter_info.get("chapter_index", 0),
                    is_downloaded=1,
                )
                session.add(chapter)
                session.commit()
                print(f"[数据库] 保存章节: {chapter.title}")
                return chapter
        except Exception as e:
            session.rollback()
            print(f"[数据库] 保存章节失败: {e}")
            return None
        finally:
            session.close()

    def get_chapter(self, book_id: int, index: int) -> Optional[Chapter]:
        """
        获取某本书的指定章节
        :param book_id: 书籍ID
        :param index: 章节序号（从1开始）
        :return: Chapter 对象，不存在则返回 None
        """
        session = self._get_session()
        try:
            chapter = (
                session.query(Chapter)
                .filter(
                    Chapter.book_id == book_id,
                    Chapter.chapter_index == index,
                )
                .first()
            )
            return chapter
        except Exception as e:
            print(f"[数据库] 获取章节失败: {e}")
            return None
        finally:
            session.close()

    def get_chapters_by_book(self, book_id: int) -> List[Chapter]:
        """
        获取一本书的所有章节列表
        :param book_id: 书籍ID
        :return: 章节对象列表，按章节序号升序排列
        """
        session = self._get_session()
        try:
            chapters = (
                session.query(Chapter)
                .filter(Chapter.book_id == book_id)
                .order_by(Chapter.chapter_index.asc())
                .all()
            )
            return chapters
        except Exception as e:
            print(f"[数据库] 获取章节列表失败: {e}")
            return []
        finally:
            session.close()

    def get_downloaded_chapters(self, book_id: int) -> List[Chapter]:
        """
        获取一本书中已下载的章节列表
        :param book_id: 书籍ID
        :return: 已下载的章节列表
        """
        session = self._get_session()
        try:
            chapters = (
                session.query(Chapter)
                .filter(
                    Chapter.book_id == book_id,
                    Chapter.is_downloaded == 1,
                )
                .order_by(Chapter.chapter_index.asc())
                .all()
            )
            return chapters
        except Exception as e:
            print(f"[数据库] 获取已下载章节失败: {e}")
            return []
        finally:
            session.close()

    # ==================== 阅读进度操作 ====================

    def update_last_read(self, book_id: int, chapter_index: int) -> bool:
        """
        更新阅读进度（记录读到了哪一章）
        :param book_id: 书籍ID
        :param chapter_index: 当前阅读的章节序号
        :return: 是否更新成功
        """
        session = self._get_session()
        try:
            book = session.query(Book).filter(Book.id == book_id).first()
            if not book:
                print(f"[数据库] 书籍不存在，ID: {book_id}")
                return False

            # 获取该章节的标题
            chapter = (
                session.query(Chapter)
                .filter(
                    Chapter.book_id == book_id,
                    Chapter.chapter_index == chapter_index,
                )
                .first()
            )

            book.last_read_index = chapter_index
            if chapter:
                book.last_read_chapter = chapter.title

            session.commit()
            chapter_title = chapter.title if chapter else f"第{chapter_index}章"
            print(f"[数据库] 更新阅读进度: {book.title} → {chapter_title}")
            return True
        except Exception as e:
            session.rollback()
            print(f"[数据库] 更新阅读进度失败: {e}")
            return False
        finally:
            session.close()

    def get_last_read(self, book_id: int) -> Optional[Dict]:
        """
        获取某本书的阅读进度
        :param book_id: 书籍ID
        :return: {"chapter_index": int, "chapter_title": str} 或 None
        """
        session = self._get_session()
        try:
            book = session.query(Book).filter(Book.id == book_id).first()
            if not book:
                return None
            return {
                "chapter_index": book.last_read_index or 0,
                "chapter_title": book.last_read_chapter or "",
            }
        except Exception as e:
            print(f"[数据库] 获取阅读进度失败: {e}")
            return None
        finally:
            session.close()

    # ==================== 批量操作 ====================

    def save_chapters_batch(self, chapters: List[Dict]) -> int:
        """
        批量保存章节（提高效率）
        :param chapters: 章节信息字典列表
        :return: 成功保存的章节数
        """
        success_count = 0
        for ch in chapters:
            result = self.save_chapter(ch)
            if result:
                success_count += 1
        print(f"[数据库] 批量保存完成: {success_count}/{len(chapters)}")
        return success_count

    def get_total_chapters(self, book_id: int) -> int:
        """
        获取一本书的总章节数
        :param book_id: 书籍ID
        :return: 章节总数
        """
        session = self._get_session()
        try:
            count = (
                session.query(Chapter)
                .filter(Chapter.book_id == book_id)
                .count()
            )
            return count
        except Exception as e:
            print(f"[数据库] 获取章节总数失败: {e}")
            return 0
        finally:
            session.close()
