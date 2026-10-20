@echo off
cd /d "%~dp0"
echo [1/3] Setting up Python environment...
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate
pip install -q -r requirements.txt
echo [2/3] Starting the Observatory app in a new window...
start "OS Observatory (keep open)" cmd /k "call .venv\Scripts\activate && python app.py"
echo [3/3] Starting Prometheus + Grafana (Docker)...
docker compose up -d
echo.
echo Ready:
echo   Live UI        http://localhost:5050
echo   Grafana        http://localhost:3000   (login: admin / admin)
echo   Prometheus     http://localhost:9090
pause
