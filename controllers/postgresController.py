from __future__ import annotations

from collections.abc import Sequence

from models.postgresModel import PostgreSQLModel


class PostgreSQLController:
    def __init__(
        self,
        connection_id: str,
        raw_table_name: str = "sensordata",
        metrics_table_name: str = "sensormetrics",
    ):
        self.model = PostgreSQLModel(connection_id)
        self.raw_table_name = raw_table_name
        self.metrics_table_name = metrics_table_name

    def get_last_source_id(self) -> int:
        query = f"""
            SELECT COALESCE(MAX(nSourceId), 0)
            FROM {self.raw_table_name}
        """

        result = self.model.fetch_one(query)

        if result is None:
            return 0

        return int(result[0])

    def insert_sensor_rows(
        self,
        rows: Sequence[Sequence],
    ) -> int:
        if not rows:
            return 0

        query = f"""
            INSERT INTO {self.raw_table_name}
            (
                nSourceId,
                strMachineName,
                fCurrent,
                fVoltage,
                nTemperature,
                dtInsert
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            ON CONFLICT
            (
                nSourceId,
                strMachineName
            )
            DO NOTHING
        """

        return self.model.execute_many(
            query=query,
            rows=rows,
        )

    def calculate_sensor_metrics(
        self,
        temperature_alert_threshold: int,
    ) -> tuple[int, int]:
        query = f"""
            WITH new_sensor_data AS
            (
                SELECT
                    sd.nId,
                    sd.nSourceId,
                    sd.strMachineName,
                    sd.fCurrent,
                    sd.fVoltage,
                    sd.nTemperature,
                    sd.dtInsert,

                    DATE_TRUNC('hour', sd.dtInsert)
                    + FLOOR(
                        EXTRACT(MINUTE FROM sd.dtInsert) / 5
                    ) * INTERVAL '5 minutes'
                        AS dtWindowStart

                FROM {self.raw_table_name} AS sd

                LEFT JOIN PipelineControl AS pc
                    ON pc.strMachineName = sd.strMachineName

                WHERE
                (
                    pc.nLastProcessedSourceId IS NOT NULL
                    AND sd.nSourceId > pc.nLastProcessedSourceId
                )
                OR
                (
                    pc.nLastProcessedSourceId IS NULL
                    AND sd.dtInsert >= CURRENT_TIMESTAMP - INTERVAL '1 day'
                )
            ),

            affected_windows AS
            (
                SELECT DISTINCT
                    strMachineName,
                    dtWindowStart

                FROM new_sensor_data
            ),

            aggregated_metrics AS
            (
                SELECT
                    sd.strMachineName,

                    aw.dtWindowStart,

                    aw.dtWindowStart + INTERVAL '5 minutes'
                        AS dtWindowEnd,

                    MIN(sd.nSourceId)
                        AS nFirstSourceId,

                    MAX(sd.nSourceId)
                        AS nLastSourceId,

                    COUNT(*)
                        AS nRecords,

                    AVG(sd.fCurrent)
                        AS fAverageCurrent,

                    MIN(sd.fCurrent)
                        AS fMinimumCurrent,

                    MAX(sd.fCurrent)
                        AS fMaximumCurrent,

                    AVG(sd.fVoltage)
                        AS fAverageVoltage,

                    MIN(sd.fVoltage)
                        AS fMinimumVoltage,

                    MAX(sd.fVoltage)
                        AS fMaximumVoltage,

                    AVG(sd.nTemperature)
                        AS fAverageTemperature,

                    MIN(sd.nTemperature)
                        AS nMinimumTemperature,

                    MAX(sd.nTemperature)
                        AS nMaximumTemperature

                FROM affected_windows AS aw

                INNER JOIN {self.raw_table_name} AS sd
                    ON sd.strMachineName =
                        aw.strMachineName

                AND sd.dtInsert >=
                        aw.dtWindowStart

                AND sd.dtInsert <
                        aw.dtWindowStart
                        + INTERVAL '5 minutes'

                GROUP BY
                    sd.strMachineName,
                    aw.dtWindowStart
            ),

            inserted_metrics AS
            (
                INSERT INTO {self.metrics_table_name}
                (
                    strMachineName,

                    dtWindowStart,
                    dtWindowEnd,

                    nFirstSourceId,
                    nLastSourceId,

                    nRecords,

                    fAverageCurrent,
                    fMinimumCurrent,
                    fMaximumCurrent,

                    fAverageVoltage,
                    fMinimumVoltage,
                    fMaximumVoltage,

                    fAverageTemperature,
                    nMinimumTemperature,
                    nMaximumTemperature,

                    bTemperatureAlert
                )

                SELECT
                    strMachineName,

                    dtWindowStart,
                    dtWindowEnd,

                    nFirstSourceId,
                    nLastSourceId,

                    nRecords,

                    fAverageCurrent,
                    fMinimumCurrent,
                    fMaximumCurrent,

                    fAverageVoltage,
                    fMinimumVoltage,
                    fMaximumVoltage,

                    fAverageTemperature,
                    nMinimumTemperature,
                    nMaximumTemperature,

                    nMaximumTemperature >= %s
                        AS bTemperatureAlert

                FROM aggregated_metrics

                ON CONFLICT
                (
                    strMachineName,
                    dtWindowStart,
                    dtWindowEnd
                )

                DO UPDATE SET
                    nFirstSourceId =
                        EXCLUDED.nFirstSourceId,

                    nLastSourceId =
                        EXCLUDED.nLastSourceId,

                    nRecords =
                        EXCLUDED.nRecords,

                    fAverageCurrent =
                        EXCLUDED.fAverageCurrent,

                    fMinimumCurrent =
                        EXCLUDED.fMinimumCurrent,

                    fMaximumCurrent =
                        EXCLUDED.fMaximumCurrent,

                    fAverageVoltage =
                        EXCLUDED.fAverageVoltage,

                    fMinimumVoltage =
                        EXCLUDED.fMinimumVoltage,

                    fMaximumVoltage =
                        EXCLUDED.fMaximumVoltage,

                    fAverageTemperature =
                        EXCLUDED.fAverageTemperature,

                    nMinimumTemperature =
                        EXCLUDED.nMinimumTemperature,

                    nMaximumTemperature =
                        EXCLUDED.nMaximumTemperature,

                    bTemperatureAlert =
                        EXCLUDED.bTemperatureAlert,

                    dtProcessing =
                        CURRENT_TIMESTAMP

                RETURNING
                    strMachineName
            ),

            processed_sources AS
            (
                SELECT
                    strMachineName,

                    MAX(nSourceId)
                        AS nLastProcessedSourceId

                FROM new_sensor_data

                GROUP BY
                    strMachineName
            ),

            successful_machines AS
            (
                SELECT DISTINCT
                    strMachineName

                FROM inserted_metrics
            ),

            updated_control AS
            (
                INSERT INTO PipelineControl
                (
                    strMachineName,
                    nLastProcessedSourceId,
                    dtLastProcessing
                )

                SELECT
                    ps.strMachineName,
                    ps.nLastProcessedSourceId,
                    CURRENT_TIMESTAMP

                FROM processed_sources AS ps

                INNER JOIN successful_machines AS sm
                    ON sm.strMachineName =
                        ps.strMachineName

                ON CONFLICT
                (
                    strMachineName
                )

                DO UPDATE SET
                    nLastProcessedSourceId =
                        GREATEST
                        (
                            PipelineControl
                                .nLastProcessedSourceId,

                            EXCLUDED
                                .nLastProcessedSourceId
                        ),

                    dtLastProcessing =
                        EXCLUDED.dtLastProcessing

                RETURNING
                    strMachineName,
                    nLastProcessedSourceId
            )

            SELECT
                (
                    SELECT COUNT(*)
                    FROM inserted_metrics
                ) AS nProcessedMetrics,

                (
                    SELECT COUNT(*)
                    FROM updated_control
                ) AS nUpdatedMachines
        """

        result = self.model.execute_returning_one(
            query,
            (temperature_alert_threshold,),
        )

        if result is None:
            return 0, 0

        return int(result[0] or 0), int(result[1] or 0)