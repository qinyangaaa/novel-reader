"""
全局配置 — 所有模块共享的单例对象
在这里统一初始化，避免各路由各自 new 一份
"""
import json
from pathlib import Path
from fastapi.templating import Jinja2Templates

BASE_DIR  = Path(__file__).resolve().parent.parent          # novel_reader/
TMPL_DIR  = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"
DB_PATH   = BASE_DIR / "data" / "novel.db"

# 共享 Jinja2 实例（含 tojson filter）
templates = Jinja2Templates(directory=str(TMPL_DIR))
templates.env.filters["tojson"] = lambda v: json.dumps(v, ensure_ascii=False)
