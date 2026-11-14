@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Instalando SIAMS Captura - solo la primera vez requiere internet.
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv 2>nul || python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
    echo No se pudo crear el entorno. Instala Python 3.11 o superior.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Fallo la instalacion de dependencias.
) else (
    echo Instalacion completa. Ahora abre INICIAR_OFFLINE.bat
)
pause
