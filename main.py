"""小说阅读器 Kivy APP - 启动入口"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import NovelReaderApp

if __name__ == '__main__':
    NovelReaderApp().run()

