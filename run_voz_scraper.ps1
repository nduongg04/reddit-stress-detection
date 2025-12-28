# Run Vozforums.com Scraper (PowerShell)
# 
# Usage:
#   .\run_voz_scraper.ps1                    # Scrape to file only
#   .\run_voz_scraper.ps1 -Kafka             # Scrape and send to Kafka
#   .\run_voz_scraper.ps1 -TargetPosts 5000  # Custom target

param(
    [int]$TargetPosts = 10000,
    [switch]$Kafka,
    [int]$MaxWorkers = 5,
    [double]$Delay = 1.0
)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Vozforums.com Scraper" -ForegroundColor Cyan
Write-Host "  Target: $TargetPosts posts" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "[1/4] Activating virtual environment..." -ForegroundColor Green
    & .venv\Scripts\Activate.ps1
} else {
    Write-Host "[!] Virtual environment not found at .venv" -ForegroundColor Red
    Write-Host "    Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    & .venv\Scripts\Activate.ps1
}

# Install dependencies
Write-Host "[2/4] Installing dependencies..." -ForegroundColor Green
pip install -q -r producers\voz_scraper\requirements.txt
pip install -q -r producers\reddit_producer\requirements.txt

# Create data directory
Write-Host "[3/4] Creating data directory..." -ForegroundColor Green
New-Item -ItemType Directory -Force -Path "data" | Out-Null

# Build command
$cmd = "python producers\voz_scraper\main.py --target-posts $TargetPosts --max-workers $MaxWorkers --delay $Delay"

if ($Kafka) {
    Write-Host "[*] Kafka mode enabled - checking services..." -ForegroundColor Yellow
    
    # Check if Kafka is running
    $kafkaRunning = docker ps --filter "name=reddit-kafka" --format "{{.Names}}" | Select-String "reddit-kafka"
    
    if ($kafkaRunning) {
        Write-Host "    ✓ Kafka is running" -ForegroundColor Green
        $cmd += " --kafka"
    } else {
        Write-Host "    ✗ Kafka is not running!" -ForegroundColor Red
        Write-Host "    Starting Kafka services..." -ForegroundColor Yellow
        docker-compose up -d zookeeper kafka cassandra
        Write-Host "    Waiting 30s for Kafka to be ready..." -ForegroundColor Yellow
        Start-Sleep -Seconds 30
        $cmd += " --kafka"
    }
}

# Run scraper
Write-Host "[4/4] Starting scraper..." -ForegroundColor Green
Write-Host ""
Write-Host "Command: $cmd" -ForegroundColor Cyan
Write-Host ""

Invoke-Expression $cmd

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Scraping Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
