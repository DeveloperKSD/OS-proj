@echo off
cd /d "%~dp0"
docker compose down
echo OS Observatory containers stopped.
pause
