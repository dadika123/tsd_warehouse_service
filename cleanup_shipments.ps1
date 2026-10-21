$ErrorActionPreference = "Stop"

$env:DJANGO_DEBUG = "true"
$env:DJANGO_SECRET_KEY = "django-insecure-tsd-warehouse-local"

Set-Location $PSScriptRoot
& "$PSScriptRoot\venv\Scripts\python.exe" manage.py cleanup_shipments *>> "$PSScriptRoot\cleanup.log"
