@echo off
echo ============================================
echo  Building TallyCounter.exe
echo ============================================

REM Clean previous build artifacts
echo Cleaning previous builds...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

REM Run PyInstaller via the venv Python directly (avoids activate.bat path issues)
echo Running PyInstaller...
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -m PyInstaller TallyCounter.spec
) else (
    python -m PyInstaller TallyCounter.spec
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed. Check the output above for errors.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Build successful!
echo  Output: dist\TallyCounter.exe
echo ============================================
pause
