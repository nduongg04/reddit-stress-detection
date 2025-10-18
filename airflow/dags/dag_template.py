"""
DAG Template for Reddit Real-Time Stress Monitoring Pipeline.

This template provides a standardized structure for creating DAGs
in the Reddit stress monitoring project.

Usage:
1. Copy this file to a new DAG file
2. Update the DAG configuration below
3. Add your custom tasks
4. Define task dependencies
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

# ============================================================================
# DAG CONFIGURATION - CUSTOMIZE THESE VALUES
# ============================================================================

DAG_ID = 'template_dag'  # Change this to your DAG name
DAG_DESCRIPTION = 'Template DAG for Reddit stress monitoring pipeline'
SCHEDULE_INTERVAL = None  # Change to cron expression or timedelta
START_DATE = datetime(2025, 10, 1)
TAGS = ['template']  # Add relevant tags

# ============================================================================
# DEFAULT ARGUMENTS
# ============================================================================

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email': [],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'retry_exponential_backoff': True,
    'max_retry_delay': timedelta(minutes=30),
}

# ============================================================================
# TASK FUNCTIONS
# ============================================================================

def start_pipeline(**context):
    """
    Initialize pipeline execution.

    Args:
        **context: Airflow context variables

    Returns:
        str: Status message
    """
    print(f"Starting pipeline: {context['dag'].dag_id}")
    print(f"Execution date: {context['execution_date']}")
    return "pipeline_started"


def check_dependencies(**context):
    """
    Verify all required services and data sources are available.

    Args:
        **context: Airflow context variables

    Returns:
        str: Status message

    Raises:
        Exception: If any dependency check fails
    """
    print("Checking dependencies...")
    # Add your dependency checks here:
    # - Check Kafka connectivity
    # - Check Cassandra connectivity
    # - Check Spark cluster status
    # - Check required environment variables

    print("All dependencies satisfied")
    return "dependencies_ok"


def process_data(**context):
    """
    Main data processing logic.

    Args:
        **context: Airflow context variables

    Returns:
        dict: Processing results
    """
    print("Processing data...")
    # Add your data processing logic here

    results = {
        'records_processed': 0,
        'errors': 0,
        'duration_seconds': 0,
    }

    print(f"Processing complete: {results}")
    return results


def cleanup_resources(**context):
    """
    Clean up temporary resources and close connections.

    Args:
        **context: Airflow context variables

    Returns:
        str: Status message
    """
    print("Cleaning up resources...")
    # Add cleanup logic here

    print("Cleanup complete")
    return "cleanup_done"


def handle_failure(context):
    """
    Custom failure handler for the DAG.

    Args:
        context: Airflow context variables
    """
    print(f"Task failed: {context['task_instance'].task_id}")
    print(f"Exception: {context.get('exception')}")
    # Add custom failure handling:
    # - Send notifications
    # - Log to monitoring system
    # - Trigger rollback procedures


# ============================================================================
# DAG DEFINITION
# ============================================================================

with DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description=DAG_DESCRIPTION,
    schedule_interval=SCHEDULE_INTERVAL,
    start_date=START_DATE,
    catchup=False,
    tags=TAGS,
    on_failure_callback=handle_failure,
) as dag:

    # ========================================================================
    # TASK DEFINITIONS
    # ========================================================================

    # Task 1: Start pipeline
    start_task = PythonOperator(
        task_id='start_pipeline',
        python_callable=start_pipeline,
        provide_context=True,
    )

    # Task 2: Check dependencies
    check_deps_task = PythonOperator(
        task_id='check_dependencies',
        python_callable=check_dependencies,
        provide_context=True,
    )

    # Task 3: Process data
    process_task = PythonOperator(
        task_id='process_data',
        python_callable=process_data,
        provide_context=True,
    )

    # Task 4: Cleanup
    cleanup_task = PythonOperator(
        task_id='cleanup_resources',
        python_callable=cleanup_resources,
        provide_context=True,
        trigger_rule='all_done',  # Run even if upstream tasks fail
    )

    # Task 5: Example Bash task
    bash_example = BashOperator(
        task_id='bash_example',
        bash_command='echo "Bash task example"',
    )

    # ========================================================================
    # TASK DEPENDENCIES
    # ========================================================================

    # Linear pipeline
    start_task >> check_deps_task >> process_task >> bash_example >> cleanup_task

    # For parallel tasks, use list syntax:
    # start_task >> [task1, task2, task3] >> cleanup_task

# ============================================================================
# NOTES
# ============================================================================

"""
Common Airflow Operators for this project:

1. PythonOperator - Run Python functions
2. BashOperator - Run bash commands
3. BranchPythonOperator - Conditional branching
4. DummyOperator - Placeholder tasks
5. TriggerDagRunOperator - Trigger other DAGs
6. EmailOperator - Send email notifications

Useful Airflow Features:

- XCom: Share data between tasks using context['ti'].xcom_push() and xcom_pull()
- Variables: Store configuration using airflow.models.Variable
- Connections: Store credentials using Airflow connections
- Sensors: Wait for conditions (FileSensor, TimeSensor, etc.)
- Pools: Limit parallelism across DAGs
- Task Groups: Organize related tasks

For Reddit pipeline integration:

- Add KafkaProducer tasks to ingest data
- Add Spark job submission tasks
- Add Cassandra write tasks
- Add monitoring and alerting tasks
- Add data quality checks
"""
