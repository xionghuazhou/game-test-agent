@echo off
title 游戏测试Agent - 一键启动
cd /d "%~dp0backend"

echo ============================================
echo          游戏测试Agent - 一键启动
echo ============================================
echo.

rem ---------- 0) 若服务已在运行，直接打开面板 ----------
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [提示] 服务已在运行，直接打开控制台面板...
    start "" http://127.0.0.1:8000/
ping -n 4 127.0.0.1 >nul
    exit /b 0
)

rem ---------- 1) 依赖检查（首次运行自动安装） ----------
python -c "import fastapi, uvicorn, sqlalchemy, httpx, PIL" >nul 2>&1
if not %errorlevel%==0 (
    echo [初始化] 首次运行，正在安装依赖，约1-2分钟，仅此一次...
    pip install -r requirements.txt -q
    if not %errorlevel%==0 (
        echo [错误] 依赖安装失败，请检查 Python 环境后重试。
        pause
        exit /b 1
    )
)

rem ---------- 2) 初始化数据库（幂等，秒级） ----------
python scripts\init_db.py >nul 2>&1

rem ---------- 3) 后台启动服务（最小化窗口，日志写入 server.log） ----------
echo [启动] 正在启动服务...
start "GameTestAgent-Server" /min cmd /c "python -m uvicorn main:app --host 127.0.0.1 --port 8000 > server.log 2>&1"

rem ---------- 4) 等待服务就绪（最多30秒） ----------
set /a tries=0
:waitloop
ping -n 2 127.0.0.1 >nul
set /a tries+=1
curl -s -m 2 http://127.0.0.1:8000/api/health >nul 2>&1
if %errorlevel%==0 goto ready
if %tries% geq 30 (
    echo.
    echo [错误] 服务启动超时，请查看 backend\server.log 排查。
    pause
    exit /b 1
)
goto waitloop

:ready
echo [完成] 服务已就绪！
echo [打开] 正在打开控制台: http://127.0.0.1:8000
start "" http://127.0.0.1:8000/
echo.
echo  提示: 服务在任务栏最小化窗口 [GameTestAgent-Server] 中运行
echo        不用时请双击「一键关闭.bat」，它会结束所有相关进程
echo.
ping -n 7 127.0.0.1 >nul
exit /b 0
