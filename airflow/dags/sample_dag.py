"""
Sample DAG for testing Airflow setup.

This DAG verifies that Airflow is configured correctly and can execute tasks.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator


def print_hello():
    """Simple Python function to verify Python operators work."""
    print("Hello from Airflow!")
    print(f"Execution date: {datetime.now()}")
    return "success"


def print_context(**context):
    """Print Airflow context variables."""
    print(f"DAG ID: {context['dag'].dag_id}")
    print(f"Task ID: {context['task'].task_id}")
    print(f"Execution date: {context['execution_date']}")
    return "context_printed"


# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Define the DAG
with DAG(
    dag_id='sample_dag',
    default_args=default_args,
    description='A simple sample DAG to test Airflow setup',
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2025, 10, 1),
    catchup=False,
    tags=['test', 'sample'],
) as dag:

    # Task 1: Bash operator test
    bash_task = BashOperator(
        task_id='bash_hello',
        bash_command='echo "Hello from Bash operator!" && date',
    )

    # Task 2: Python operator test
    python_task = PythonOperator(
        task_id='python_hello',
        python_callable=print_hello,
    )

    # Task 3: Context test
    context_task = PythonOperator(
        task_id='print_context',
        python_callable=print_context,
        provide_context=True,
    )

    # Task 4: Check environment
    env_task = BashOperator(
        task_id='check_environment',
        bash_command='echo "Python version:" && python --version && echo "Airflow home: $AIRFLOW_HOME"',
    )

    # Define task dependencies
    bash_task >> python_task >> context_task >> env_task
