@echo off
REM ============================================================
REM AI Web Agent - Full Stack Launcher (API + Frontend)
REM ============================================================

set "SCRIPT_DIR=%~dp0"
set "ROOT=%SCRIPT_DIR%.."
pushd "%ROOT%"

echo.
echo ============================================================
echo   Starting Full Stack Application
echo ============================================================
echo.
echo This will start:
echo   1. API Server (http://localhost:8000)
echo   2. Frontend Dev Server (http://localhost:3000)
echo.
echo Press Ctrl+C to stop all servers
echo.

REM Start API server in a new window
start "API Server" cmd /k "\"%SCRIPT_DIR%run_api_server.cmd\""

REM Wait a bit for API server to start
timeout /t 3 /nobreak >nul

REM Start frontend in a new window
start "Frontend Dev Server" cmd /k "\"%SCRIPT_DIR%run_frontend.cmd\""

echo.
echo Both servers are starting...
echo.
echo API Server: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Close the command windows to stop the servers.
echo.

pause

popd

