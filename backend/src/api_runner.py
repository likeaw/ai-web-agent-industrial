"""
API服务器启动脚本
"""

import uvicorn
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    uvicorn.run(
        "backend.src.api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )

