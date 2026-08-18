from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from airflow.sdk import dag, task

from controllers.postgresController import PostgreSQLController
from controllers.sqliteController import SQLiteController

SQLITE_DATABASE = Path(
    "/opt/project/database/LocalData.db"
)

POSTGRES_CONNECTION_ID = "sensor_postgres"



@dag(
    dag_id="sqlite_to_postgres",
    description='Get data from SQLite and insert into PostgreSQL',
    schedule="*/1 * * * *",
    start_date=datetime(2026, 7, 1),
    catchup=False,
    max_active_runs=1,
    tags=["sensors", "sqlite", "postgresql"],
)
def sqlite_to_postgres():

    @task
    def transfer_sensor_data() -> int:
        postgres_controller = PostgreSQLController(
            connection_id=POSTGRES_CONNECTION_ID,
        )
        sqlite_controller = SQLiteController(SQLITE_DATABASE,table_name='SensorData')

        # nSourceId comes from SQLite's global AUTOINCREMENT sequence, so one
        # cursor is sufficient even when records belong to different machines.
        last_source_id = (
            postgres_controller.get_last_ingested_source_id()
        )

        # get in sqlite the data after this last source id
        rows = sqlite_controller.get_sensor_rows_after(
            last_source_id
        )

        # insert this data to postgresql
        inserted_rows = (
            postgres_controller.insert_sensor_rows(rows)
        )

        print(
            f"Rows found in SQLite: {len(rows)}. "
            f"Rows inserted into PostgreSQL: "
            f"{inserted_rows}."
        )

        return inserted_rows

    transfer_sensor_data()


sqlite_to_postgres()
