# =============================================
# SportsDB Dev CLI - Final Clean Version
# =============================================
function Dev-Help {
    Write-Host "`nSportsDB Dev CLI" -ForegroundColor Cyan
    Write-Host "========================" -ForegroundColor Cyan
    Write-Host "  .\dev.ps1 install   -> Install dependencies"
    Write-Host "  .\dev.ps1 start     -> Start backend"
    Write-Host "  .\dev.ps1 db-test   -> Test database"
    Write-Host "  .\dev.ps1 reset     -> Reset environment"
    Write-Host "  .\dev.ps1 ingest    -> Run data ingestion worker"
}

function Install-Dev {
    Write-Host "`nInstalling dependencies..." -ForegroundColor Green
    if (-not (Test-Path "venv")) { python -m venv venv }
    & .\venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install fastapi uvicorn[standard] sqlalchemy psycopg2-binary python-dotenv requests
    Write-Host "Installation complete!" -ForegroundColor Green
}

function Start-Dev {
    Write-Host "`nCleaning cache..." -ForegroundColor Yellow
    Get-ChildItem -Recurse -Include __pycache__,*.pyc -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue
    Write-Host "`nStarting SportsDB backend..." -ForegroundColor Cyan
    if (-not $env:VIRTUAL_ENV) {
        & .\venv\Scripts\Activate.ps1
    }
    python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
}

function Db-Test {
    Write-Host "`nTesting database..." -ForegroundColor Cyan
    if (-not $env:VIRTUAL_ENV) { & .\venv\Scripts\Activate.ps1 }
    python -c "from dotenv import load_dotenv; import os; load_dotenv(); url = os.getenv('DATABASE_URL'); print('URL:', url); exit(1) if not url else None; from sqlalchemy import create_engine; engine = create_engine(url); conn = engine.connect(); print('Connected successfully!'); conn.close()"
}

function Ingest-Dev {
    Write-Host "`nRunning data ingestion worker..." -ForegroundColor Cyan
    if (-not $env:VIRTUAL_ENV) { & .\venv\Scripts\Activate.ps1 }
    python -m app.workers.run_ingestion
}

function Reset-Dev {
    Write-Host "`nResetting environment..." -ForegroundColor Yellow
    if (Test-Path "venv") { Remove-Item -Recurse -Force venv }
    Write-Host "Reset complete" -ForegroundColor Green
}

$command = $args[0]
switch ($command) {
    "start"   { Start-Dev }
    "install" { Install-Dev }
    "db-test" { Db-Test }
    "ingest"  { Ingest-Dev }
    "reset"   { Reset-Dev }
    default   { Dev-Help }
}
