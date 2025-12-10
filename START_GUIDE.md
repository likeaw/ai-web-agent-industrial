# AI Web Agent - Quick Start Guide

## File Structure

### Main Launcher Files

- **`start.bat`** - Main launcher (Windows batch file)
  - Double-click to start the application
  - Sets UTF-8 encoding to avoid garbled characters
  
- **`launcher.py`** - Main Python launcher
  - Unified launcher with menu interface
  - Handles environment checks and dependency installation
  - English-only UI to avoid encoding issues

- **`setup_python_env.cmd`** - Python environment setup
  - Run this first to set up Python and install dependencies
  - Downloads and configures Python 3.11.0 embeddable package

### Service Launchers

- **`run_api_server.cmd`** - Start API server only
- **`run_frontend.cmd`** - Start frontend dev server only  
- **`run_full_stack.cmd`** - Start both API and frontend

### Removed Files (Cleaned Up)

The following redundant files have been removed:
- `run_agent.cmd` (replaced by `launcher.py`)
- `run_agent.py` (replaced by `launcher.py`)
- `start_agent.py` (replaced by `launcher.py`)
- `run_simple.bat` (replaced by `start.bat`)

## Quick Start

### First Time Setup

1. **Set up Python environment:**
   ```bash
   setup_python_env.cmd
   ```
   This will:
   - Check for Python installation
   - Install pip if needed
   - Install all required dependencies
   - Install Playwright browser drivers

2. **Start the application:**
   ```bash
   start.bat
   ```
   Or double-click `start.bat` in Windows Explorer

### Using the Launcher Menu

After starting, you'll see a menu with options:

1. **Run CLI** - Start the AI Agent command-line interface
2. **Run API Server** - Start the API server (http://localhost:8000)
3. **Run Frontend** - Start the frontend dev server (http://localhost:3000)
4. **Run Full Stack** - Start both API and frontend together
5. **Clean Logs** - Remove all log files
6. **Clean Temp Files** - Remove temporary files
7. **Clean All** - Clean both logs and temp files
8. **Configure Pip Mirror** - Set pip package mirror source
9. **Reinstall Dependencies** - Reinstall all Python packages

## Troubleshooting

### Encoding Issues (Garbled Characters)

The launcher uses English-only UI to avoid encoding issues. If you still see garbled characters:

1. Make sure you're using `start.bat` (not running Python directly)
2. Check that your terminal supports UTF-8
3. Try running in a new terminal window

### Python Not Found

Run `setup_python_env.cmd` first to set up the Python environment.

### Dependencies Missing

The launcher will automatically check and offer to install missing dependencies on first run.

## Notes

- All launcher files use UTF-8 encoding
- The main launcher (`launcher.py`) uses English-only UI to ensure compatibility
- Logs are stored in the `logs/` directory
- Temporary files are stored in the `temp/` directory

