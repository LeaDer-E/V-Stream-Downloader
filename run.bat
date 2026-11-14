@echo off
chcp 65001 >nul
title V-Stream Downloader Pro v5.1
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py %*
) else (
    python main.py %*
)
