@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [信息] 正在检查依赖...
python -m pip install -r requirements.txt -q
echo [信息] 启动小说爬虫...
python main.py
pause
