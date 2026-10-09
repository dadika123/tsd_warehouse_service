@echo off
REM Запуск Django-сервиса склада на всех интерфейсах, порт 8001.
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" manage.py runserver 0.0.0.0:8001
