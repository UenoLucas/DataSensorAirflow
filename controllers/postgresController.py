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

    def get_last_ingested_source_id(self) -> int:
        """Return the global SQLite cursor already loaded into PostgreSQL.

        ``nSourceId`` is copied from the ``nId`` AUTOINCREMENT column of the
        single shared SQLite ``SensorData`` table. That sequence is global
        across all machines, so the ingestion cursor must also be global.

        If each machine starts using an independent source database or its
        own ID sequence, this method and the SQLite read must be changed to
        track a cursor per machine instead.
        """
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
        window_minutes: int = 2,
        # tolerância após o fechamento da janela para permitir que leituras
        # atrasadas cheguem ao PostgreSQL antes do cálculo das métricas
        watermark_seconds: int = 15,
    ) -> tuple[int, int]:
        """calcula e persiste as métricas das janelas já encerradas."""
        if window_minutes <= 0:
            raise ValueError("window_minutes must be greater than zero.")

        if watermark_seconds < 0:
            raise ValueError("watermark_seconds cannot be negative.")

        query = f"""
            -- concentra os parâmetros para que todas as CTEs usem os mesmos
            -- intervalos e o mesmo limite de alerta durante a transação
            WITH metric_settings AS
            (
                SELECT
                    make_interval(mins => %s)
                        AS window_interval,

                    make_interval(secs => %s)
                        AS watermark_interval,

                    %s::DOUBLE PRECISION
                        AS window_minutes,

                    %s::INTEGER
                        AS temperature_alert_threshold
            ),

            -- seleciona somente leituras posteriores ao cursor de cada
            -- máquina e calcula a qual janela cada leitura pertence
            candidate_sensor_data AS
            (
                SELECT
                    sd.nId,
                    sd.nSourceId,
                    sd.strMachineName,
                    sd.fCurrent,
                    sd.fVoltage,
                    sd.nTemperature,
                    sd.dtInsert,

                    -- arredonda o horário para o início da janela; por
                    -- exemplo, 10:03 pertence à janela iniciada às 10:02
                    DATE_TRUNC('hour', sd.dtInsert)
                    + FLOOR(
                        EXTRACT(MINUTE FROM sd.dtInsert)
                        / settings.window_minutes
                    ) * settings.window_interval
                        AS dtWindowStart

                FROM {self.raw_table_name} AS sd

                CROSS JOIN metric_settings AS settings

                LEFT JOIN PipelineControl AS pc
                    ON pc.strMachineName = sd.strMachineName

                WHERE
                (
                    pc.nLastProcessedSourceId IS NOT NULL
                    AND sd.nSourceId > pc.nLastProcessedSourceId
                )
                OR
                (
                    -- limita a carga inicial para não processar um histórico
                    -- potencialmente muito grande de uma máquina nova
                    pc.nLastProcessedSourceId IS NULL
                    AND sd.dtInsert >= CURRENT_TIMESTAMP - INTERVAL '1 day'
                )
            ),

            -- mantém apenas dados de janelas fechadas; o watermark dá tempo
            -- para que leituras ligeiramente atrasadas cheguem ao PostgreSQL
            new_sensor_data AS
            (
                SELECT
                    candidate.*

                FROM candidate_sensor_data AS candidate

                CROSS JOIN metric_settings AS settings

                WHERE
                    candidate.dtWindowStart
                    + settings.window_interval
                    <= CURRENT_TIMESTAMP
                    - settings.watermark_interval
            ),

            -- identifica somente as janelas que precisam ser calculadas ou
            -- recalculadas nesta execução
            affected_windows AS
            (
                SELECT DISTINCT
                    strMachineName,
                    dtWindowStart

                FROM new_sensor_data
            ),

            -- recalcula cada janela afetada usando todos os seus registros,
            -- não apenas os registros novos, para aceitar chegadas atrasadas
            aggregated_metrics AS
            (
                SELECT
                    sd.strMachineName,

                    aw.dtWindowStart,

                    aw.dtWindowStart
                    + settings.window_interval
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

                FROM metric_settings AS settings

                CROSS JOIN affected_windows AS aw

                INNER JOIN {self.raw_table_name} AS sd
                    ON sd.strMachineName =
                        aw.strMachineName

                -- usa um intervalo semiaberto [início, fim) para que uma
                -- leitura no limite pertença somente à janela seguinte
                AND sd.dtInsert >=
                        aw.dtWindowStart

                AND sd.dtInsert <
                        aw.dtWindowStart
                        + settings.window_interval

                GROUP BY
                    sd.strMachineName,
                    aw.dtWindowStart,
                    settings.window_interval
            ),

            -- persiste as métricas e atualiza a janela quando ela já existe;
            -- isso torna o processamento idempotente e aceita dados atrasados
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

                    nMaximumTemperature >=
                        settings.temperature_alert_threshold
                        AS bTemperatureAlert

                FROM aggregated_metrics

                CROSS JOIN metric_settings AS settings

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

            -- encontra o maior ID realmente elegível para avançar o cursor
            -- individual de cada máquina
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

            -- considera bem-sucedidas somente máquinas cujas métricas foram
            -- inseridas ou atualizadas nesta mesma transação
            successful_machines AS
            (
                SELECT DISTINCT
                    strMachineName

                FROM inserted_metrics
            ),

            -- avança o controle somente após a persistência das métricas;
            -- assim uma falha anterior não faz leituras serem ignoradas
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
                    -- impede que um reprocessamento faça o cursor retroceder
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

            -- devolve contagens simples para os logs e para o retorno da task
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
            (
                window_minutes,
                watermark_seconds,
                window_minutes,
                temperature_alert_threshold,
            ),
        )

        if result is None:
            return 0, 0

        return int(result[0] or 0), int(result[1] or 0)
