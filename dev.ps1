# =============================================
# SportsDB Dev CLI - dev.ps1
# =============================================

function Dev-Help {
    Write-Host "`n⚡ SportsDB Dev CLI" -ForegroundColor Cyan
    Write-Host "========================`n" -ForegroundColor Cyan
    Write-Host "dev start     -> start backend" -ForegroundColor White
    Write-Host "dev install   -> install dependencies" -ForegroundColor White
    Write-Host "dev reset     -> clean cache + reset env" -ForegroundColor White
    Write-Host "dev db-test   -> test database connection" -ForegroundColor White
    Write-Host ""
}

function Install-Dev {
    Write-Host "`n📦 Installing dependencies..." -ForegroundColor Green
    
    # Create virtual environment if it doesn't exist
    if (-not (Test-Path "venv")) {
        Write-Host "Creating virtual environment..." -ForegroundColor Yellow
        python -m venv venv
        Write-Host "✅ Virtual environment created" -ForegroundColor Green
    }
    
    # Activate venv
    & .\venv\Scripts\Activate.ps1
    
    # Upgrade pip and install requirements
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    
    Write-Host "✅ Dependencies installed successfully!" -ForegroundColor Green
}

function Start-Dev {
    Write-Host "`n🧹 Cleaning Python cache..." -ForegroundColor Yellow
    Get-ChildItem -Recurse -Include __pycache__,*.pyc -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue
    Write-Host "✅ Cleanup complete" -ForegroundColor Green
    
    Write-Host "`n🚀 Starting backend server..." -ForegroundColor Cyan
    
    # Ensure virtual environment is activated
    if (-not $env:VIRTUAL_ENV) {
        if (Test-Path "venv\Scripts\Activate.ps1") {
            & .\venv\Scripts\Activate.ps1
            Write-Host "✅ Virtual environment activated" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Virtual environment not found. Installing first..." -ForegroundColor Yellow
            Install-Dev
        }
    }
    
    # Start the FastAPI server
    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
}

function Reset-Dev {
    Write-Host "`n🔄 Resetting development environment..." -ForegroundColor Yellow
    if (Test-Path "venv") { 
        Remove-Item -Recurse -Force venv 
        Write-Host "✅ Removed virtual environment" -ForegroundColor Green
    }
    Write-Host "✅ Reset complete. Run '.\dev.ps1 install' next." -ForegroundColor Green
}

function Db-Test {
    Write-Host "`n🧪 Testing database connection..." -ForegroundColor Cyan
    # TODO: Add your actual database test here later
    python -c "
import sys
print('✅ Python is working')
print('Database test placeholder - configure later')
" 
}

# ===================== MAIN CLI =====================
$command = $args[0]

switch ($command) {
    "start"   { Start-Dev }
    "install" { Install-Dev }
    "reset"   { Reset-Dev }
    "db-test" { Db-Test }
    default   { Dev-Help }
}