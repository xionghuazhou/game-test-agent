@echo off
title 游戏测试Agent - 一键关闭
echo ============================================
echo          游戏测试Agent - 一键关闭
echo ============================================
echo.

set "found=0"
rem 结束所有监听 8000 端口的服务进程（精确匹配，不影响其他程序）
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo [结束] 进程 PID=%%p
    taskkill /F /T /PID %%p >nul 2>&1
    set "found=1"
)

if "%found%"=="0" (
    echo [提示] 服务当前未在运行。
) else (
    echo.
    echo [完成] 服务已停止，所有相关进程已结束。
)

rem 确认端口已释放
ping -n 2 127.0.0.1 >nul
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [警告] 仍有进程占用 8000 端口，请手动检查。
) else (
    echo [确认] 8000 端口已释放。
)
echo.
echo 本次运行产生的数据（数据库/截图/日志）保留在 backend\data\ 下。
ping -n 5 127.0.0.1 >nul
exit /b 0
