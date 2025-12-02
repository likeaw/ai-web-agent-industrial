@echo off
chcp 65001 >nul 2>&1
REM ============================================================
REM Python Environment Setup Script
REM For downloading and configuring embedded Python 3.11.0
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo   Python Environment Setup
echo ============================================================
echo.

REM 检查是否已存在 Python 环境
if exist "python\python.exe" (
    echo [INFO] Python environment already exists at: python\
    echo [INFO] Python version:
    python\python.exe --version
    echo.
    echo [INFO] Python is already installed. Checking pip configuration...
    goto check_pip
)

echo [INFO] Please download Python 3.11.0 Windows embeddable package:
echo.
echo   Download URL: https://www.python.org/ftp/python/3.11.0/python-3.11.0-embed-amd64.zip
echo.
echo   Or visit: https://www.python.org/downloads/release/python-3110/
echo   Select: "Windows embeddable package (64-bit)"
echo.
set /p continue=Have you downloaded the zip file? (y/N): 

if /I not "%continue%"=="y" (
    echo Setup cancelled. Please download Python first.
    pause
    exit /b 1
)

echo.
echo [INFO] Please extract the zip file to a folder named 'python' in the project root.
echo [INFO] Expected structure: python\python.exe, python\python311.dll, etc.
echo.
set /p extracted=Have you extracted the zip to 'python' folder? (y/N): 

if /I not "%extracted%"=="y" (
    echo Setup cancelled. Please extract Python first.
    pause
    exit /b 1
)

REM 检查 Python 是否存在
if not exist "python\python.exe" (
    echo [ERROR] python\python.exe not found!
    echo [ERROR] Please make sure you extracted Python to the 'python' folder.
    pause
    exit /b 1
)

echo.
echo [INFO] Verifying Python installation...
python\python.exe --version
if errorlevel 1 (
    echo [ERROR] Python verification failed!
    pause
    exit /b 1
)

:check_pip
REM 检查并安装 pip（如果不存在）
if exist "python\Scripts\pip.exe" (
    echo [OK] pip is already installed.
) else (
    echo.
    echo [INFO] pip not found. Installing pip...
    if not exist "python\get-pip.py" (
        echo [INFO] Downloading get-pip.py...
        powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'python\get-pip.py'"
        if errorlevel 1 (
            echo [ERROR] Failed to download get-pip.py
            pause
            exit /b 1
        )
    )
    
    echo [INFO] Installing pip...
    python\python.exe python\get-pip.py
    if errorlevel 1 (
        echo [ERROR] Failed to install pip
        pause
        exit /b 1
    )
    echo [OK] pip installed successfully.
)

REM 修改 python311._pth 以启用 site-packages（仅适用于 embeddable 版本）
echo [INFO] Configuring Python path...
if exist "python\python311._pth" (
    findstr /C:"import site" python\python311._pth >nul 2>&1
    if errorlevel 1 (
        echo [INFO] Enabling site-packages in python311._pth...
        echo import site >> python\python311._pth
    ) else (
        echo [OK] python311._pth already configured.
    )
) else (
    echo [INFO] python311._pth not found (full Python installation detected, no need to configure).
)

echo.
echo [SUCCESS] Python environment setup completed!
echo [INFO] Python location: %CD%\python\
echo.
echo [INFO] Next steps:
echo   1. Run run_agent.cmd to start the application
echo   2. The script will automatically install required packages
echo.
pause

