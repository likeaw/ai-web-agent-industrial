# Python 环境设置指南

## 内置 Python 3.11.0 环境配置

本项目支持内置 Python 环境，实现一键部署，无需手动安装 Python。

### 步骤 1：下载 Python 3.11.0

1. 访问 Python 官方下载页面：
   - 直接下载：https://www.python.org/ftp/python/3.11.0/python-3.11.0-embed-amd64.zip
   - 或访问：https://www.python.org/downloads/release/python-3110/
   - 选择 **"Windows embeddable package (64-bit)"**

2. 下载完成后，将 zip 文件保存到项目根目录

### 步骤 2：解压 Python

1. 在项目根目录创建 `python` 文件夹（如果不存在）

2. 将下载的 `python-3.11.0-embed-amd64.zip` 解压到 `python/` 目录

3. 解压后的目录结构应该是：
   ```
   python/
   ├── python.exe
   ├── python311.dll
   ├── python311._pth
   ├── python.cat
   ├── pythonw.exe
   └── vcruntime140.dll
   ```

### 步骤 3：运行设置脚本

1. 双击运行 `setup_python_env.cmd`

2. 脚本会自动：
   - 验证 Python 安装
   - 下载并安装 pip
   - 配置 Python 路径以启用 site-packages
   - 验证安装是否成功

### 步骤 4：验证安装

运行以下命令验证 Python 环境：

```cmd
python\python.exe --version
```

应该输出：`Python 3.11.0`

### 步骤 5：启动项目

运行 `run_agent.cmd`，脚本会自动：
- 检查 Python 环境
- 检查并安装依赖包
- 检查 Playwright 浏览器驱动
- 启动 CLI 界面

## 配置 Pip 镜像源

为了加快国内用户的依赖安装速度，项目支持配置 pip 镜像源。

### 方式一：通过菜单配置（推荐）

1. 运行 `run_agent.cmd`
2. 选择选项 `[5] ⚙️  Configure Pip Mirror`
3. 选择镜像源：
   - `[1]` 阿里云
   - `[2]` 清华大学
   - `[3]` 中科大
   - `[4]` 豆瓣
   - `[5]` 官方源
   - `[6]` 自定义

### 方式二：手动配置

```cmd
python\Scripts\pip.exe config set global.index-url https://mirrors.aliyun.com/pypi/simple/
```

### 常用镜像源

| 镜像源 | URL |
|--------|-----|
| 阿里云 | https://mirrors.aliyun.com/pypi/simple/ |
| 清华大学 | https://pypi.tuna.tsinghua.edu.cn/simple/ |
| 中科大 | https://pypi.mirrors.ustc.edu.cn/simple/ |
| 豆瓣 | https://pypi.douban.com/simple/ |
| 官方源 | https://pypi.org/simple/ |

## 故障排除

### 问题 1：Python 环境未找到

**错误信息：**
```
[ERROR] Built-in Python environment not found!
```

**解决方法：**
- 确认 `python/` 目录存在
- 确认 `python/python.exe` 文件存在
- 重新运行 `setup_python_env.cmd`

### 问题 2：pip 安装失败

**错误信息：**
```
[ERROR] Failed to install pip
```

**解决方法：**
- 检查网络连接
- 尝试手动下载 get-pip.py：
  ```cmd
  powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'python\get-pip.py'"
  python\python.exe python\get-pip.py
  ```

### 问题 3：依赖安装缓慢

**解决方法：**
- 配置国内镜像源（见上方"配置 Pip 镜像源"）
- 使用选项 `[5]` 在菜单中配置

### 问题 4：Playwright 浏览器驱动安装失败

**解决方法：**
- 确保网络连接正常
- 手动安装：
  ```cmd
  python\python.exe -m playwright install chromium
  ```

## 使用系统 Python 环境

如果你已经安装了 Python 3.9+，也可以使用系统 Python：

1. 确保系统 Python 在 PATH 中
2. 直接运行：
   ```cmd
   python -m backend.src.cli
   ```
3. 或修改 `run_agent.cmd` 中的 `PYTHON_EXE` 变量指向系统 Python

## 注意事项

- 内置 Python 环境仅支持 Windows 系统
- Linux/macOS 用户请使用系统 Python 环境
- 内置 Python 环境大小约 10-15 MB（不含依赖包）
- 依赖包安装后，总大小约 200-300 MB

