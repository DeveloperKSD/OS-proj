@echo off
cd /d "%~dp0"
docker compose down
echo Close the "OS Observatory" window to stop the app.
pause
