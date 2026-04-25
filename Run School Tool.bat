@echo off
REM =====================================================================
REM  Run School Tool - one-click launcher.
REM  Double-click me from Windows Explorer.
REM  This window will ALWAYS stay open at the end so you can read output.
REM =====================================================================

setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo ============================================================
echo   School Tool - launcher
echo ============================================================
echo.

REM --- 1. Locate Python 3.12 -------------------------------------------
where py >nul 2>nul
if errorlevel 1 goto :need_python

py -3.12 -c "import sys" >nul 2>nul
if errorlevel 1 goto :need_python

goto :have_python

:need_python
echo [x] Python 3.12 is not installed on this computer.
echo.
echo     Install options:
echo       Option A: open PowerShell and run:
echo                   winget install Python.Python.3.12
echo       Option B: download from python.org and tick
echo                 "Add python.exe to PATH" during install.
echo.
echo     Opening the Python download page now...
start "" "https://www.python.org/downloads/release/python-3129/"
echo.
pause
exit /b 1

:have_python
echo [*] Python 3.12 found.

REM --- 2. Create venv if missing ---------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [*] First run - creating local virtual environment at .venv\
    py -3.12 -m venv .venv
    if errorlevel 1 (
        echo.
        echo [x] Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

REM --- 3. Activate + install deps if needed ----------------------------
call ".venv\Scripts\activate.bat"

set "MARKER=.venv\.deps-installed-v1"
if not exist "%MARKER%" (
    echo [*] Installing dependencies ^(one-time, about 60 s^)...
    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"
    if errorlevel 1 (
        echo.
        echo [x] Dependency install failed. See messages above.
        pause
        exit /b 1
    )
    echo.> "%MARKER%"
    echo [*] Dependencies ready.
)

REM --- 4. Launch -------------------------------------------------------
echo.
echo [*] Starting School Tool...
echo     If the window does not appear, the error will print here.
echo     This cmd window will stay open after the app exits.
echo.
echo ------------------------------------------------------------
python -u app.py
set "EXIT_CODE=%ERRORLEVEL%"
echo ------------------------------------------------------------

echo.
if "%EXIT_CODE%"=="0" (
    echo   App exited normally ^(code 0^).
    echo   If no window appeared, copy the output above and send it to me.
) else (
    echo   App exited with error code %EXIT_CODE%.
    echo   Copy the traceback above and send it to me.
)
echo.
echo Press any key to close this window.
pause >nul

endlocal
exit /b %EXIT_CODE%
