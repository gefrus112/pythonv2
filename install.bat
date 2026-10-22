@echo off
setlocal EnableExtensions
color 1F
title Python v2 + PyHope installer

echo.
echo  =============================================
echo   Python v2 0.3 + PyHope Game Engine
 echo  Windows installer - no pygame required
 echo  =============================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3.10 or newer was not found.
  echo Install Python from https://www.python.org/downloads/
  echo Check "Add Python to PATH", then run this file again.
  pause
  exit /b 1
)

for /f "tokens=2" %%V in ('py --version 2^>^&1') do set PYVERSION=%%V
echo [1/4] Found Python %PYVERSION%

set "INSTALL_DIR=%LOCALAPPDATA%\PythonV2"
set "ZIP_FILE=%TEMP%\pythonv2-main.zip"
set "UNPACK_DIR=%TEMP%\pythonv2-install"

echo [2/4] Downloading Python v2 from GitHub...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/gefrus112/pythonv2/archive/refs/heads/main.zip' -OutFile '%ZIP_FILE%'"
if errorlevel 1 goto :download_error

if exist "%UNPACK_DIR%" rmdir /s /q "%UNPACK_DIR%"
mkdir "%UNPACK_DIR%" >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Expand-Archive -Force '%ZIP_FILE%' '%UNPACK_DIR%'"
if errorlevel 1 goto :download_error

if exist "%INSTALL_DIR%" rmdir /s /q "%INSTALL_DIR%"
move "%UNPACK_DIR%\pythonv2-main" "%INSTALL_DIR%" >nul

echo [3/4] Installing pyv2 and PyHope for this user...
py -m pip install --user --upgrade "%INSTALL_DIR%"
if errorlevel 1 goto :pip_error

echo [4/4] Running engine checks...
py -m pyv2 --version
py -m pyhope --check
if errorlevel 1 goto :check_error

echo.
echo  SUCCESS! Python v2 and PyHope are installed.
echo.
echo  Try these commands:
echo    pyv2
 echo    pyv2 "%INSTALL_DIR%\examples\hello.pyv2"
echo    pyhope --demo
 echo.
echo  If pyv2 is not on PATH, use: py -m pyv2
 echo  Install folder: %INSTALL_DIR%
echo.
pause
exit /b 0

:download_error
echo [ERROR] Download failed. Check your internet connection and try again.
pause
exit /b 1

:pip_error
echo [ERROR] Python could not install the local package.
echo Try: py -m pip install --user --upgrade "%INSTALL_DIR%"
pause
exit /b 1

:check_error
echo [ERROR] Installation completed, but the self-check failed.
echo Open an issue: https://github.com/gefrus112/pythonv2/issues
pause
exit /b 1
