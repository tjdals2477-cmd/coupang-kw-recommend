@echo off
setlocal
set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
"%PYTHON_EXE%" -m pip install pyinstaller
if errorlevel 1 (
  echo [WARN] PyInstaller installation failed. Build skipped.
  exit /b 0
)
"%PYTHON_EXE%" -m PyInstaller --onefile --name coupang-kw-rec --collect-data coupang_kw_rec pyinstaller_entry.py
if errorlevel 1 (
  echo [WARN] PyInstaller build failed. Pipeline will continue.
  exit /b 0
)
echo Built dist\coupang-kw-rec.exe
exit /b 0
