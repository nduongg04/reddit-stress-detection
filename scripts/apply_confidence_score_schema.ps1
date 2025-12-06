# Script to apply confidence_scores field to Cassandra schema (PowerShell)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Applying Confidence Score Schema Update" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Cassandra is running
Write-Host "1. Checking Cassandra container..." -ForegroundColor Yellow
$cassandraRunning = docker ps | Select-String "reddit-cassandra"
if (-not $cassandraRunning) {
    Write-Host "[X] Cassandra container is not running!" -ForegroundColor Red
    Write-Host "   Please start Cassandra first: docker-compose up -d cassandra" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Cassandra is running" -ForegroundColor Green
Write-Host ""

# Wait for Cassandra to be ready
Write-Host "2. Waiting for Cassandra to be ready..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 0
$ready = $false

while ($attempt -lt $maxAttempts) {
    try {
        $result = docker exec reddit-cassandra cqlsh -e "DESCRIBE KEYSPACES" 2>&1
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            Write-Host "[OK] Cassandra is ready" -ForegroundColor Green
            break
        }
    }
    catch {
        # Continue waiting
    }
    
    $attempt++
    Write-Host "   Waiting... ($attempt/$maxAttempts)" -ForegroundColor Gray
    Start-Sleep -Seconds 2
}

if (-not $ready) {
    Write-Host "[X] Cassandra is not responding after $maxAttempts attempts" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Apply schema change
Write-Host "3. Adding confidence_scores field to classified_posts_by_hour..." -ForegroundColor Yellow
$cqlCommand = @"
USE reddit_rt;
ALTER TABLE classified_posts_by_hour 
ADD confidence_scores map<text, double>;
"@

$result = docker exec reddit-cassandra cqlsh -e $cqlCommand 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Schema updated successfully" -ForegroundColor Green
}
else {
    Write-Host "[!] Note: Field might already exist (this is OK)" -ForegroundColor Yellow
}
Write-Host ""

# Verify schema
Write-Host "4. Verifying schema..." -ForegroundColor Yellow
$describeCommand = @"
USE reddit_rt;
DESCRIBE TABLE classified_posts_by_hour;
"@

$schemaOutput = docker exec reddit-cassandra cqlsh -e $describeCommand 2>&1
$hasField = $schemaOutput | Select-String "confidence_scores"

if ($hasField) {
    Write-Host ""
    Write-Host "[OK] confidence_scores field is present in schema" -ForegroundColor Green
}
else {
    Write-Host "[X] confidence_scores field not found in schema" -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Schema Update Complete!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Restart Spark containers:" -ForegroundColor White
Write-Host "   docker-compose restart spark-master spark-worker" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Restart Airflow containers:" -ForegroundColor White
Write-Host "   docker-compose restart airflow-webserver airflow-scheduler" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Enable DAG in Airflow UI:" -ForegroundColor White
Write-Host "   http://localhost:8082 (airflow/airflow)" -ForegroundColor Gray
Write-Host "   Toggle ON: vietnamese_absa_daily_retrain" -ForegroundColor Gray
Write-Host ""
