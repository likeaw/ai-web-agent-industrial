@echo off
REM ============================================================
REM AI Web Agent - launcher / cleaner (Windows .cmd)
REM This script must be placed in the project root.
REM ============================================================

REM Switch to the directory of this script (project root)
cd /d "%~dp0"

:menu
echo.
echo ===================== AI Web Agent ======================
echo   1. Run CLI (rich-based AI web agent)
echo   2. Clean logs   (logs\*)
echo   3. Clean temp   (temp\*)
echo   4. Clean logs + temp
echo   Q. Quit
echo =========================================================
set /p choice=Select option (1/2/3/4/Q): 

if /I "%choice%"=="1" goto run
if /I "%choice%"=="2" goto clear_logs
if /I "%choice%"=="3" goto clear_temp
if /I "%choice%"=="4" goto clear_all
if /I "%choice%"=="Q" goto end
if /I "%choice%"=="q" goto end

echo Invalid option, please try again...
goto menu

:run
echo.
echo [INFO] Starting AI Web Agent CLI ...
echo.
python -m backend.src.cli
echo.
echo [INFO] CLI exited. Back to menu.
goto menu

:clear_logs
echo.
echo [INFO] Cleaning logs directory (logs\) ...
if exist "logs" (
  rmdir /S /Q "logs"
  echo [OK] logs\ directory removed.
) else (
  echo [INFO] logs\ directory not found. Nothing to clean.
)
goto menu

:clear_temp
echo.
echo [INFO] Cleaning temp directory (temp\) ...
if exist "temp" (
  rmdir /S /Q "temp"
  echo [OK] temp\ directory removed.
) else (
  echo [INFO] temp\ directory not found. Nothing to clean.
)
goto menu

:clear_all
call :clear_logs
call :clear_temp
goto menu

:end
echo.
echo Bye.
exit /b 0


