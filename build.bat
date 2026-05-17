@echo off
rem ============================================================
rem  BEFORE BUILDING A RELEASE - bump version in BOTH places:
rem    core\config.py  ->  VERSION = "x.y.z"
rem    installer.iss   ->  AppVersion=x.y.z
rem ============================================================
setlocal

echo === Step 1: PyInstaller ===
call venv\Scripts\activate
pyinstaller main.py --onefile --noconsole --name MCAddonCompanion --clean
if errorlevel 1 (
    echo PyInstaller failed.
    exit /b 1
)

echo === Step 2: Inno Setup ===
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    echo Inno Setup not found at %ISCC%
    exit /b 1
)
%ISCC% installer.iss
if errorlevel 1 (
    echo Inno Setup failed.
    exit /b 1
)

echo === Build complete ===
echo Installer: Output\MCAddonCompanion-Setup.exe
endlocal
