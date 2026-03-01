@echo off
echo ============================================================
echo   PDF Chapter Splitter — Build to EXE
echo ============================================================
echo.

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install build dependencies (if not already)
pip install pyinstaller pywebview --quiet

REM Run the build script
python build.py

echo.
pause
