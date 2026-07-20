@echo off
chcp 65001 >nul
cd /d "%~dp0"
".venv\Scripts\python.exe" -u token_refresh_local.py >> facebook_token_log.txt 2>&1
