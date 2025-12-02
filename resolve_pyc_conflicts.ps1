# 解决 .pyc 文件冲突的脚本
# 这些文件不应该被版本控制，所以直接移除它们

$pycFiles = @(
    "backend/src/__pycache__/cli.cpython-314.pyc",
    "backend/src/agent/__pycache__/DecisionMaker.cpython-314.pyc",
    "backend/src/services/__pycache__/BrowserService.cpython-314.pyc",
    "backend/src/services/__pycache__/LLMAdapter.cpython-314.pyc",
    "backend/src/tools/browser/__pycache__/__init__.cpython-314.pyc",
    "backend/src/tools/browser/__pycache__/downloads.cpython-314.pyc"
)

foreach ($file in $pycFiles) {
    Write-Host "Removing $file from git..."
    git rm --cached -f $file 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Removed $file"
    } else {
        Write-Host "✗ Failed to remove $file (may already be removed)"
    }
}

Write-Host "`nAll .pyc files have been removed from git tracking."
Write-Host "They will be ignored in the future thanks to .gitignore"

