"""
启动脚本 — 无论从哪个目录运行都能正常工作
用法：python run.py
"""
import os
import sys
import uvicorn

# 把 novel_reader/ 目录加入 sys.path，确保 `app` 包可被找到
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)          # 切换工作目录到 novel_reader/
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[os.path.join(ROOT, "app")],
    )
