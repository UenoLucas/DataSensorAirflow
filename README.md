# Data Sensor Airflow

A local data-engineering project that simulates machine sensor readings,
ingests MQTT messages into SQLite, transfers the raw data to PostgreSQL with
Apache Airflow, calculates metrics in five-minute windows, and displays the
results in a Dash dashboard.

## Architecture

```text
Publisher (host)
    |
    v
Mosquitto MQTT (Docker)
    |
    v
Subscriber (Docker) -> SQLite
                         |
                         v
              Airflow: SQLite to PostgreSQL
                         |
                         v
                 PostgreSQL SensorData
                         |
                         v
                Airflow: Sensor Metrics
                         |
                         v
                PostgreSQL SensorMetrics
                         |
                         v
                    Dash Dashboard
```

## Technologies

- Python 3.10
- Apache Airflow 3.3
- PostgreSQL 16
- SQLite
- MQTT
- Dash and Plotly
- Docker Compose

## Project structure

```text
DataSensorAirflow/
├── config/                 # Non-secret application settings
├── controllers/
├── dags/
│   ├── sqliteToPostgres.py
│   └── sensorProcessing.py
├── dashboard/
│   └── DashInterface.py
├── database/               # Runtime SQLite database (ignored by Git)
├── docker/
│   ├── mosquitto/
│   ├── postgres/
│   └── sqlite/
├── models/
├── scripts/
│   ├── PublisherMqtt.py
│   ├── SubscriberMqtt.py
│   └── initSqlite.py
├── .env.example
├── docker-compose.yml
├── Dockerfile.airflow
├── Dockerfile.app
├── requirements-airflow.txt
└── requirements-app.txt
```

## Pipeline

1. The publisher simulates machine current, voltage, and temperature and
   publishes readings to MQTT.
2. The subscriber stores MQTT messages in SQLite.
3. The `sqlite_to_postgres` DAG incrementally loads raw readings into the
   PostgreSQL `SensorData` table every minute.
4. The `sensor_processing` DAG calculates five-minute aggregates in
   `SensorMetrics` every five minutes.
5. The Dash application displays the aggregated metrics and alerts.

## Requirements

- Docker with the Compose plugin
- Python 3.10 or newer to run the publisher on the host

## Configuration

Create the local environment file:

```bash
cp .env.example .env
```

On Linux, set `AIRFLOW_UID` to your host user ID so bind-mounted files have
the correct ownership:

```bash
sed -i "s/^AIRFLOW_UID=.*/AIRFLOW_UID=$(id -u)/" .env
```

Replace the example passwords and `AIRFLOW_JWT_SECRET` in `.env`. The `.env`
file is ignored by Git. The committed `config/config.json` contains only
non-secret defaults.

MQTT settings use the following precedence:

1. `MQTT_HOST`, `MQTT_PORT`, and `MQTT_TOPIC` environment variables;
2. values under `mqtt` in `config/config.json`.

The default broker address is `localhost`, which is suitable for the
publisher running on the host. Docker Compose sets `MQTT_HOST=mosquitto` for
the subscriber on the internal Docker network.

## Running the project

Build and start all services:

```bash
docker compose up -d --build
```

The one-shot `airflow-init` and `sqlite-init` services should finish with exit
code `0`. Check the complete state with:

```bash
docker compose ps -a
```

Follow the logs with:

```bash
docker compose logs -f
```

No manual `docker compose up airflow-init` step is required because the
remaining Airflow services depend on its successful completion.

## Running the publisher

Create a Python virtual environment on the host and install the application
dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-app.txt
python scripts/PublisherMqtt.py --machine Machine1
```

To use a broker other than the default:

```bash
MQTT_HOST=192.0.2.10 MQTT_PORT=1883 \
python scripts/PublisherMqtt.py --machine Machine1
```

Stop publishing with `Ctrl+C`.

## Access

- Airflow: <http://127.0.0.1:8080>
- Dashboard: <http://127.0.0.1:8050>
- PostgreSQL: `127.0.0.1:5433` by default
- Mosquitto: `127.0.0.1:1883` by default

The Airflow username comes from `AIRFLOW_USERNAME`. With Simple Auth Manager,
the generated password is stored locally in
`config/simple_auth_manager_passwords.json.generated`; that file is ignored
by Git.

Host ports may be changed in `.env`. All published ports bind to `127.0.0.1`
and are not exposed on the LAN by default.

## Resetting local data

Stop the containers while preserving databases:

```bash
docker compose down
```

To intentionally delete the PostgreSQL and Mosquitto volumes and rebuild all
local data from scratch:

```bash
docker compose down --volumes
```

The SQLite database is a bind-mounted file under `database/` and must be
removed separately if a complete reset is desired.