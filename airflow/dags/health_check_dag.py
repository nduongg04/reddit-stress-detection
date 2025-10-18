"""
Health Check DAG for Reddit Real-Time Stress Monitoring Pipeline.

This DAG runs periodic health checks on all system components:
- Airflow itself
- Kafka cluster
- Cassandra database
- Spark cluster (when implemented)

Scheduled to run every 15 minutes to ensure system health.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator

# ============================================================================
# CONFIGURATION
# ============================================================================

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': True,  # Enable email alerts on failure
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

# ============================================================================
# HEALTH CHECK FUNCTIONS
# ============================================================================

def check_airflow_health(**context):
    """
    Verify Airflow core components are functioning.

    Returns:
        dict: Health status
    """
    import psutil
    from airflow.models import Variable

    print("=== Airflow Health Check ===")

    health = {
        'status': 'healthy',
        'checks': {}
    }

    # Check system resources
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()

    health['checks']['cpu'] = {
        'usage_percent': cpu_percent,
        'status': 'ok' if cpu_percent < 80 else 'warning'
    }

    health['checks']['memory'] = {
        'usage_percent': memory.percent,
        'available_mb': memory.available / (1024 * 1024),
        'status': 'ok' if memory.percent < 80 else 'warning'
    }

    # Check disk space
    disk = psutil.disk_usage('/')
    health['checks']['disk'] = {
        'usage_percent': disk.percent,
        'free_gb': disk.free / (1024**3),
        'status': 'ok' if disk.percent < 80 else 'warning'
    }

    print(f"CPU Usage: {cpu_percent}%")
    print(f"Memory Usage: {memory.percent}%")
    print(f"Disk Usage: {disk.percent}%")

    # Determine overall status
    if any(check['status'] == 'warning' for check in health['checks'].values()):
        health['status'] = 'warning'

    # Push results to XCom
    context['ti'].xcom_push(key='airflow_health', value=health)

    return health['status']


def check_kafka_health(**context):
    """
    Verify Kafka cluster connectivity and health.

    Returns:
        str: Health status
    """
    print("=== Kafka Health Check ===")

    try:
        import socket

        # Check if Kafka port is accessible
        # Kafka hostname from docker network: reddit-kafka, port 9092
        kafka_host = 'reddit-kafka'
        kafka_port = 9092

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((kafka_host, kafka_port))
        sock.close()

        if result == 0:
            print(f"✓ Kafka is accessible at {kafka_host}:{kafka_port}")
            context['ti'].xcom_push(key='kafka_health', value='healthy')
            return 'healthy'
        else:
            print(f"✗ Kafka not accessible at {kafka_host}:{kafka_port}")
            context['ti'].xcom_push(key='kafka_health', value='unhealthy')
            return 'unhealthy'

    except Exception as e:
        print(f"✗ Kafka health check failed: {str(e)}")
        context['ti'].xcom_push(key='kafka_health', value='unhealthy')
        return 'unhealthy'


def check_cassandra_health(**context):
    """
    Verify Cassandra database connectivity and health.

    Returns:
        str: Health status
    """
    print("=== Cassandra Health Check ===")

    try:
        import socket

        # Check if Cassandra port is accessible
        # Cassandra hostname from docker network: cassandra, port 9042
        cassandra_host = 'cassandra'
        cassandra_port = 9042

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((cassandra_host, cassandra_port))
        sock.close()

        if result == 0:
            print(f"✓ Cassandra is accessible at {cassandra_host}:{cassandra_port}")
            context['ti'].xcom_push(key='cassandra_health', value='healthy')
            return 'healthy'
        else:
            print(f"✗ Cassandra not accessible at {cassandra_host}:{cassandra_port}")
            context['ti'].xcom_push(key='cassandra_health', value='unhealthy')
            return 'unhealthy'

    except Exception as e:
        print(f"✗ Cassandra health check failed: {str(e)}")
        context['ti'].xcom_push(key='cassandra_health', value='unhealthy')
        return 'unhealthy'


def check_spark_health(**context):
    """
    Verify Spark cluster connectivity (when implemented).

    Returns:
        str: Health status
    """
    print("=== Spark Health Check ===")

    try:
        import socket

        # Check if Spark master UI port is accessible
        # Spark master hostname from docker network: spark-master, port 8080
        spark_host = 'spark-master'
        spark_port = 8080

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((spark_host, spark_port))
        sock.close()

        if result == 0:
            print(f"✓ Spark master is accessible at {spark_host}:{spark_port}")
            context['ti'].xcom_push(key='spark_health', value='healthy')
            return 'healthy'
        else:
            print(f"⚠ Spark master not accessible at {spark_host}:{spark_port}")
            context['ti'].xcom_push(key='spark_health', value='not_configured')
            return 'not_configured'

    except Exception as e:
        print(f"⚠ Spark health check skipped: {str(e)}")
        context['ti'].xcom_push(key='spark_health', value='not_configured')
        return 'not_configured'


def evaluate_overall_health(**context):
    """
    Evaluate overall system health based on component checks.

    Returns:
        str: Task ID to branch to
    """
    ti = context['ti']

    # Retrieve all health statuses
    airflow_health = ti.xcom_pull(key='airflow_health', task_ids='check_airflow')
    kafka_health = ti.xcom_pull(key='kafka_health', task_ids='check_kafka')
    cassandra_health = ti.xcom_pull(key='cassandra_health', task_ids='check_cassandra')
    spark_health = ti.xcom_pull(key='spark_health', task_ids='check_spark')

    print("\n=== Overall Health Summary ===")
    print(f"Airflow: {airflow_health}")
    print(f"Kafka: {kafka_health}")
    print(f"Cassandra: {cassandra_health}")
    print(f"Spark: {spark_health}")

    # Determine overall status
    critical_unhealthy = any([
        kafka_health == 'unhealthy',
        cassandra_health == 'unhealthy',
    ])

    if critical_unhealthy:
        print("\n⚠️ CRITICAL: One or more components are unhealthy!")
        return 'alert_on_failure'
    elif airflow_health == 'warning':
        print("\n⚠️ WARNING: System resources under pressure")
        return 'alert_on_warning'
    else:
        print("\n✓ All systems healthy")
        return 'system_healthy'


def send_alert(**context):
    """
    Send alert notification when health check fails.
    """
    print("=== Sending Health Alert ===")

    ti = context['ti']
    health_data = {
        'airflow': ti.xcom_pull(key='airflow_health', task_ids='check_airflow'),
        'kafka': ti.xcom_pull(key='kafka_health', task_ids='check_kafka'),
        'cassandra': ti.xcom_pull(key='cassandra_health', task_ids='check_cassandra'),
        'spark': ti.xcom_pull(key='spark_health', task_ids='check_spark'),
    }

    # In production, send to:
    # - Email
    # - Slack
    # - PagerDuty
    # - Monitoring dashboard

    print("Alert would be sent with data:")
    print(health_data)


# ============================================================================
# DAG DEFINITION
# ============================================================================

with DAG(
    dag_id='health_check_dag',
    default_args=default_args,
    description='Periodic health checks for all system components',
    schedule_interval=timedelta(minutes=15),  # Run every 15 minutes
    start_date=datetime(2025, 10, 1),
    catchup=False,
    tags=['health', 'monitoring'],
) as dag:

    # Start marker
    start = DummyOperator(task_id='start_health_check')

    # Component health checks (run in parallel)
    check_airflow = PythonOperator(
        task_id='check_airflow',
        python_callable=check_airflow_health,
        provide_context=True,
    )

    check_kafka = PythonOperator(
        task_id='check_kafka',
        python_callable=check_kafka_health,
        provide_context=True,
    )

    check_cassandra = PythonOperator(
        task_id='check_cassandra',
        python_callable=check_cassandra_health,
        provide_context=True,
    )

    check_spark = PythonOperator(
        task_id='check_spark',
        python_callable=check_spark_health,
        provide_context=True,
    )

    # Evaluate overall health and branch
    evaluate_health = BranchPythonOperator(
        task_id='evaluate_health',
        python_callable=evaluate_overall_health,
        provide_context=True,
    )

    # Branch outcomes
    system_healthy = DummyOperator(
        task_id='system_healthy',
    )

    alert_on_warning = PythonOperator(
        task_id='alert_on_warning',
        python_callable=send_alert,
        provide_context=True,
    )

    alert_on_failure = PythonOperator(
        task_id='alert_on_failure',
        python_callable=send_alert,
        provide_context=True,
    )

    # End marker
    end = DummyOperator(
        task_id='end_health_check',
        trigger_rule='none_failed_min_one_success',
    )

    # Define task dependencies
    start >> [check_airflow, check_kafka, check_cassandra, check_spark]
    [check_airflow, check_kafka, check_cassandra, check_spark] >> evaluate_health
    evaluate_health >> [system_healthy, alert_on_warning, alert_on_failure]
    [system_healthy, alert_on_warning, alert_on_failure] >> end
