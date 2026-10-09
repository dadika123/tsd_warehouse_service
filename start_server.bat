@echo off
REM Запуск сервиса склада без консольного окна, лог в server.out.log.
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" manage.py runserver 0.0.0.0:8090 --noreload >> "%~dp0server.out.log" 2>&1
