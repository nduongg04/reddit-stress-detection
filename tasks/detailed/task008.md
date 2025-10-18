# TASK-008: Airflow Environment Setup

**Owner:** DataOps/Viz Engineer
**Priority:** Medium
**Dependencies:** None
**Estimate:** 1 day

---

## Overview
Install and configure Apache Airflow for workflow orchestration and monitoring of the data pipeline.

---

## Subtasks

### 8.1 Verify Airflow Services in Docker
**Status:** ✅ Completed
**Type:** Automated
**Estimate:** 20 minutes

- [x] Verify docker-compose.yml includes:
  - airflow-postgres (metadata database)
  - airflow-webserver (UI)
  - airflow-scheduler (job scheduler)
- [x] Check configuration:
  - Webserver port 8082
  - Executor: LocalExecutor
  - Credentials: airflow/airflow
- [x] Verify volume mounts for:
  - DAGs folder
  - Logs folder
  - Plugins folder

**Acceptance Criteria:**
- All Airflow services defined ✅
- Configuration correct ✅
- Volumes mounted properly ✅

---

### 8.2 Create Directory Structure
**Status:** ✅ Completed
**Type:** Automated
**Estimate:** 15 minutes

- [x] Create Airflow directories:
  - `airflow/dags/` (DAG definitions)
  - `airflow/logs/` (execution logs)
  - `airflow/plugins/` (custom plugins)
  - `airflow/config/` (configuration files)
- [x] Set proper permissions
- [x] Create `.gitkeep` files for empty directories
- [x] Update `.gitignore` for logs

**Acceptance Criteria:**
- Directory structure created ✅
- Proper permissions set ✅
- Ready for Airflow ✅

---

### 8.3 Start Airflow Services
**Status:** ✅ Completed
**Type:** Automated + Manual
**Estimate:** 30 minutes

- [x] Start Postgres container first
- [x] Wait for Postgres to be healthy
- [x] Start Airflow webserver and scheduler
- [x] Wait for initialization (can take 1-2 minutes)
- [x] Check logs for errors
- [x] **[USER TASK]** Access Airflow UI at http://localhost:8082
- [x] **[USER TASK]** Login with airflow/airflow

**Acceptance Criteria:**
- All containers running ✅
- Airflow UI accessible ✅
- Can login successfully (user verification needed)
- No errors in logs ✅

---

### 8.4 Verify Airflow Database
**Status:** ✅ Completed
**Type:** Automated + Manual
**Estimate:** 20 minutes

- [x]Check Postgres connection
- [x]Verify metadata tables created
- [x] **[USER TASK]** Check Airflow UI shows:
  - No DAGs yet (empty state)
  - Scheduler is running
  - Database connection working
- [x]Test database connectivity

**Acceptance Criteria:**
- Database initialized correctly
- Metadata tables exist
- Airflow can connect to DB

---

### 8.5 Create Sample DAG
**Status:** ✅ Completed
**Type:** Automated
**Estimate:** 45 minutes

- [x]Create `airflow/dags/sample_dag.py`
- [x]Define simple DAG:
  - Single task: print "Hello from Airflow"
  - Schedule: daily
  - Start date: yesterday
- [x]Add proper DAG documentation
- [x]Test DAG syntax: `python airflow/dags/sample_dag.py`
- [x] **[USER TASK]** Verify DAG appears in UI (may take 30s-1min)

**Acceptance Criteria:**
- Sample DAG created
- No syntax errors
- DAG visible in Airflow UI
- Can be triggered manually

---

### 8.6 Test DAG Execution
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 30 minutes

- [x] **[USER TASK]** In Airflow UI, trigger sample DAG
- [x] **[USER TASK]** Monitor execution in:
  - Graph view
  - Tree view
  - Log view
- [x] **[USER TASK]** Verify task completes successfully
- [x]Check logs for output message
- [x]Test DAG re-run

**Acceptance Criteria:**
- DAG executes successfully
- Logs accessible
- Task shows green (success)
- Can re-trigger DAG

---

### 8.7 Configure Airflow Settings
**Status:** ✅ Completed
**Type:** Automated
**Estimate:** 45 minutes

- [x]Create `airflow/config/airflow.cfg` (optional overrides)
- [x]Configure via environment variables:
  - AIRFLOW__CORE__LOAD_EXAMPLES: false
  - AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: true
  - AIRFLOW__CORE__DAG_DISCOVERY_SAFE_MODE: false
  - AIRFLOW__WEBSERVER__EXPOSE_CONFIG: true
  - AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL: 30
- [x]Restart services to apply changes
- [x]Verify settings in UI (Admin → Configuration)

**Acceptance Criteria:**
- Settings configured correctly
- Example DAGs not loaded
- Configuration accessible in UI

---

### 8.8 Setup Airflow Connections
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 45 minutes

- [x] **[USER TASK]** Navigate to Admin → Connections
- [x] **[USER TASK]** Add connection for Kafka:
  - Conn ID: kafka_default
  - Conn Type: (use JSON or generic)
  - Host: kafka
  - Port: 29092
- [x] **[USER TASK]** Add connection for Spark:
  - Conn ID: spark_default
  - Conn Type: Spark
  - Host: spark://spark-master
  - Port: 7077
- [x] **[USER TASK]** Add connection for Cassandra:
  - Conn ID: cassandra_default
  - Conn Type: (use JSON or generic)
  - Host: cassandra
  - Port: 9042
  - Schema: reddit_rt
- [x]Test connections (if possible)
- [x]Document connection details

**Acceptance Criteria:**
- All connections created
- Connection details correct
- Documented for reference

---

### 8.9 Install Airflow Providers (Optional)
**Status:** ✅ Completed
**Type:** Automated
**Estimate:** 30 minutes

- [x]Identify needed providers:
  - apache-airflow-providers-apache-spark
  - apache-airflow-providers-apache-kafka (if available)
- [x]Create requirements.txt for Airflow
- [x]Install providers in Airflow container
- [x]Restart services
- [x]Verify providers installed

**Acceptance Criteria:**
- Providers installed (if needed)
- Additional operators available
- No version conflicts

---

### 8.10 Create DAG Template
**Status:** ✅ Completed
**Type:** Automated
**Estimate:** 1 hour

- [x]Create `airflow/dags/templates/dag_template.py`
- [x]Include best practices:
  - Proper imports
  - DAG documentation
  - Default arguments
  - Task dependencies
  - Error handling
  - Retries configuration
  - Email notifications (structure)
- [x]Add comments explaining each section
- [x]Document usage

**Acceptance Criteria:**
- Template covers common patterns
- Well documented
- Easy to copy and modify

---

### 8.11 Configure Logging
**Status:** ✅ Completed
**Type:** Automated
**Estimate:** 30 minutes

- [x]Verify log directory mounted
- [x]Configure log retention:
  - Keep logs for 30 days
  - Automatic cleanup
- [x]Test log writing
- [x] **[USER TASK]** Verify logs accessible in UI
- [x]Configure log level (INFO for prod, DEBUG for dev)

**Acceptance Criteria:**
- Logs written to correct location
- Accessible via UI
- Retention policy configured
- Log level appropriate

---

### 8.12 Setup Email Notifications (Optional)
**Status:** ✅ Completed
**Type:** Automated
**Estimate:** 45 minutes

- [x]Configure SMTP settings (if email server available):
  - AIRFLOW__SMTP__SMTP_HOST
  - AIRFLOW__SMTP__SMTP_PORT
  - AIRFLOW__SMTP__SMTP_USER
  - AIRFLOW__SMTP__SMTP_PASSWORD
- [x]Test email sending
- [x]Configure default recipients
- [x]Add email on failure settings
- [x]Document email configuration

**Acceptance Criteria:**
- Email configured (or documented as TODO)
- Test email sent successfully (if configured)
- Failure notifications work

---

### 8.13 Create Health Check DAG
**Status:** ✅ Completed
**Type:** Automated
**Estimate:** 1 hour

- [x]Create `airflow/dags/system_health_check.py`
- [x]Check components:
  - Kafka broker health
  - Spark cluster health
  - Cassandra health
  - Disk space
- [x]Schedule: every 5 minutes
- [x]Alert on failures
- [x]Log health status

**Acceptance Criteria:**
- Health check DAG created
- Tests all critical components
- Runs every 5 minutes
- Alerts on failure

---

### 8.14 Configure Scheduler Settings
**Status:** ✅ Completed
**Type:** Automated
**Estimate:** 30 minutes

- [x]Tune scheduler settings:
  - Max active runs per DAG
  - Scheduler heartbeat interval
  - DAG parsing interval
  - Task execution parallelism
- [x]Document tuning rationale
- [x]Test scheduler performance
- [x]Monitor scheduler metrics

**Acceptance Criteria:**
- Scheduler settings optimized
- DAGs parsed regularly
- No scheduler lag
- Settings documented

---

### 8.15 Create Utility Scripts
**Status:** ✅ Completed
**Type:** Automated
**Estimate:** 45 minutes

- [x]Create `scripts/airflow-cli.sh` wrapper
- [x]Common commands:
  - List DAGs
  - Trigger DAG
  - View logs
  - Pause/unpause DAG
  - Clear task instances
- [x]Make scripts executable
- [x]Document usage

**Acceptance Criteria:**
- Utility scripts created
- Common operations simplified
- Scripts documented

---

### 8.16 Testing DAG Development Workflow
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 45 minutes

- [x]Create test DAG
- [x]Edit DAG locally
- [x] **[USER TASK]** Verify changes appear in UI (~30s)
- [x]Test DAG validation
- [x]Test task execution
- [x]Test error handling
- [x]Document development workflow

**Acceptance Criteria:**
- Development workflow smooth
- Changes detected quickly
- Errors caught early
- Workflow documented

---

### 8.17 Setup Variable Management
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 30 minutes

- [x] **[USER TASK]** Navigate to Admin → Variables
- [x] **[USER TASK]** Add common variables:
  - kafka_topic_raw: reddit.posts.raw.v1
  - kafka_topic_dlq: reddit.posts.dlq.v1
  - data_retention_days: 90
  - alert_email: (email address)
- [x]Document variable usage
- [x]Create variables export/import script

**Acceptance Criteria:**
- Common variables defined
- Variables accessible from DAGs
- Export/import capability

---

### 8.18 Performance and Monitoring
**Status:** ✅ Completed
**Type:** Automated + Manual
**Estimate:** 30 minutes

- [x] **[USER TASK]** Explore Airflow metrics:
  - DAG run duration
  - Task duration
  - Success/failure rates
  - Scheduler lag
- [x]Document key metrics to monitor
- [x]Identify any performance issues
- [x]Plan monitoring integration (TASK-036)

**Acceptance Criteria:**
- Metrics understood
- Key metrics identified
- Performance acceptable
- Ready for monitoring integration

---

### 8.19 Documentation
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 1.5 hours

- [x]Create `docs/airflow-setup.md`
- [x]Document:
  - Airflow architecture
  - How to access UI
  - How to create DAGs
  - Connection management
  - Variable management
  - Triggering DAGs
  - Viewing logs
  - Troubleshooting guide
  - Common commands
- [x]Add screenshots
- [x]Document best practices

**Acceptance Criteria:**
- Complete documentation
- Screenshots included
- Easy for new users
- Best practices documented

---

### 8.20 Security Hardening (Basic)
**Status:** ✅ Completed
**Type:** Automated
**Estimate:** 45 minutes

- [x] **[USER TASK]** Change default admin password
- [x]Disable DAG examples (already done in 8.7)
- [x]Configure Fernet key for encryption
- [x]Limit webserver exposure (internal only)
- [x]Document security configuration
- [x]Plan for production security (RBAC, etc.)

**Acceptance Criteria:**
- Default password changed
- Fernet key configured
- Basic security measures in place
- Production security planned

---

## Final Acceptance Criteria Checklist

- [x]Apache Airflow (2.x) installed and running
- [x]Executor configured (LocalExecutor for dev)
- [x]Connections set up (Kafka, Spark, Cassandra)
- [x]DAG folder structure created
- [x]Logging configured and accessible
- [x]Sample DAG executes successfully
- [x]Webserver accessible at http://localhost:8082
- [x]Scheduler running without errors
- [x]Can create and trigger DAGs
- [x]Documentation complete
- [x] **[USER TASK]** All manual setup and verification completed

---

## Dependencies for Next Tasks

This task enables:
- TASK-022: Model Training Airflow DAG
- TASK-027: Producer Control Airflow DAG
- TASK-028: Backfill Airflow DAG
- TASK-037: Aggregation Recompute DAG
- TASK-038: Data Quality Checks DAG

---

## Rollback Plan

If this task fails:
1. Stop Airflow containers
2. Remove Airflow volumes (if needed)
3. Fix configuration issues
4. Restart from subtask 8.3

---

## Example Simple DAG

```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 10, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def hello_world():
    print("Hello from Airflow!")
    return "Success"

with DAG(
    'sample_dag',
    default_args=default_args,
    description='A simple sample DAG',
    schedule_interval='@daily',
    catchup=False,
    tags=['example'],
) as dag:

    task1 = PythonOperator(
        task_id='hello_task',
        python_callable=hello_world,
    )
```

---

## Common Airflow CLI Commands

```bash
# List DAGs
docker exec reddit-airflow-webserver airflow dags list

# Trigger DAG
docker exec reddit-airflow-webserver airflow dags trigger sample_dag

# View task logs
docker exec reddit-airflow-webserver airflow tasks logs sample_dag hello_task 2025-10-06

# Pause/Unpause DAG
docker exec reddit-airflow-webserver airflow dags pause sample_dag
docker exec reddit-airflow-webserver airflow dags unpause sample_dag
```

---

## Notes

- LocalExecutor sufficient for development (single machine)
- Production will need CeleryExecutor or KubernetesExecutor
- DAG files are automatically parsed every 30 seconds
- Keep DAG files lightweight (import in task execution, not at DAG level)
- Use Variables and Connections for configuration (not hardcode)
- Test DAGs locally before deploying
- Monitor scheduler performance regularly
- Plan for scaling as DAG count grows
