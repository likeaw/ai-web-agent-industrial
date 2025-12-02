@echo off
echo Resolving .pyc file conflicts by removing them from git...

git rm --cached -f backend/src/__pycache__/cli.cpython-314.pyc
git rm --cached -f backend/src/agent/__pycache__/DecisionMaker.cpython-314.pyc
git rm --cached -f backend/src/services/__pycache__/BrowserService.cpython-314.pyc
git rm --cached -f backend/src/services/__pycache__/LLMAdapter.cpython-314.pyc
git rm --cached -f backend/src/tools/browser/__pycache__/__init__.cpython-314.pyc
git rm --cached -f backend/src/tools/browser/__pycache__/downloads.cpython-314.pyc

echo Done! .pyc files have been removed from git tracking.

