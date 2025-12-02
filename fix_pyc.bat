@echo off
chcp 65001 >nul
echo 正在解决 .pyc 文件冲突...
echo.

set GIT_PAGER=cat
set PAGER=cat

git rm --cached -f backend/src/__pycache__/cli.cpython-314.pyc 2>nul
if %errorlevel% equ 0 (echo [OK] 已移除 cli.cpython-314.pyc) else (echo [跳过] cli.cpython-314.pyc)

git rm --cached -f backend/src/agent/__pycache__/DecisionMaker.cpython-314.pyc 2>nul
if %errorlevel% equ 0 (echo [OK] 已移除 DecisionMaker.cpython-314.pyc) else (echo [跳过] DecisionMaker.cpython-314.pyc)

git rm --cached -f backend/src/services/__pycache__/BrowserService.cpython-314.pyc 2>nul
if %errorlevel% equ 0 (echo [OK] 已移除 BrowserService.cpython-314.pyc) else (echo [跳过] BrowserService.cpython-314.pyc)

git rm --cached -f backend/src/services/__pycache__/LLMAdapter.cpython-314.pyc 2>nul
if %errorlevel% equ 0 (echo [OK] 已移除 LLMAdapter.cpython-314.pyc) else (echo [跳过] LLMAdapter.cpython-314.pyc)

git rm --cached -f backend/src/tools/browser/__pycache__/__init__.cpython-314.pyc 2>nul
if %errorlevel% equ 0 (echo [OK] 已移除 __init__.cpython-314.pyc) else (echo [跳过] __init__.cpython-314.pyc)

git rm --cached -f backend/src/tools/browser/__pycache__/downloads.cpython-314.pyc 2>nul
if %errorlevel% equ 0 (echo [OK] 已移除 downloads.cpython-314.pyc) else (echo [跳过] downloads.cpython-314.pyc)

echo.
echo 完成！所有 .pyc 文件已从 git 跟踪中移除。
echo 这些文件将被 .gitignore 忽略，不会再被版本控制。
pause



