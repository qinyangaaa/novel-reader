"""
小说爬虫 Kivy 版 - 全部用 Python 构建 UI
"""
import sys
import os
import threading

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.lang import Builder
from kivy.core.text import LabelBase
from kivy.clock import Clock
from kivy.properties import StringProperty, NumericProperty, ListProperty, ObjectProperty
from kivy.utils import platform
from kivy.graphics import Color, Rectangle

# ---------- 全局字体 ----------
def setup_font():
    paths = []
    if platform == 'win':
        paths = [('C:/Windows/Fonts/msyh.ttc', 'YaHei')]
    elif platform == 'android':
        paths = [('/system/fonts/NotoSansSC-Regular.otf', 'NotoSansSC')]
    for p, n in paths:
        if os.path.exists(p):
            try:
                LabelBase.register(name='cn', fn_regular=p)
                return True
            except:
                pass
    return False

setup_font()

# ---------- KV ----------
kv_dir = os.path.join(os.path.dirname(__file__), 'kv')
fp = os.path.join(kv_dir, 'font_fix.kv')
if os.path.exists(fp):
    Builder.load_file(fp)

from crawlers.shuzhaige_crawler import ShuzhaigeCrawler
from database.db_manager import DatabaseManager


# ---------- 数据层 ----------
class BookShelf:
    def __init__(self):
        self.crawler = ShuzhaigeCrawler()
        self.db = DatabaseManager()

    def _run(self, func, cb, *args, **kw):
        def task():
            try:
                r = func(*args, **kw)
                Clock.schedule_once(lambda dt: cb(r, None))
            except Exception as e:
                Clock.schedule_once(lambda dt: cb(None, str(e)))
        threading.Thread(target=task, daemon=True).start()

    def search(self, kw, cb): self._run(self.crawler.search, cb, kw)
    def get_books(self, cb): self._run(self.db.get_all_books, cb)
    def get_chapters(self, url, cb): self._run(self.crawler.get_chapters, cb, url)
    def get_content(self, url, cb): self._run(self.crawler.get_content, cb, url)

    def add_to_shelf(self, info, cb):
        def add():
            d = {"title": info["title"], "author": info["author"],
                 "source_url": info["url"], "cover_url": "", "latest_chapter": ""}
            return self.db.add_book(d)
        self._run(add, cb)

    def save_chapter(self, info):
        def do(): self.db.save_chapter(info)
        threading.Thread(target=do, daemon=True).start()

    def update_last_read(self, bid, idx):
        def do(): self.db.update_last_read(bid, idx)
        threading.Thread(target=do, daemon=True).start()


# ---------- 通用组件 ----------
CN = 'cn'  # 字体名

def bar_label(text, size_x=0.7, **kw):
    """顶栏标题"""
    return Label(text=text, font_size='20sp', color=(1,1,1,1),
                size_hint_x=size_x, halign='left', valign='middle', font_name=CN, **kw)

def top_bar(text, btn_text, btn_callback, btn_size=0.2):
    """创建顶栏"""
    bar = BoxLayout(size_hint_y=None, height='56dp',
                    padding=['12dp','8dp'], spacing='8dp')
    with bar.canvas.before:
        Color(0.2, 0.6, 0.8, 1)
        Rectangle(pos=bar.pos, size=bar.size)
    bar.bind(pos=lambda s, v: setattr(s.canvas.before.children[-1], 'pos', v))
    bar.bind(size=lambda s, v: setattr(s.canvas.before.children[-1], 'size', v))

    lbl = bar_label(text)
    bar.add_widget(lbl)

    btn = Button(text=btn_text, size_hint_x=btn_size,
                background_color=(1,1,1,0.2), color=(1,1,1,1), font_name=CN)
    btn.bind(on_press=lambda x: btn_callback())
    bar.add_widget(btn)
    return bar

def white_card(children, height='64dp'):
    """白色卡片"""
    card = BoxLayout(orientation='horizontal',
                    size_hint_y=None, height=height,
                    padding=['12dp','6dp'], spacing='8dp')
    with card.canvas.before:
        Color(1, 1, 1, 1)
        Rectangle(pos=card.pos, size=card.size)
    card.bind(pos=lambda s,v: setattr(s.canvas.before.children[-1], 'pos', v))
    card.bind(size=lambda s,v: setattr(s.canvas.before.children[-1], 'size', v))
    for c in children:
        card.add_widget(c)
    return card

def info_column(title, subtitle, title_size='17sp'):
    """信息列"""
    col = BoxLayout(orientation='vertical', spacing='2dp')
    tl = Label(text=title, font_size=title_size, bold=True,
              color=(0.1,0.1,0.1,1), size_hint_y=0.6,
              halign='left', valign='middle', font_name=CN)
    tl.bind(size=lambda s,w: setattr(s, 'text_size', w))
    sl = Label(text=subtitle, font_size='13sp',
              color=(0.5,0.5,0.5,1), size_hint_y=0.4,
              halign='left', valign='middle', font_name=CN)
    sl.bind(size=lambda s,w: setattr(s, 'text_size', w))
    col.add_widget(tl)
    col.add_widget(sl)
    return col

def scroll_grid(**kw):
    """可滚动的网格"""
    sv = ScrollView(do_scroll_x=False)
    gl = GridLayout(cols=1, spacing='2dp',
                   size_hint_y=None, padding=['8dp',0], **kw)
    gl.bind(minimum_height=gl.setter('height'))
    sv.add_widget(gl)
    return sv, gl

def status_label(text=''):
    """状态条"""
    return Label(text=text, font_size='14sp', color=(0.6,0.6,0.6,1),
                size_hint_y=None, height='36dp',
                halign='center', valign='middle', font_name=CN)


# ---------- Screen - 书架 ----------
class BookcaseScreen(Screen):
    books = ListProperty([])

    def __init__(self, **kw):
        super().__init__(**kw)
        self._loaded = False
        self._build_ui()

    def _build_ui(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical')

        root.add_widget(top_bar('我的书架', '搜索', self._go_search))

        self._status = status_label('加载中...')
        root.add_widget(self._status)

        sv, self._grid = scroll_grid()
        root.add_widget(sv)

        self.add_widget(root)

    def on_enter(self):
        if self._loaded:
            return
        self._loaded = True
        self._status.text = '加载中...'
        app = App.get_running_app()
        app.shelf.get_books(self._on_books)

    def _on_books(self, books, error=None):
        self._grid.clear_widgets()
        if error:
            self._status.text = '加载失败'
            return
        if not books:
            self._status.text = '书架是空的，去搜索添加小说吧'
            return
        self._status.text = ''
        for b in books:
            self._add_book(b)

    def _add_book(self, book):
        col = info_column(book.title, book.author)
        btn = Button(text='阅读', size_hint_x=0.2,
                    background_color=(0.2,0.6,0.8,1),
                    color=(1,1,1,1), font_name=CN)
        btn.bind(on_press=lambda x, b=book: self._open(b))
        card = white_card([col, btn], height='72dp')
        self._grid.add_widget(card)

    def _open(self, book):
        app = App.get_running_app()
        app.current_book = book
        app.current_book_id = book.id
        ch = self.manager.get_screen('chapters')
        ch.load_chapters(book.source_url)
        self.manager.current = 'chapters'

    def _go_search(self):
        self.manager.current = 'search'


# ---------- Screen - 搜索 ----------
class SearchScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._build_ui()

    def _build_ui(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical')

        # 顶栏
        bar = BoxLayout(size_hint_y=None, height='56dp',
                       padding=['8dp','8dp'], spacing='8dp')
        with bar.canvas.before:
            Color(0.2, 0.6, 0.8, 1)
            Rectangle(pos=bar.pos, size=bar.size)
        bar.bind(pos=lambda s,v: setattr(s.canvas.before.children[-1], 'pos', v))
        bar.bind(size=lambda s,v: setattr(s.canvas.before.children[-1], 'size', v))

        back_btn = Button(text='<', size_hint_x=0.12,
                         background_color=(1,1,1,0.2), color=(1,1,1,1),
                         font_size='20sp', font_name=CN)
        back_btn.bind(on_press=lambda x: self._go_back())
        bar.add_widget(back_btn)

        self._input = TextInput(size_hint_x=0.6, hint_text='书名',
                               multiline=False, font_size='16sp', font_name=CN)
        self._input.bind(on_text_validate=lambda x: self._do_search())
        bar.add_widget(self._input)

        search_btn = Button(text='搜索', size_hint_x=0.28,
                           background_color=(1,1,1,0.2), color=(1,1,1,1),
                           font_name=CN)
        search_btn.bind(on_press=lambda x: self._do_search())
        bar.add_widget(search_btn)
        root.add_widget(bar)

        self._status = status_label('')
        root.add_widget(self._status)

        sv, self._grid = scroll_grid()
        root.add_widget(sv)

        self.add_widget(root)

    def _do_search(self):
        kw = self._input.text.strip()
        if not kw:
            return
        self._grid.clear_widgets()
        self._status.text = '搜索中...'
        app = App.get_running_app()
        app.shelf.search(kw, self._on_result)

    def _on_result(self, data, error=None):
        self._grid.clear_widgets()
        if error:
            self._status.text = '搜索失败'
            return
        if not data:
            self._status.text = '未找到相关小说'
            return
        self._status.text = ''
        for b in data:
            self._add_result(b)

    def _add_result(self, book):
        col = info_column(book['title'], book['author'])
        btn = Button(text='+添加', size_hint_x=0.2,
                    background_color=(0.2,0.8,0.2,1),
                    color=(1,1,1,1), font_name=CN)
        btn.bind(on_press=lambda x, b=book: self._add(b))
        card = white_card([col, btn], height='64dp')
        self._grid.add_widget(card)

    def _add(self, book_info):
        self._status.text = '添加中...'
        app = App.get_running_app()
        app.shelf.add_to_shelf(book_info, lambda r,e=None: self._on_added(r, e))

    def _on_added(self, result, error=None):
        if result:
            self._status.text = '已添加到书架'
        else:
            self._status.text = error or '已在书架中'

    def _go_back(self):
        self.manager.current = 'bookcase'


# ---------- Screen - 章节 ----------
class ChaptersScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._build_ui()

    def _build_ui(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical')

        bar = BoxLayout(size_hint_y=None, height='56dp',
                       padding=['12dp','8dp'], spacing='8dp')
        with bar.canvas.before:
            Color(0.6, 0.6, 0.6, 1)
            Rectangle(pos=bar.pos, size=bar.size)
        bar.bind(pos=lambda s,v: setattr(s.canvas.before.children[-1], 'pos', v))
        bar.bind(size=lambda s,v: setattr(s.canvas.before.children[-1], 'size', v))

        back_btn = Button(text='< 返回', size_hint_x=0.2,
                         background_color=(1,1,1,0.2), color=(1,1,1,1), font_name=CN)
        back_btn.bind(on_press=lambda x: self._go_back())
        bar.add_widget(back_btn)

        lbl = Label(text='章节列表', font_size='18sp',
                   color=(1,1,1,1), font_name=CN)
        bar.add_widget(lbl)
        root.add_widget(bar)

        self._status = status_label('加载章节中...')
        root.add_widget(self._status)

        sv, self._grid = scroll_grid()
        root.add_widget(sv)

        self.add_widget(root)

    def load_chapters(self, url):
        self._grid.clear_widgets()
        self._status.text = '加载章节中...'
        app = App.get_running_app()
        app.shelf.get_chapters(url, self._on_chapters)

    def _on_chapters(self, data, error=None):
        self._grid.clear_widgets()
        if error:
            self._status.text = '加载失败'
            return
        if not data:
            self._status.text = '暂无章节'
            return
        self._status.text = ''
        for ch in data:
            btn = Button(
                text=f'[{ch["index"]}] {ch["title"]}',
                size_hint_y=None, height='44dp',
                background_normal='', background_color=(1,1,1,1),
                color=(0.1,0.1,0.1,1),
                halign='left', padding=('16dp',0), font_name=CN,
            )
            btn.bind(on_press=lambda x, c=ch: self._open(c))
            self._grid.add_widget(btn)

    def _open(self, chapter):
        app = App.get_running_app()
        reader = self.manager.get_screen('reader')
        reader.load_chapter(chapter, app.current_book_id)
        self.manager.current = 'reader'

    def _go_back(self):
        self.manager.current = 'bookcase'


# ---------- Screen - 阅读器 ----------
class ReaderScreen(Screen):
    chapter_index = NumericProperty(0)
    book_id = NumericProperty(0)

    def __init__(self, **kw):
        super().__init__(**kw)
        self._build_ui()

    def _build_ui(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical')

        # 顶栏
        bar = BoxLayout(size_hint_y=None, height='48dp',
                       padding=['8dp','4dp'], spacing='8dp')
        with bar.canvas.before:
            Color(0.6, 0.6, 0.6, 1)
            Rectangle(pos=bar.pos, size=bar.size)
        bar.bind(pos=lambda s,v: setattr(s.canvas.before.children[-1], 'pos', v))
        bar.bind(size=lambda s,v: setattr(s.canvas.before.children[-1], 'size', v))

        back_btn = Button(text='< 返回', size_hint_x=0.2,
                         background_color=(1,1,1,0.2), color=(1,1,1,1), font_name=CN)
        back_btn.bind(on_press=lambda x: self._go_back())
        bar.add_widget(back_btn)

        self._title = Label(text='', font_size='16sp',
                           color=(1,1,1,1), font_name=CN)
        bar.add_widget(self._title)
        root.add_widget(bar)

        # 正文
        sv = ScrollView(do_scroll_x=False, size_hint_y=0.92)
        self._content = Label(
            text='加载中...', font_size='17sp',
            color=(0.15,0.15,0.15,1), font_name=CN,
            padding=['15dp','15dp'],
            text_size=(None, None),
            size_hint_y=None, height=0,
            valign='top', halign='left',
        )
        sv.add_widget(self._content)
        root.add_widget(sv)

        self.add_widget(root)

    def load_chapter(self, chapter, book_id):
        self._title.text = chapter['title']
        self._content.text = '加载中...'
        self._content.height = 0
        self.chapter_index = chapter['index']
        self.book_id = book_id

        app = App.get_running_app()
        app.shelf.update_last_read(book_id, chapter['index'])
        app.shelf.get_content(chapter['url'], self._on_content)

    def _on_content(self, data, error=None):
        if data and data.get('content'):
            txt = data['content']
            self._content.text = txt
            # 调整高度
            self._content.texture_update()
            if self._content.texture:
                self._content.height = self._content.texture.height + 30
            if data.get('title'):
                self._title.text = data['title']
            app = App.get_running_app()
            if self.book_id:
                app.shelf.save_chapter({
                    'book_id': self.book_id,
                    'title': self._title.text,
                    'url': '',
                    'content': txt,
                    'chapter_index': self.chapter_index,
                })
        else:
            self._content.text = '获取内容失败，请检查网络'

    def _go_back(self):
        self.manager.current = 'chapters'


# ---------- App ----------
class NovelReaderApp(App):
    current_book = ObjectProperty(None, allownone=True)
    current_book_id = NumericProperty(0)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.shelf = BookShelf()
        self.title = '小说阅读器'

    def build(self):
        from kivy.core.window import Window
        Window.clearcolor = (0.95, 0.95, 0.95, 1)

        sm = ScreenManager()
        sm.add_widget(BookcaseScreen(name='bookcase'))
        sm.add_widget(SearchScreen(name='search'))
        sm.add_widget(ChaptersScreen(name='chapters'))
        sm.add_widget(ReaderScreen(name='reader'))

        Clock.schedule_once(lambda dt: self._load(), 1.0)
        return sm

    def _load(self):
        try:
            sm = self.root
            if sm and sm.has_screen('bookcase'):
                sm.get_screen('bookcase').on_enter()
        except:
            pass
