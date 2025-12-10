@echo off
REM ============================================================
REM AI Web Agent - API Server Launcher
REM ============================================================

set "ROOT=%~dp0.."
pushd "%ROOT%"

REM Set paths
set "PYTHON_EXE=%ROOT%\python\python.exe"
set "PIP_EXE=%ROOT%\python\Scripts\pip.exe"
set "LOG_FILE=%ROOT%\api_server.log"
set "ERROR_LOG=%ROOT%\api_server_error.log"

REM Check Python
if not exist "%PYTHON_EXE%" (
    echo ERROR: Python not found at: %PYTHON_EXE%
    echo Please run setup_python_env.cmd first.
    pause
    exit /b 1
)

REM Check pip
if not exist "%PIP_EXE%" (
    echo ERROR: pip not found at: %PIP_EXE%
    echo Please run setup_python_env.cmd first.
    pause
    exit /b 1
)

REM Check FastAPI
"%PYTHON_EXE%" -c "import fastapi" >nul 2>> "%ERROR_LOG%"
if errorlevel 1 (
    echo Installing API dependencies...
    "%PIP_EXE%" install fastapi uvicorn[standard] websockets python-socketio >> "%LOG_FILE%" 2>> "%ERROR_LOG%"
    if errorlevel 1 (
        echo ERROR: Failed to install API dependencies!
        echo Check api_server_error.log for details.
        pause
        exit /b 1
    )
)

echo.
echo ============================================================
echo   Starting API Server
echo ============================================================
echo.
echo API Server will be available at http://localhost:8000
echo WebSocket endpoint: ws://localhost:8000/ws
echo.
echo Press Ctrl+C to stop the server
echo.

"%PYTHON_EXE%" -m backend.src.api_runner >> "%LOG_FILE%" 2>> "%ERROR_LOG%"

pause

popd

