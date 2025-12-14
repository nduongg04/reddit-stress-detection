# Monitor Vietnamese ABSA Retrain Pipeline
# This script triggers a DAG run and monitors all 7 tasks until completion

Write-Host "=== Vietnamese ABSA Retrain Pipeline Monitor ===" -ForegroundColor Cyan
Write-Host ""

# Check if Cassandra is running
Write-Host "[1/8] Checking Cassandra status..." -ForegroundColor Yellow
$cassandraStatus = docker ps --filter "name=cassandra" --format "{{.Status}}"
if ($cassandraStatus -match "healthy") {
    Write-Host "  ✓ Cassandra is healthy" -ForegroundColor Green
} elseif ($cassandraStatus -match "Up") {
    Write-Host "  ⚠ Cassandra is up but not yet healthy, waiting 20s..." -ForegroundColor Yellow
    Start-Sleep -Seconds 20
} else {
    Write-Host "  ✗ Cassandra is not running, starting..." -ForegroundColor Red
    docker start reddit-cassandra
    Write-Host "  Waiting 30s for Cassandra to be ready..." -ForegroundColor Yellow
    Start-Sleep -Seconds 30
}

# Trigger new DAG run
Write-Host ""
Write-Host "[2/8] Triggering new DAG run..." -ForegroundColor Yellow
$triggerOutput = docker exec reddit-airflow-scheduler airflow dags trigger vietnamese_absa_daily_retrain 2>&1
Write-Host "  ✓ DAG triggered" -ForegroundColor Green

# Wait for run to start
Write-Host ""
Write-Host "[3/8] Waiting for DAG run to start (10s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Get latest run ID
Write-Host ""
Write-Host "[4/8] Getting latest run ID..." -ForegroundColor Yellow
$runId = docker exec reddit-airflow-scheduler bash -c "cd /opt/airflow/logs/dag_id=vietnamese_absa_daily_retrain && ls -t | head -1" 2>&1
$runId = $runId -replace "run_id=", ""
Write-Host "  Run ID: $runId" -ForegroundColor Cyan

$logBase = "/opt/airflow/logs/dag_id=vietnamese_absa_daily_retrain/run_id=$runId"

# Define tasks
$tasks = @(
    @{Name="fetch_recent_posts"; DisplayName="Fetch Recent Posts"; EstimatedTime=5},
    @{Name="run_inference"; DisplayName="Run Inference"; EstimatedTime=240},
    @{Name="select_uncertain_predictions"; DisplayName="Select Uncertain Predictions"; EstimatedTime=30},
    @{Name="validate_with_ollama"; DisplayName="Validate with Ollama"; EstimatedTime=300},
    @{Name="retrain_model"; DisplayName="Retrain Model"; EstimatedTime=1800},
    @{Name="update_model_registry"; DisplayName="Update Model Registry"; EstimatedTime=10},
    @{Name="send_metrics"; DisplayName="Send Metrics"; EstimatedTime=5}
)

Write-Host ""
Write-Host "[5/8] Monitoring pipeline execution..." -ForegroundColor Yellow
Write-Host ""

$totalTasks = $tasks.Count
$completedTasks = 0

foreach ($task in $tasks) {
    $taskNum = $completedTasks + 1
    Write-Host "[$taskNum/$totalTasks] Task: $($task.DisplayName)" -ForegroundColor Cyan
    Write-Host "  Estimated time: $($task.EstimatedTime)s" -ForegroundColor Gray
    
    $logPath = "$logBase/task_id=$($task.Name)/attempt=1.log"
    $maxWait = $task.EstimatedTime + 60  # Add 60s buffer
    $waited = 0
    $checkInterval = 15
    
    # Wait for task to start
    while ($waited -lt $maxWait) {
        $logExists = docker exec reddit-airflow-scheduler test -f $logPath 2>&1
        if ($LASTEXITCODE -eq 0) {
            break
        }
        Start-Sleep -Seconds 5
        $waited += 5
        if ($waited % 30 -eq 0) {
            Write-Host "  ... waiting for task to start ($waited`s)" -ForegroundColor Gray
        }
    }
    
    if ($waited -ge $maxWait) {
        Write-Host "  ✗ Task did not start within expected time" -ForegroundColor Red
        break
    }
    
    # Monitor task execution
    $taskCompleted = $false
    while ($waited -lt $maxWait) {
        Start-Sleep -Seconds $checkInterval
        $waited += $checkInterval
        
        # Check log for completion markers
        $logTail = docker exec reddit-airflow-scheduler tail -20 $logPath 2>&1
        
        if ($logTail -match "Marking task as SUCCESS") {
            Write-Host "  ✓ Task completed successfully" -ForegroundColor Green
            $taskCompleted = $true
            $completedTasks++
            break
        } elseif ($logTail -match "Marking task as FAILED" -or $logTail -match "ERROR - Task failed") {
            Write-Host "  ✗ Task failed!" -ForegroundColor Red
            Write-Host ""
            Write-Host "Last 30 lines of log:" -ForegroundColor Yellow
            docker exec reddit-airflow-scheduler tail -30 $logPath
            $taskCompleted = $false
            break
        } elseif ($logTail -match "UP_FOR_RETRY") {
            Write-Host "  ⚠ Task is retrying..." -ForegroundColor Yellow
        }
        
        if ($waited % 60 -eq 0) {
            Write-Host "  ... task running ($waited`s / $maxWait`s)" -ForegroundColor Gray
        }
    }
    
    if (-not $taskCompleted) {
        Write-Host "  ✗ Task did not complete within expected time or failed" -ForegroundColor Red
        break
    }
    
    Write-Host ""
}

# Summary
Write-Host ""
Write-Host "[6/8] Pipeline Summary" -ForegroundColor Yellow
Write-Host "  Completed tasks: $completedTasks / $totalTasks" -ForegroundColor Cyan

if ($completedTasks -eq $totalTasks) {
    Write-Host ""
    Write-Host "[7/8] ✓ ALL TASKS COMPLETED SUCCESSFULLY!" -ForegroundColor Green
    Write-Host ""
    Write-Host "[8/8] Fetching final metrics..." -ForegroundColor Yellow
    $metricsLog = docker exec reddit-airflow-scheduler tail -50 "$logBase/task_id=send_metrics/attempt=1.log"
    Write-Host $metricsLog
} else {
    Write-Host ""
    Write-Host "[7/8] ✗ Pipeline incomplete" -ForegroundColor Red
    Write-Host ""
    Write-Host "To view full logs, run:" -ForegroundColor Yellow
    Write-Host "  docker exec reddit-airflow-scheduler tail -100 $logBase/task_id=<TASK_NAME>/attempt=1.log"
}

Write-Host ""
Write-Host "=== Monitoring Complete ===" -ForegroundColor Cyan
