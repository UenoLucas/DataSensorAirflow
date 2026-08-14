#!/usr/bin/env bash
set -euo pipefail

psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set=airflow_user="$AIRFLOW_DB_USER" \
    --set=airflow_password="$AIRFLOW_DB_PASSWORD" \
    --set=airflow_database="$AIRFLOW_DB_NAME" \
    --set=sensor_user="$SENSOR_DB_USER" \
    --set=sensor_password="$SENSOR_DB_PASSWORD" \
    --set=sensor_database="$SENSOR_DB_NAME" \
    <<'SQL'
CREATE USER :"airflow_user"
WITH PASSWORD :'airflow_password';

CREATE DATABASE :"airflow_database"
OWNER :"airflow_user";

CREATE USER :"sensor_user"
WITH PASSWORD :'sensor_password';

CREATE DATABASE :"sensor_database"
OWNER :"sensor_user";
SQL

psql \
    --username "$POSTGRES_USER" \
    --dbname "$SENSOR_DB_NAME" \
    --set=sensor_user="$SENSOR_DB_USER" \
    <<'SQL'
SET ROLE :"sensor_user";

CREATE TABLE IF NOT EXISTS SensorData
(
    nId BIGSERIAL PRIMARY KEY,
    nSourceId BIGINT NOT NULL,
    strMachineName VARCHAR(100) NOT NULL,
    fCurrent DOUBLE PRECISION NOT NULL,
    fVoltage DOUBLE PRECISION NOT NULL,
    nTemperature INTEGER NOT NULL,
    dtInsert TIMESTAMP NOT NULL,
    dtLoad TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uqSensorSourceMachine
        UNIQUE (nSourceId, strMachineName)
);

CREATE TABLE IF NOT EXISTS SensorMetrics
(
    nId BIGSERIAL PRIMARY KEY,
    nFirstSourceId BIGINT NOT NULL,
    nLastSourceId BIGINT NOT NULL,
    strMachineName VARCHAR(100) NOT NULL,
    dtWindowStart TIMESTAMP NOT NULL,
    dtWindowEnd TIMESTAMP NOT NULL,
    nRecords INTEGER NOT NULL,
    fAverageCurrent DOUBLE PRECISION,
    fMinimumCurrent DOUBLE PRECISION,
    fMaximumCurrent DOUBLE PRECISION,
    fAverageVoltage DOUBLE PRECISION,
    fMinimumVoltage DOUBLE PRECISION,
    fMaximumVoltage DOUBLE PRECISION,
    fAverageTemperature DOUBLE PRECISION,
    nMinimumTemperature INTEGER,
    nMaximumTemperature INTEGER,
    bTemperatureAlert BOOLEAN NOT NULL,
    dtProcessing TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uqSensorMetricsWindow
        UNIQUE (
            strMachineName,
            dtWindowStart,
            dtWindowEnd
        )
);

CREATE TABLE IF NOT EXISTS PipelineControl
(
    strMachineName VARCHAR(100) PRIMARY KEY,
    nLastProcessedSourceId BIGINT NOT NULL,
    dtLastProcessing TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);
SQL
