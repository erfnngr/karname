@echo off
setlocal
cd /d "%~dp0"
if exist "Karname.exe" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install.ps1"
  if errorlevel 1 pause
  exit /b
)
echo Preparing Karname source. Internet and Python 3.10-3.13 are required.
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto failed
)
rem Always check/install requirements; an empty venv is not a complete install.
".venv\Scripts\python.exe" -m ensurepip --upgrade
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "import PySide6.QtWidgets, jdatetime, openpyxl, bs4, requests"
if errorlevel 1 goto failed
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0launcher.py" --show
exit /b 0
:failed
echo Installation failed. Use the ready-made Windows EXE package, or check Python and internet.
pause
exit /b 1
