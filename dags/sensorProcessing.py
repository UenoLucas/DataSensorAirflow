from datetime import datetime

from airflow.sdk import dag, task

from controllers.postgresController import PostgreSQLController


POSTGRES_CONNECTION_ID = "sensor_postgres"
TEMPERATURE_ALERT_THRESHOLD = 85
METRICS_WINDOW_MINUTES = 2
METRICS_WATERMARK_SECONDS = 15


@dag(
    dag_id="sensor_processing",
    description="Calculate two-minute metrics from raw sensor data",
    # Run every two minutes on odd minutes. This leaves roughly one minute
    # between an even-minute window boundary and its metrics calculation.
    schedule="1-59/2 * * * *",
    start_date=datetime(2026, 7, 1),
    catchup=False,
    max_active_runs=1,
    tags=["sensors", "postgresql", "metrics"],
)
def sensor_processing():

    @task
    def calculate_metrics() -> int:
        controller = PostgreSQLController(
            connection_id=POSTGRES_CONNECTION_ID,
        )

        processed_metrics, updated_machines = (
            controller.calculate_sensor_metrics(
                temperature_alert_threshold=(
                    TEMPERATURE_ALERT_THRESHOLD
                ),
                window_minutes=METRICS_WINDOW_MINUTES,
                watermark_seconds=(
                    METRICS_WATERMARK_SECONDS
                ),
            )
        )

        print(
            f"Processed metrics: {processed_metrics}. "
            f"Updated machines: {updated_machines}."
        )

        return processed_metrics

    calculate_metrics()


sensor_processing()
