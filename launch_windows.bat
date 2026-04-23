@echo off
REM =============================================================================
REM launch_windows.bat — End-user launcher for Ranking Tool on Windows
REM
REM This script requires NO Python installation.  It simply runs the
REM pre-built RankingTool.exe that ships alongside it.
REM
REM Usage:
REM   Double-click launch_windows.bat
REM   (or double-click RankingTool.exe directly — both work)
REM
REM If you receive this as part of a distributed folder the structure is:
REM   RankingTool\
REM   ├── RankingTool.exe       <- the application
REM   ├── launch_windows.bat    <- this file (optional convenience launcher)
REM   └── ...                   <- supporting files bundled by PyInstaller
REM
REM The "projects" folder where your ranking data is saved will be created
REM automatically next to this launcher on first run.
REM =============================================================================

setlocal

REM Resolve the directory this .bat lives in so paths are always correct
REM regardless of where you launch it from.
set "SCRIPT_DIR=%~dp0"
set "EXE=%SCRIPT_DIR%RankingTool.exe"

REM ── Sanity check ─────────────────────────────────────────────────────────────
if not exist "%EXE%" (
    echo ERROR: RankingTool.exe not found at:
    echo   %EXE%
    echo.
    echo This launcher must be placed in the same folder as RankingTool.exe.
    echo If you are a developer, run build_windows.bat first to produce the binary.
    pause
    exit /b 1
)

REM ── Launch ───────────────────────────────────────────────────────────────────
cd /d "%SCRIPT_DIR%"
start "" "%EXE%"
