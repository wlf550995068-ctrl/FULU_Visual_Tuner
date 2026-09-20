@echo off
setlocal
cd /d "%~dp0"
if not exist ".cache\tmp" mkdir ".cache\tmp"
if not exist ".cache\pip" mkdir ".cache\pip"
set "TEMP=%~dp0.cache\tmp"
set "TMP=%TEMP%"
set "PIP_CACHE_DIR=%~dp0.cache\pip"
set "PYTHONDONTWRITEBYTECODE=1"
if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -c "import moderngl, moderngl_window, imgui_bundle, numpy, PIL" >nul 2>&1
if errorlevel 1 (
    .venv\Scripts\python.exe -m pip install -r requirements-lock.txt
    if errorlevel 1 goto failed
)
.venv\Scripts\python.exe simulator.py --window pyglet %*
if errorlevel 1 goto failed
exit /b 0
:failed
echo Startup failed. Please keep the error text.
pause
exit /b 1

