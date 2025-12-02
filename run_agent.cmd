@echo off
REM ============================================================
REM AI Web Agent - Simple Launcher (Windows .cmd)
REM ============================================================

REM Set paths
cd /d "%~dp0"
set "PYTHON_EXE=%~dp0python\python.exe"
set "PIP_EXE=%~dp0python\Scripts\pip.exe"
set "LOG_FILE=%~dp0run_agent.log"
set "ERROR_LOG=%~dp0run_agent_error.log"
set "DEPS_FLAG=%~dp0.deps_installed"

REM Log start
echo [%DATE% %TIME%] Script started >> "%LOG_FILE%"

REM Check Python
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python not found at: %PYTHON_EXE% >> "%ERROR_LOG%"
    echo.
    echo ERROR: Python not found!
    echo Please run setup_python_env.cmd first.
    echo.
    pause
    exit /b 1
)

REM Check pip
if not exist "%PIP_EXE%" (
    echo [ERROR] pip not found at: %PIP_EXE% >> "%ERROR_LOG%"
    echo.
    echo ERROR: pip not found!
    echo Please run setup_python_env.cmd first.
    echo.
    pause
    exit /b 1
)

REM Quick dependency check (only on first run)
if not exist "%DEPS_FLAG%" (
    echo [%DATE% %TIME%] Checking dependencies... >> "%LOG_FILE%"
    echo.
    echo Checking dependencies...
    
    REM Check each package
    set "NEED_INSTALL=0"
    
    "%PYTHON_EXE%" -c "import pydantic" >nul 2>> "%ERROR_LOG%"
    if errorlevel 1 (
        echo Missing: pydantic
        set "NEED_INSTALL=1"
    )
    
    "%PYTHON_EXE%" -c "import playwright" >nul 2>> "%ERROR_LOG%"
    if errorlevel 1 (
        echo Missing: playwright
        set "NEED_INSTALL=1"
    )
    
    "%PYTHON_EXE%" -c "import rich" >nul 2>> "%ERROR_LOG%"
    if errorlevel 1 (
        echo Missing: rich
        set "NEED_INSTALL=1"
    )
    
    "%PYTHON_EXE%" -c "import dotenv" >nul 2>> "%ERROR_LOG%"
    if errorlevel 1 (
        echo Missing: python-dotenv
        set "NEED_INSTALL=1"
    )
    
    "%PYTHON_EXE%" -c "import requests" >nul 2>> "%ERROR_LOG%"
    if errorlevel 1 (
        echo Missing: requests
        set "NEED_INSTALL=1"
    )
    
    REM Install if needed
    if "%NEED_INSTALL%"=="1" (
        echo.
        echo Installing missing dependencies...
        echo This may take a few minutes...
        echo.
        "%PIP_EXE%" install -r requirements.txt >> "%LOG_FILE%" 2>> "%ERROR_LOG%"
        if errorlevel 1 (
            echo [ERROR] Failed to install dependencies >> "%ERROR_LOG%"
            echo.
            echo ERROR: Failed to install dependencies!
            echo Check run_agent_error.log for details.
            echo.
            pause
            exit /b 1
        )
        echo Dependencies installed successfully.
    ) else (
        echo All dependencies are installed.
    )
    
    REM Create flag file
    echo. > "%DEPS_FLAG%" 2>> "%ERROR_LOG%"
    echo [%DATE% %TIME%] Dependencies check completed >> "%LOG_FILE%"
) else (
    echo [%DATE% %TIME%] Dependencies already checked, skipping... >> "%LOG_FILE%"
)

REM Main menu loop
:menu
cls
echo.
echo ============================================================
echo          AI Web Agent - Industrial
echo          Intelligent Web Automation
echo ============================================================
echo.
echo   [1] Run CLI (Start AI Agent)
echo   [2] Clean Logs
echo   [3] Clean Temp Files
echo   [4] Clean All
echo   [5] Configure Pip Mirror
echo   [6] Reinstall Dependencies
echo   [Q] Quit
echo.
echo ============================================================
set /p choice=Select option: 

if /I "%choice%"=="1" goto run
if /I "%choice%"=="2" goto clean_logs
if /I "%choice%"=="3" goto clean_temp
if /I "%choice%"=="4" goto clean_all
if /I "%choice%"=="5" goto config_pip
if /I "%choice%"=="6" goto reinstall
if /I "%choice%"=="Q" goto end
if /I "%choice%"=="q" goto end

echo Invalid option, please try again...
timeout /t 2 >nul
goto menu

:run
cls
echo.
echo Starting AI Web Agent CLI...
echo.
echo [%DATE% %TIME%] Starting CLI >> "%LOG_FILE%"
"%PYTHON_EXE%" -m backend.src.cli 2>> "%ERROR_LOG%"
set "EXIT_CODE=%ERRORLEVEL%"
echo [%DATE% %TIME%] CLI exited with code: %EXIT_CODE% >> "%LOG_FILE%"
if errorlevel 1 (
    echo.
    echo CLI exited with error code: %EXIT_CODE%
    echo Check run_agent_error.log for details.
)
echo.
pause
goto menu

:clean_logs
echo.
echo Cleaning logs directory...
if exist "logs" (
    rmdir /S /Q "logs" 2>> "%ERROR_LOG%"
    echo Logs directory removed.
) else (
    echo Logs directory not found.
)
timeout /t 2 >nul
goto menu

:clean_temp
echo.
echo Cleaning temp directory...
if exist "temp" (
    rmdir /S /Q "temp" 2>> "%ERROR_LOG%"
    echo Temp directory removed.
) else (
    echo Temp directory not found.
)
timeout /t 2 >nul
goto menu

:clean_all
call :clean_logs
call :clean_temp
goto menu

:config_pip
cls
echo.
echo ============================================================
echo   Configure Pip Mirror Source
echo ============================================================
echo.
echo   [1] Aliyun
echo   [2] Tsinghua
echo   [3] USTC
echo   [4] Douban
echo   [5] Official
echo   [0] Back
echo.
set /p mirror_choice=Select mirror: 

if "%mirror_choice%"=="1" set "MIRROR=https://mirrors.aliyun.com/pypi/simple/"
if "%mirror_choice%"=="2" set "MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple/"
if "%mirror_choice%"=="3" set "MIRROR=https://pypi.mirrors.ustc.edu.cn/simple/"
if "%mirror_choice%"=="4" set "MIRROR=https://pypi.douban.com/simple/"
if "%mirror_choice%"=="5" set "MIRROR=https://pypi.org/simple/"
if "%mirror_choice%"=="0" goto menu

if defined MIRROR (
    echo.
    echo Configuring pip to use: %MIRROR%
    "%PIP_EXE%" config set global.index-url %MIRROR% 2>> "%ERROR_LOG%"
    if errorlevel 1 (
        echo Failed to configure pip mirror.
    ) else (
        echo Pip mirror configured successfully!
    )
    timeout /t 2 >nul
)
goto menu

:reinstall
echo.
echo Reinstalling dependencies...
if exist "%DEPS_FLAG%" del /Q "%DEPS_FLAG%" 2>> "%ERROR_LOG%"
echo.
echo Installing dependencies from requirements.txt...
echo This may take a few minutes...
echo.
"%PIP_EXE%" install -r requirements.txt >> "%LOG_FILE%" 2>> "%ERROR_LOG%"
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies!
    echo Check run_agent_error.log for details.
    pause
) else (
    echo.
    echo Dependencies reinstalled successfully!
    echo. > "%DEPS_FLAG%" 2>> "%ERROR_LOG%"
    timeout /t 2 >nul
)
goto menu

:end
echo.
echo Thank you for using AI Web Agent!
echo [%DATE% %TIME%] Script ended >> "%LOG_FILE%"
timeout /t 1 >nul
exit /b 0
