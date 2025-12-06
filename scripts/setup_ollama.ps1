# Script to pull Ollama model for active learning validation

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Ollama Model Setup for Active Learning" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Wait for Ollama service to be ready
Write-Host "Waiting for Ollama service..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 0

while ($attempt -lt $maxAttempts) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -Method GET -TimeoutSec 2 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            break
        }
    }
    catch {
        Start-Sleep -Seconds 2
        Write-Host "  Waiting for Ollama..." -ForegroundColor Gray
        $attempt++
    }
}

if ($attempt -eq $maxAttempts) {
    Write-Host "✗ Ollama service not ready after 60 seconds" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Ollama service is ready" -ForegroundColor Green

# Pull llama3.1:8b model (used by DAG)
Write-Host ""
Write-Host "Pulling llama3.1:8b model (this may take a while)..." -ForegroundColor Yellow
docker exec reddit-ollama ollama pull llama3.1:8b

Write-Host ""
Write-Host "✓ Ollama model setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Available models:" -ForegroundColor Cyan
docker exec reddit-ollama ollama list

Write-Host ""
Write-Host "You can now run the Airflow DAG for retraining." -ForegroundColor Cyan
