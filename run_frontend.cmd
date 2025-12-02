@echo off
REM ============================================================
REM AI Web Agent - Frontend Server Launcher
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo   Starting Frontend Development Server
echo ============================================================
echo.

REM Check if Node.js is installed
where node >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH!
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

REM Check if frontend directory exists
if not exist "frontend" (
    echo ERROR: Frontend directory not found!
    pause
    exit /b 1
)

REM Navigate to frontend directory
cd frontend

REM Check if node_modules exists
if not exist "node_modules" (
    echo Installing dependencies...
    call npm install
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies!
        pause
        exit /b 1
    )
)

REM Start development server
echo.
echo Starting Vite development server...
echo Frontend will be available at http://localhost:3000
echo.
call npm run dev

pause

