@chcp 65001 >nul
@echo off
setlocal enabledelayedexpansion

title V-Stream Downloader Pro - Build Standalone Python EXE

echo =====================================================================
echo   V-Stream Downloader Pro v5.1.0 - Standalone EXE Builder (PyInstaller)
echo =====================================================================
echo.

cd /d "%~dp0"

set "PY_EXE=python"
if exist ".venv\Scripts\python.exe" set "PY_EXE=.venv\Scripts\python.exe"
if exist "venv\Scripts\python.exe" set "PY_EXE=venv\Scripts\python.exe"

echo [*] Using Python interpreter: %PY_EXE%
echo [*] Cleaning previous build artifacts...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "V-Stream-Downloader.spec" del /f /q "V-Stream-Downloader.spec"

echo [*] Running build_exe.py (bundling full Python Standard Library + yt-dlp + EJS + SSL certs)...
"%PY_EXE%" build_exe.py

if %errorlevel% neq 0 (
    echo [!] Build failed! Make sure requirements are installed:
    echo     "%PY_EXE%" -m pip install -r requirements-dev.txt
    pause
    exit /b %errorlevel%
)

echo.
echo =====================================================================
echo   SUCCESS! Standalone EXE is ready at:
echo   dist\V-Stream-Downloader\V-Stream-Downloader.exe
echo =====================================================================
pause
exit /b 0
