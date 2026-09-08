@echo off
REM Doble clic para jugar. Si tienes varias camaras, prueba: jugar.bat --camera 1
cd /d "%~dp0"
python main.py %*
pause
