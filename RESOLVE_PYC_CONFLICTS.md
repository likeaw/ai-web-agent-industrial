# 解决 .pyc 文件冲突的说明

由于终端环境的问题，请手动执行以下命令来解决 .pyc 文件的冲突。

## 方法 1：使用 Git Bash 或 CMD（推荐）

打开 **Git Bash** 或 **CMD**（不是 PowerShell），然后执行：

```bash
# 移除所有冲突的 .pyc 文件
git rm --cached -f backend/src/__pycache__/cli.cpython-314.pyc
git rm --cached -f backend/src/agent/__pycache__/DecisionMaker.cpython-314.pyc
git rm --cached -f backend/src/services/__pycache__/BrowserService.cpython-314.pyc
git rm --cached -f backend/src/services/__pycache__/LLMAdapter.cpython-314.pyc
git rm --cached -f backend/src/tools/browser/__pycache__/__init__.cpython-314.pyc
git rm --cached -f backend/src/tools/browser/__pycache__/downloads.cpython-314.pyc
```

## 方法 2：使用 PowerShell（如果方法1不行）

在 PowerShell 中，先设置环境变量禁用分页器：

```powershell
$env:GIT_PAGER = 'cat'
$env:GIT_CONFIG_NOSYSTEM = '1'

# 然后执行移除命令
git rm --cached -f backend/src/__pycache__/cli.cpython-314.pyc
git rm --cached -f backend/src/agent/__pycache__/DecisionMaker.cpython-314.pyc
git rm --cached -f backend/src/services/__pycache__/BrowserService.cpython-314.pyc
git rm --cached -f backend/src/services/__pycache__/LLMAdapter.cpython-314.pyc
git rm --cached -f backend/src/tools/browser/__pycache__/__init__.cpython-314.pyc
git rm --cached -f backend/src/tools/browser/__pycache__/downloads.cpython-314.pyc
```

## 方法 3：使用 Git GUI 工具

如果你使用 SourceTree、GitKraken 或其他 Git GUI 工具：
1. 找到冲突的 .pyc 文件
2. 右键选择 "Resolve Conflict" -> "Remove from index" 或 "Unstage"
3. 或者直接删除这些文件（它们不应该被版本控制）

## 验证

执行完命令后，运行：

```bash
git status
```

应该看到这些 .pyc 文件不再显示为冲突状态。

## 说明

- `.pyc` 文件是 Python 的字节码缓存文件，不应该被版本控制
- `.gitignore` 文件已经创建，包含了 `__pycache__/` 和 `*.pyc` 规则
- 这些文件会在 Python 运行时自动重新生成

