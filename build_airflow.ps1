# Quick build script for Airflow ML service (PowerShell)

Write-Host "======================================================================" -ForegroundColor Blue
Write-Host "Building Airflow ML Service (reddit-airflow-ml)" -ForegroundColor Blue
Write-Host "======================================================================" -ForegroundColor Blue
Write-Host ""

Write-Host "[1/3] Building Airflow image with ML dependencies..." -ForegroundColor Yellow
Write-Host "      This may take 10-15 minutes (installing torch/transformers)..." -ForegroundColor Gray
Write-Host ""

docker-compose build airflow-webserver airflow-scheduler

Write-Host ""
Write-Host "[2/3] Verifying image..." -ForegroundColor Yellow
docker images | Select-String "reddit-airflow-ml"

Write-Host ""
Write-Host "[3/3] Starting services..." -ForegroundColor Yellow
docker-compose up -d airflow-postgres airflow-webserver airflow-scheduler ollama

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Blue
Write-Host "✓ Build Complete!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Blue
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Pull Ollama model (one-time):" -ForegroundColor White
Write-Host "   docker exec reddit-ollama ollama pull llama3.1:8b" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Access Airflow UI:" -ForegroundColor White
Write-Host "   http://localhost:8082 (airflow/airflow)" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Enable DAG: vietnamese_absa_daily_retrain" -ForegroundColor White
Write-Host ""
Write-Host "4. Verify ML dependencies:" -ForegroundColor White
Write-Host "   docker exec reddit-airflow-scheduler python -c 'import torch; import transformers; print(\`"OK\`")'" -ForegroundColor Gray
Write-Host ""
