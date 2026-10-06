@echo off
REM ---------------------------------------------------------------------------
REM  Build Mind Map Viewer for Windows.
REM    build_windows.bat            folder build  + release\*.zip (+ Setup.exe if Inno Setup is installed)
REM    build_windows.bat --onefile  single MindMapViewer.exe
REM    build_windows.bat --clean    clean rebuild
REM  Output goes to dist\ and release\. Needs Python 3.9+ (python.org, "Add to PATH").
REM ---------------------------------------------------------------------------
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% build.py %*
if errorlevel 1 (
    echo.
    echo BUILD FAILED
    pause
    exit /b 1
)
echo.
echo Build finished - see the release folder.
pause
