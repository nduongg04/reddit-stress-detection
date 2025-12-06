# Setup Script for Reddit Stress Detection - Retrain Pipeline
# Run this ONCE before starting the Airflow retrain pipeline

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Reddit Stress Detection - Retrain Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
Write-Host "Checking Python installation..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Python not found. Please install Python 3.9+" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Python installed: $pythonVersion" -ForegroundColor Green
Write-Host ""

# Check if virtual environment exists
Write-Host "Checking virtual environment..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "[OK] Virtual environment found" -ForegroundColor Green
}
else {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[X] Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Virtual environment created" -ForegroundColor Green
}
Write-Host ""

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1
Write-Host "[OK] Virtual environment activated" -ForegroundColor Green
Write-Host ""

# Install dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
Write-Host "  This may take 5-10 minutes..." -ForegroundColor Gray
pip install --upgrade pip -q
pip install -r requirements.txt -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Failed to install dependencies" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Dependencies installed" -ForegroundColor Green
Write-Host ""

# Check Docker
Write-Host "Checking Docker..." -ForegroundColor Yellow
$dockerVersion = docker --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Docker not found. Please install Docker Desktop" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Docker installed: $dockerVersion" -ForegroundColor Green

$dockerComposeVersion = docker-compose --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Docker Compose not found" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Docker Compose installed: $dockerComposeVersion" -ForegroundColor Green
Write-Host ""

# Check model files
Write-Host "Checking Vietnamese ABSA PhoBERT model..." -ForegroundColor Yellow
if (Test-Path "ml\models\vietnamese_absa_sentiment_phobert_v1\model.pt") {
    Write-Host "[OK] Model weights found" -ForegroundColor Green
}
else {
    Write-Host "[!] Model weights not found (model.pt)" -ForegroundColor Yellow
    Write-Host "  You may need to train the model first" -ForegroundColor Gray
}

if (Test-Path "ml\models\registry\registry.json") {
    Write-Host "[OK] Model registry initialized" -ForegroundColor Green
}
else {
    Write-Host "[!] Model registry not found" -ForegroundColor Yellow
    Write-Host "  It will be created automatically" -ForegroundColor Gray
}
Write-Host ""

# Check training data
Write-Host "Checking training data..." -ForegroundColor Yellow
if (Test-Path "ml\dataset\labeled") {
    $csvFiles = Get-ChildItem -Path "ml\dataset\labeled" -Filter "*.csv" -ErrorAction SilentlyContinue
    if ($csvFiles.Count -gt 0) {
        Write-Host "[OK] Training data found ($($csvFiles.Count) CSV files)" -ForegroundColor Green
    }
    else {
        Write-Host "[!] No CSV files in ml/dataset/labeled/" -ForegroundColor Yellow
        Write-Host "  You need labeled data for retraining" -ForegroundColor Gray
    }
}
else {
    Write-Host "[!] Training data directory not found" -ForegroundColor Yellow
    Write-Host "  Creating directory..." -ForegroundColor Gray
    New-Item -ItemType Directory -Path "ml\dataset\labeled" -Force | Out-Null
    Write-Host "[OK] Directory created" -ForegroundColor Green
}
Write-Host ""

# Summary
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Start Docker services:" -ForegroundColor White
Write-Host "     docker-compose up -d" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Setup Ollama model (one-time):" -ForegroundColor White
Write-Host "     .\scripts\setup_ollama.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Access Airflow UI:" -ForegroundColor White
Write-Host "     http://localhost:8082 (airflow/airflow)" -ForegroundColor Gray
Write-Host ""
Write-Host "  4. Enable the retrain DAG:" -ForegroundColor White
Write-Host "     vietnamese_absa_daily_retrain" -ForegroundColor Gray
Write-Host ""
