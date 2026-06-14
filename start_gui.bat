@echo off
cd /d %~dp0
where pythonw.exe >nul 2>&1
if %errorlevel%==0 (
    start "" pythonw.exe "%~dp0foxair_phnix_controll.py"
) else (
    start "" python.exe "%~dp0foxair_phnix_controll.py"
)
exit /b
