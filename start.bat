@echo off
REM ============================================================
REM AI Web Agent - Main Launcher (Windows Batch)
REM ============================================================

REM Set console code page to UTF-8
chcp 65001 >nul 2>&1

REM Set environment variables
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM Change to project directory
cd /d "%~dp0"

REM Check Python
if not exist "python\python.exe" (
    echo ERROR: Python not found!
    echo Expected: python\python.exe
    echo Please run setup_python_env.cmd first
    pause
    exit /b 1
)

REM Run Python launcher
python\python.exe launcher.py

REM Pause on error
if errorlevel 1 (
    echo.
    echo Error occurred. Press any key to exit...
    pause >nul
)
