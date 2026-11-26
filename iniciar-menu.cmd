@echo off
setlocal
cd /d "%~dp0"
echo Iniciando el menu de yt-dlp...
python --version >nul 2>&1
if errorlevel 1 goto python_missing
python -u "%~dp0menu_yt_dlp.py"
if errorlevel 1 echo El menu termino con un error. Revisa el mensaje anterior.
goto finish
:python_missing
echo No se encontro Python. Instala Python 3.11 o superior y agregalo al PATH.
:finish
echo.
pause
