@echo off
cd /d d:\app_file\vpn_tunnel\backend
echo Starting VPN Tunnel API Server on port 8080... > server_log.txt 2>&1
echo. >> server_log.txt 2>&1
D:\app_file\vpn_tunnel\backend\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8080 >> server_log.txt 2>&1
echo. >> server_log.txt 2>&1
echo Server stopped. >> server_log.txt 2>&1
type server_log.txt
pause
