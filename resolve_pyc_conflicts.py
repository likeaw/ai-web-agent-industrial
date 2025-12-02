#!/usr/bin/env python3
"""
解决 .pyc 文件冲突的脚本
这些文件不应该被版本控制，所以直接移除它们
"""
import subprocess
import sys
import os

# 禁用 git 分页器 - 使用多种方法确保分页器被禁用
env = os.environ.copy()
env['GIT_PAGER'] = 'cat'
env['PAGER'] = 'cat'
env['GIT_CONFIG_NOSYSTEM'] = '1'

# 临时禁用 git 分页器配置
subprocess.run(["git", "config", "--global", "core.pager", "cat"], 
               capture_output=True, timeout=5)

pyc_files = [
    "backend/src/__pycache__/cli.cpython-314.pyc",
    "backend/src/agent/__pycache__/DecisionMaker.cpython-314.pyc",
    "backend/src/services/__pycache__/BrowserService.cpython-314.pyc",
    "backend/src/services/__pycache__/LLMAdapter.cpython-314.pyc",
    "backend/src/tools/browser/__pycache__/__init__.cpython-314.pyc",
    "backend/src/tools/browser/__pycache__/downloads.cpython-314.pyc"
]

print("Resolving .pyc file conflicts by removing them from git...")
print("=" * 60)

for pyc_file in pyc_files:
    print(f"\nProcessing: {pyc_file}")
    
    # 首先尝试解决冲突（选择 ours 版本）
    try:
        result = subprocess.run(
            ["git", "checkout", "--ours", "--", pyc_file],
            capture_output=True,
            text=True,
            timeout=10,
            env=env
        )
        if result.returncode == 0:
            print(f"  ✓ Resolved conflict for {pyc_file}")
        else:
            print(f"  ! Conflict resolution returned: {result.stderr.strip()}")
    except Exception as e:
        print(f"  ! Error resolving conflict: {e}")
    
    # 然后从 git 索引中移除
    try:
        result = subprocess.run(
            ["git", "rm", "--cached", "-f", pyc_file],
            capture_output=True,
            text=True,
            timeout=10,
            env=env
        )
        if result.returncode == 0:
            print(f"  ✓ Removed {pyc_file} from git tracking")
        else:
            print(f"  ! Removal returned: {result.stderr.strip()}")
    except Exception as e:
        print(f"  ! Error removing file: {e}")

print("\n" + "=" * 60)
print("Done! All .pyc files have been processed.")
print("They will be ignored in the future thanks to .gitignore")

