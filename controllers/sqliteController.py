import sqlite3
from pathlib import Path


class SQLiteController:
    def __init__(self, fp_database, table_name = None):
        self.fp_database = fp_database
        self.connection = sqlite3.connect(fp_database)
        self.connection.row_factory = sqlite3.Row
        if table_name:
            self.table_name = table_name
        else:
            self.table_name = 'SensorData'
        self.verify_table_exists()

    def cursor(self):
        return self.connection.cursor()

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()

    def verify_table_exists(self) -> None:
        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
            AND name = ?
            """,
            (self.table_name,),
        )

        if cursor.fetchone() is None:
            raise RuntimeError(
                f"SQLite table '{self.table_name}' does not exist. "
                "Run the SQLite initialization container first."
            )

    def insert_sensor_data(self, sensor):
        cursor = self.connection.cursor()

        cursor.execute(f"""
            INSERT INTO {self.table_name} (
                strMachineName,
                fA,
                fV,
                nTemperature,
                dtInsert
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            sensor.machine_name,
            sensor.current,
            sensor.voltage,
            sensor.temperature,
            sensor.insert_date,
        ))

        self.connection.commit()

    def get_sensor_rows_after(self, nSourceID):
        query = f"""
            SELECT
                nId,
                strMachineName,
                fA as fCurrent,
                fV as fVoltage,
                nTemperature,
                dtInsert
            FROM {self.table_name}
            WHERE nId > ?
            ORDER BY nId
        """

        with sqlite3.connect(
            self.fp_database,
            timeout=30,
        ) as connection:

            cursor = connection.cursor()

            cursor.execute(
                query,
                (nSourceID,),
            )

            return cursor.fetchall()