@echo off
REM =====================================================================
REM  Build MSIX - one-click packaging.
REM
REM  Double-click to produce an unsigned MSIX at msix\output\.
REM  First run takes about 3 minutes. Subsequent builds about 1 minute.
REM
REM  Requirements:
REM    - Python 3.12 installed (see Run School Tool.bat)
REM    - Developer Mode enabled in Windows Settings (to sideload unsigned)
REM =====================================================================

setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo ============================================================
echo   School Tool - MSIX builder
echo ============================================================
echo.

REM --- Ensure venv exists ----------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [*] No venv found. Run "Run School Tool.bat" first to set one up.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"

REM --- Invoke the PowerShell build script ------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -File ".\msix\build_msix_package.ps1" -Version "2.0.0-alpha" -NoSign
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo ============================================================
    echo   MSIX built successfully.
    echo   Output: msix\output\SchoolTool_v2.0.0-alpha.msix
    echo.
    echo   To install:
    echo     Add-AppxPackage  msix\output\SchoolTool_v2.0.0-alpha.msix  -AllowUnsigned
    echo   Developer Mode must be enabled in Windows Settings.
    echo ============================================================
) else (
    echo ============================================================
    echo   Build failed - exit code %EXIT_CODE%.
    echo   See messages above.
    echo ============================================================
)

pause
endlocal
exit /b %EXIT_CODE%
