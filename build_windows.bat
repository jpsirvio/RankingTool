@echo off
REM =============================================================================
REM build_windows.bat — Build a standalone RankingTool.exe with PyInstaller
REM
REM Requirements:
REM   - Python 3.8+ installed and available as "python" on PATH
REM     Download from https://www.python.org/downloads/
REM     During install, tick "Add Python to PATH"
REM
REM What this script does:
REM   1. Creates a build virtual environment at .\build_venv\
REM   2. Installs PyQt5 + PyInstaller into it
REM   3. Runs PyInstaller with RankingTool.spec
REM   4. Reports where the output lives
REM
REM Output:
REM   dist\RankingTool\RankingTool.exe
REM   (distribute the entire dist\RankingTool\ folder)
REM
REM Run this script once whenever you want to produce a new build.
REM =============================================================================

setlocal EnableDelayedExpansion

REM ── Locate Python ──────────────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: "python" not found on PATH.
    echo Install Python 3.8+ from https://www.python.org/downloads/
    echo and make sure "Add Python to PATH" is ticked during installation.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo Found: %PY_VER%

REM ── Create build venv ──────────────────────────────────────────────────────
set VENV=build_venv

if not exist "%VENV%\Scripts\activate.bat" (
    echo Creating build virtual environment ...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Done.
)

REM ── Activate venv ──────────────────────────────────────────────────────────
call "%VENV%\Scripts\activate.bat"

REM ── Install / upgrade dependencies ─────────────────────────────────────────
echo Installing dependencies ...
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
pip install --quiet --upgrade pyinstaller
echo Dependencies ready.

REM ── Clean previous build artefacts ────────────────────────────────────────
echo Cleaning previous build ...
if exist build\RankingTool  rmdir /s /q build\RankingTool
if exist dist\RankingTool   rmdir /s /q dist\RankingTool

REM ── Run PyInstaller ────────────────────────────────────────────────────────
echo Running PyInstaller ...
pyinstaller RankingTool.spec

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller failed. See output above for details.
    pause
    exit /b 1
)

REM ── Copy end-user launcher into dist folder ───────────────────────────────
if exist "launch_windows.bat" (
    copy /y "launch_windows.bat" "dist\RankingTool\launch_windows.bat" >nul
    echo Copied launch_windows.bat into dist\RankingTool\
)

REM ── Report result ──────────────────────────────────────────────────────────
echo.
echo ============================================================
echo  Build successful!
echo  Executable:  dist\RankingTool\RankingTool.exe
echo  Launcher:    dist\RankingTool\launch_windows.bat
echo  Distribute:  the entire dist\RankingTool\ folder
echo ============================================================
echo.

REM Deactivate venv
call deactivate

pause
