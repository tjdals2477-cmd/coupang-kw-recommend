#!/usr/bin/env sh
python -m pip install pyinstaller || {
  echo "[WARN] PyInstaller installation failed. Build skipped."
  exit 0
}
python -m PyInstaller --onefile --name coupang-kw-rec --collect-data coupang_kw_rec pyinstaller_entry.py || {
  echo "[WARN] PyInstaller build failed. Pipeline will continue."
  exit 0
}
echo "Built dist/coupang-kw-rec"
exit 0
