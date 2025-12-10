@echo off
chcp 65001 >nul 2>&1

set "ROOT=%~dp0.."
pushd "%ROOT%"

echo.
echo ============================================================
echo   Python Environment Setup
echo ============================================================
echo.

REM 下载并（可选）安装 Visual C++ Redistributable（解决 EasyOCR DLL 问题）
set "VC_REDIST=vc_redist.x64.exe"
if not exist "%VC_REDIST%" (
    echo [INFO] Downloading Visual C++ Redistributable...
    powershell -Command "try { Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile '%VC_REDIST%' -UseBasicParsing -ErrorAction Stop } catch { Write-Host 'Download failed'; exit 1 }"
    if errorlevel 1 (
        echo [WARNING] Failed to download Visual C++ Redistributable.
        echo You can manually download from: https://aka.ms/vs/17/release/vc_redist.x64.exe
        echo.
    ) else (
        echo [OK] Downloaded: %VC_REDIST%
        echo.
    )
) else (
    echo [OK] Visual C++ Redistributable installer already exists: %VC_REDIST%
    echo.
)

set /p install_vc=Install Visual C++ Redistributable now? (Y/n): 
if /I not "%install_vc%"=="n" (
    if exist "%VC_REDIST%" (
        echo [INFO] Installing Visual C++ Redistributable...
        "%VC_REDIST%" /quiet /norestart
        if errorlevel 1 (
            echo [WARNING] Visual C++ Redistributable installation may have failed.
            echo You can re-run manually: %VC_REDIST%
        ) else (
            echo [OK] Visual C++ Redistributable installed (quiet mode).
        )
        echo.
    ) else (
        echo [WARNING] Installer not found, skipping installation.
        echo You can download manually: https://aka.ms/vs/17/release/vc_redist.x64.exe
        echo.
    )
)

REM 检查 Python 是否存在
if not exist "python\python.exe" (
    echo [ERROR] Python not found at: python\python.exe
    echo.
    echo Please download Python 3.11.0 Windows embeddable package:
    echo   https://www.python.org/ftp/python/3.11.0/python-3.11.0-embed-amd64.zip
    echo.
    echo Extract it to a folder named 'python' in the project root.
    echo.
    pause
    exit /b 1
)

echo [OK] Python found: python\python.exe
python\python.exe --version
echo.

REM 检查 pip 是否存在
if not exist "python\Scripts\pip.exe" (
    echo [INFO] pip not found. Installing pip...
    echo.
    
    REM 下载 get-pip.py
if not exist "python\get-pip.py" (
        echo [INFO] Downloading get-pip.py...
        powershell -Command "try { Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'python\get-pip.py' -ErrorAction Stop } catch { Write-Host 'Download failed'; exit 1 }"
        if errorlevel 1 (
            echo [ERROR] Failed to download get-pip.py
            echo Please check your internet connection.
            echo.
            pause
            exit /b 1
        )
    )
    
    REM 安装 pip
    echo [INFO] Installing pip...
    python\python.exe python\get-pip.py
    if errorlevel 1 (
        echo [ERROR] Failed to install pip
        echo.
        pause
        exit /b 1
    )
    
    REM 验证 pip 安装
    if not exist "python\Scripts\pip.exe" (
        echo [ERROR] pip installation failed
        echo.
        pause
        exit /b 1
    )
    
    echo [OK] pip installed successfully.
    echo.
) else (
    echo [OK] pip is already installed.
    echo.
)

REM 配置 python311._pth（仅适用于 embeddable 版本）
if exist "python\python311._pth" (
    findstr /C:"import site" python\python311._pth >nul 2>&1
    if errorlevel 1 (
        echo [INFO] Configuring python311._pth...
        echo import site >> python\python311._pth
        echo [OK] python311._pth configured.
    ) else (
        echo [OK] python311._pth already configured.
    )
    echo.
)

REM 询问是否安装依赖包
echo ============================================================
echo   Package Installation
echo ============================================================
echo.
echo This will install all required packages from requirements.txt
echo This may take 5-10 minutes.
echo.
set /p install_deps=Install required packages now? (Y/n): 

if /I "%install_deps%"=="n" (
    echo.
    echo [INFO] Skipping package installation.
    echo You can install packages later by running:
    echo   python\Scripts\pip.exe install -r requirements.txt
    echo.
    goto :end
)

REM 检查 requirements.txt
if not exist "requirements.txt" (
    echo.
    echo [ERROR] requirements.txt not found!
    echo.
    pause
    exit /b 1
)

REM 升级 pip
echo.
echo [INFO] Upgrading pip...
python\Scripts\pip.exe install --upgrade pip setuptools wheel >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Failed to upgrade pip, but continuing...
) else (
    echo [OK] pip upgraded.
)

REM 安装依赖包
echo.
echo [INFO] Installing packages from requirements.txt...
echo This may take several minutes, please wait...
echo.
python\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [WARNING] Some packages may have failed to install.
    echo You can try installing manually later:
    echo   python\Scripts\pip.exe install -r requirements.txt
    echo.
) else (
    echo.
    echo [OK] All packages installed successfully!
    echo.
)

REM 安装 Playwright 浏览器驱动
echo [INFO] Installing Playwright browser drivers...
python\Scripts\python.exe -m playwright install chromium >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Failed to install Playwright browsers.
    echo You can install them later: python\Scripts\python.exe -m playwright install chromium
) else (
    echo [OK] Playwright browsers installed.
)

:end
echo.
echo ============================================================
echo   Setup Completed!
echo ============================================================
echo.
echo [SUCCESS] Python environment setup completed!
echo.
echo Next steps:
echo   1. 运行 scripts\start.bat 启动应用
echo   2. 如未安装依赖，可手动执行:
echo      python\Scripts\pip.exe install -r requirements.txt
echo.
echo Note: For OCR functionality, easyocr will download models
popd
echo       automatically on first use (may take a few minutes).
echo.
pause
