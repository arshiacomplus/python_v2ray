@echo off
echo ===================================================
echo ===    Setting up python_v2ray Development     ===
echo ===================================================
echo.
echo [1/4] Checking for Python installation...
python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo    - ERROR: Python is not installed or not in PATH.
    pause
    exit /b
)
echo    - Python found.
echo.
echo [2/4] Creating Python virtual environment in '.venv'...
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate
echo.
echo [3/4] Installing Python dependencies...
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo    - Python packages installed successfully.
echo.
echo [4/4] Checking for Go installation...
go version >nul 2>nul
if %errorlevel% neq 0 (
    echo    - WARNING: Go is not installed or not in PATH.
) else (
    echo    - Go found.
)
echo.
echo ===================================================
echo ===    Setup Complete                          ===
echo ===================================================
echo.
pause
