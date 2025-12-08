# OCR Troubleshooting Guide

## Problem: "EasyOCR is not installed" but package is already installed

### Root Cause

EasyOCR package is installed, but it cannot be imported because PyTorch (a dependency) fails to load DLL files. This is typically due to missing Visual C++ Redistributable.

### Error Message

```
OSError: [WinError 1114] 动态链接库(DLL)初始化例程失败。 
Error loading "...\torch\lib\c10.dll" or one of its dependencies.
```

### Solution

1. **Install Visual C++ Redistributable**

   Download and install from Microsoft:
   - Direct link: https://aka.ms/vs/17/release/vc_redist.x64.exe
   - Or search for "Visual C++ Redistributable 2015-2022"

2. **After installation**
   - Restart your computer (recommended)
   - Or restart the Python process/application

3. **Verify installation**

   Run this command to test:
   ```bash
   python\python.exe -c "import easyocr; print('OK')"
   ```

### Alternative Solutions

If Visual C++ Redistributable doesn't solve the issue:

1. **Reinstall PyTorch** (CPU version, lighter):
   ```bash
   pip uninstall torch torchvision torchaudio
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
   ```

2. **Use CPU-only EasyOCR** (if GPU version causes issues):
   The code already uses CPU mode by default (`gpu=False`)

3. **Check Python version compatibility**:
   - Ensure Python 3.8-3.11 (recommended)
   - 32-bit Python may have issues with PyTorch

### Current Status

The application will automatically fall back to HTML-based content extraction when OCR is unavailable. You can still use the application, but OCR features will be disabled until the DLL issue is resolved.

