@echo off
setlocal
cd /d "%~dp0"
if exist "Karname.exe" (
  start "" "%~dp0Karname.exe" --show
  exit /b 0
)
if not exist ".venv\Scripts\python.exe" goto install
".venv\Scripts\python.exe" -c "import PySide6.QtWidgets,jdatetime,openpyxl,bs4,requests" >nul 2>nul
if errorlevel 1 goto install
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0launcher.py" --show
exit /b 0
:install
call "%~dp0Install_Windows.bat"
