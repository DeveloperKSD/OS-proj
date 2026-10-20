@echo off
cd /d "%~dp0"
title OS Observatory - Docker launcher
where docker >nul 2>nul
if errorlevel 1 (
  echo ERROR: Docker Desktop is not installed or Docker is not in PATH.
  pause
  exit /b 1
)
docker info >nul 2>nul
if errorlevel 1 (
  echo ERROR: Open Docker Desktop and wait until its engine is running, then retry.
  pause
  exit /b 1
)
echo Building and starting OS Observatory containers...
docker compose up --build -d
if errorlevel 1 (
  echo Startup failed. Check the error above.
  pause
  exit /b 1
)
echo Opening the app in your browser...
timeout /t 3 /nobreak >nul
start "" "http://localhost:5050"
echo.
echo App:        http://localhost:5050
echo Grafana:    http://localhost:3000
echo Prometheus: http://localhost:9090/targets
echo Containers keep running after this window closes.
pause
