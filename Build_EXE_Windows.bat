@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Install_Windows.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt "pyinstaller==6.22.3"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name Karname --icon "assets\karname.ico" --add-data "data;data" --add-data "assets;assets" --add-data "web;web" --collect-all cryptography launcher.py
if errorlevel 1 goto failed
echo Ready: dist\Karname.exe
pause
exit /b 0
:failed
echo Build failed. See the error above.
pause
exit /b 1
