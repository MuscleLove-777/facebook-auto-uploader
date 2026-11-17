@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "ML_FACEBOOK_RUN_LOG=%~1"
if not defined ML_FACEBOOK_RUN_LOG set "ML_FACEBOOK_RUN_LOG=facebook_post_log.txt"
".venv\Scripts\python.exe" -u auto_post_facebook.py >> "%ML_FACEBOOK_RUN_LOG%" 2>&1
set "ML_FACEBOOK_CHILD_EXIT=%ERRORLEVEL%"
exit /b %ML_FACEBOOK_CHILD_EXIT%
