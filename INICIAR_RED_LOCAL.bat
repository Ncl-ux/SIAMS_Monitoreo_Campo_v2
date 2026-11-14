@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Primero ejecuta INSTALAR_PRIMERA_VEZ.bat con internet.
    pause
    exit /b 1
)
echo ===============================================
echo SIAMS - acceso local por Wi-Fi o hotspot privado
 echo Mantén este computador encendido y en la red.
echo Consulta la IP de este equipo con ipconfig.
echo Desde el telefono abre http://TU_IP_LOCAL:8501
 echo Evita redes publicas: no existe autenticacion en esta demo.
echo ===============================================
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --browser.gatherUsageStats false
pause
