from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import psycopg2
from dash import Dash, Input, Output, callback, dcc, html
from psycopg2 import sql


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT_DIR / "config" / "config.json"


def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}

    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


config = load_config()
postgres_config = config.get("postgres", {})

POSTGRES_HOST = os.getenv(
    "POSTGRES_HOST",
    postgres_config.get("host", "sensor-postgres"),
)

POSTGRES_PORT = int(
    os.getenv(
        "POSTGRES_PORT",
        postgres_config.get("port", 5432),
    )
)

POSTGRES_DATABASE = os.getenv(
    "POSTGRES_DATABASE",
    postgres_config.get("database", "sensor_db"),
)

POSTGRES_USER = os.getenv(
    "POSTGRES_USER",
    postgres_config.get("user", "sensor_user"),
)

POSTGRES_PASSWORD = os.getenv(
    "POSTGRES_PASSWORD",
    postgres_config.get("password", "sensor_password"),
)

METRICS_TABLE_NAME = postgres_config.get(
    "metrics_table",
    "SensorMetrics",
).lower()


def get_postgres_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DATABASE,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        connect_timeout=10,
    )


def load_sensor_metrics(minutes: int = 60) -> pd.DataFrame:
    query = sql.SQL(
        """
        SELECT
            strmachinename AS "Machine",
            dtwindowstart AS "WindowStart",
            dtwindowend AS "WindowEnd",
            nfirstsourceid AS "FirstSourceId",
            nlastsourceid AS "LastSourceId",
            nrecords AS "Records",
            faveragecurrent AS "AverageCurrent",
            fminimumcurrent AS "MinimumCurrent",
            fmaximumcurrent AS "MaximumCurrent",
            faveragevoltage AS "AverageVoltage",
            fminimumvoltage AS "MinimumVoltage",
            fmaximumvoltage AS "MaximumVoltage",
            faveragetemperature AS "AverageTemperature",
            nminimumtemperature AS "MinimumTemperature",
            nmaximumtemperature AS "MaximumTemperature",
            btemperaturealert AS "TemperatureAlert",
            dtprocessing AS "ProcessingDate"

        FROM {metrics_table}
        WHERE dtwindowstart >=
            (
                CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo'
                - make_interval(mins => %s)
            )
        ORDER BY
            strmachinename,
            dtwindowstart
        """
    ).format(
        metrics_table=sql.Identifier(METRICS_TABLE_NAME)
    )

    with get_postgres_connection() as connection:
        dataframe = pd.read_sql_query(
            query.as_string(connection),
            connection,
            params=(int(minutes),),
        )

    if dataframe.empty:
        return dataframe

    dataframe["WindowStart"] = pd.to_datetime(
        dataframe["WindowStart"],
        errors="coerce",
    )

    dataframe["WindowEnd"] = pd.to_datetime(
        dataframe["WindowEnd"],
        errors="coerce",
    )

    dataframe["ProcessingDate"] = pd.to_datetime(
        dataframe["ProcessingDate"],
        errors="coerce",
    )

    return dataframe.dropna(
        subset=["Machine", "WindowStart"]
    )


def create_empty_figure(title: str):
    figure = px.line(title=title)

    figure.update_layout(
        xaxis_title="Hour",
        yaxis_title="No register",
        template="plotly_dark",
        margin={
            "l": 40,
            "r": 20,
            "t": 70,
            "b": 40,
        },
    )

    return figure


def configure_figure(
    figure,
    title: str,
    y_axis_title: str,
):
    figure.update_layout(
        title=title,
        title_font={
            "size": 22,
        },
        xaxis_title="Window Start",
        yaxis_title=y_axis_title,
        xaxis_tickformat="%H:%M",
        hovermode="x unified",
        legend_title_text="Metric",
        template="plotly_dark",
        margin={
            "l": 50,
            "r": 20,
            "t": 70,
            "b": 50,
        },
        transition_duration=300
    )

    figure.update_traces(
    line_width=3
    )

    return figure


def create_metric_figure(
    dataframe: pd.DataFrame,
    average_column: str,
    minimum_column: str,
    maximum_column: str,
    title: str,
    y_axis_title: str,
):
    chart_dataframe = dataframe[
        [
            "WindowStart",
            average_column,
            minimum_column,
            maximum_column,
        ]
    ].copy()

    chart_dataframe = chart_dataframe.rename(
        columns={
            average_column: "Average",
            minimum_column: "Min",
            maximum_column: "Max",
        }
    )

    long_dataframe = chart_dataframe.melt(
        id_vars="WindowStart",
        value_vars=[
            "Average",
            "Min",
            "Max",
        ],
        var_name="Metric",
        value_name="Value",
    )

    figure = px.line(
        long_dataframe,
        x="WindowStart",
        y="Value",
        color="Metric",
        markers=True,
    )

    return configure_figure(
        figure,
        title=title,
        y_axis_title=y_axis_title,
    )


def create_kpi_card(
    title: str,
    value: str,
    subtitle: str = "",
):
    return dbc.Card(
        dbc.CardBody(
            [
                html.H6(
                    title,
                    className="text-uppercase text-muted",
                ),
                html.H3(
                    value,
                    className="mb-1",
                ),
                html.Small(
                    subtitle,
                    className="text-muted",
                ),
            ]
        ),
        className="h-100 shadow-sm",
    )


app = Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.SUPERHERO,
    ],
)

app.title = "Machine Monitoring"

app.layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                [
                    html.H1(
                        "Machine Monitoring",
                        className="text-center mt-4 mb-2",
                    ),
                    html.P(
                        (
                            "Metrics calculated over five-minute time windows",
                        ),
                        className=(
                            "text-center text-muted "
                            "mb-4"
                        ),
                    ),
                ]
            )
        ),

        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Label(
                            "Machine",
                            className="fw-bold",
                        ),
                        dcc.Dropdown(
                            id="machine-dropdown",
                            options=[],
                            value=None,
                            clearable=False,
                            style={
                                "color": "black",
                            },
                        ),
                    ],
                    md=6,
                ),

                dbc.Col(
                    [
                        html.Label(
                            "Period",
                            className="fw-bold",
                        ),
                        dcc.Dropdown(
                            id="period-dropdown",
                            options=[
                                {"label": "Last hour", "value": 60},
                                {"label": "Last 6 hours", "value": 360},
                                {"label": "Last 12 hours", "value": 720},
                                {"label": "Last 24 hours", "value": 1440},
                            ],
                            value=60,
                            clearable=False,
                            style={
                                "color": "black",
                            },
                        ),
                    ],
                    md=6,
                ),
            ],
            className="mb-4",
        ),

        html.Div(
            id="connection-message",
            className="text-center mb-3",
        ),

        dbc.Row(
            [
                dbc.Col(
                    html.Div(id="records-card"),
                    md=3,
                    className="mb-3",
                ),
                dbc.Col(
                    html.Div(id="current-card"),
                    md=3,
                    className="mb-3",
                ),
                dbc.Col(
                    html.Div(id="voltage-card"),
                    md=3,
                    className="mb-3",
                ),
                dbc.Col(
                    html.Div(id="temperature-card"),
                    md=3,
                    className="mb-3",
                ),
            ]
        ),

        dbc.Row(
            [
                dbc.Col(
                    dcc.Graph(id="current-graph"),
                    lg=6,
                ),
                dbc.Col(
                    dcc.Graph(id="voltage-graph"),
                    lg=6,
                ),
            ]
        ),

        dbc.Row(
            dbc.Col(
                dcc.Graph(id="temperature-graph"),
                lg=12,
            )
        ),

        dbc.Row(
            dbc.Col(
                html.Div(
                    id="last-update",
                    className="text-center text-muted my-3",
                )
            )
        ),

        dcc.Interval(
            id="update-interval",
            interval=30_000,
            n_intervals=0,
        ),
    ],
    fluid=True,
)


@callback(
    Output("machine-dropdown", "options"),
    Output("machine-dropdown", "value"),
    Output("current-graph", "figure"),
    Output("voltage-graph", "figure"),
    Output("temperature-graph", "figure"),
    Output("records-card", "children"),
    Output("current-card", "children"),
    Output("voltage-card", "children"),
    Output("temperature-card", "children"),
    Output("connection-message", "children"),
    Output("last-update", "children"),
    Input("machine-dropdown", "value"),
    Input("period-dropdown", "value"),
    Input("update-interval", "n_intervals"),
)
def update_dashboard(
    selected_machine,
    selected_period,
    _,
):
    try:
        selected_period = int(selected_period or 60)
        dataframe = load_sensor_metrics(
            minutes=int(selected_period)
        )

    except Exception as exception:
        error_message = (
            "Error Postgresql connection: "
            f"{exception}"
        )

        return (
            [],
            None,
            create_empty_figure("Current"),
            create_empty_figure("Voltage"),
            create_empty_figure("Temperature"),
            create_kpi_card("Registers", "0"),
            create_kpi_card("Average Current", "--"),
            create_kpi_card("Average Voltage", "--"),
            create_kpi_card("Temperature", "--"),
            dbc.Alert(
                error_message,
                color="danger",
            ),
            "Fail to update.",
        )

    if dataframe.empty:
        return (
            [],
            None,
            create_empty_figure("Current"),
            create_empty_figure("Voltage"),
            create_empty_figure("Temperature"),
            create_kpi_card("Registers", "0"),
            create_kpi_card("Average Current", "--"),
            create_kpi_card("Average Voltage", "--"),
            create_kpi_card("Temperature", "--"),
            dbc.Alert(
                "No metrics found for the selected time range.",
                color="warning",
            ),
            (
                "Last query: "
                f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            ),
        )

    machines = sorted(
        dataframe["Machine"]
        .dropna()
        .unique()
        .tolist()
    )

    machine_options = [
        {
            "label": machine,
            "value": machine,
        }
        for machine in machines
    ]

    if selected_machine not in machines:
        selected_machine = machines[0]

    filtered_dataframe = dataframe[
        dataframe["Machine"] == selected_machine
    ].copy()

    filtered_dataframe = filtered_dataframe.sort_values(
        "WindowStart"
    )

    current_figure = create_metric_figure(
        filtered_dataframe,
        average_column="AverageCurrent",
        minimum_column="MinimumCurrent",
        maximum_column="MaximumCurrent",
        title="Current",
        y_axis_title="Amperes",
    )

    voltage_figure = create_metric_figure(
        filtered_dataframe,
        average_column="AverageVoltage",
        minimum_column="MinimumVoltage",
        maximum_column="MaximumVoltage",
        title="Voltage",
        y_axis_title="Volts",
    )

    temperature_figure = create_metric_figure(
        filtered_dataframe,
        average_column="AverageTemperature",
        minimum_column="MinimumTemperature",
        maximum_column="MaximumTemperature",
        title="Temperature",
        y_axis_title="°C",
    )

    latest_row = filtered_dataframe.iloc[-1]

    total_records = int(
        filtered_dataframe["Records"].sum()
    )

    average_current = latest_row["AverageCurrent"]
    average_voltage = latest_row["AverageVoltage"]
    maximum_temperature = latest_row["MaximumTemperature"]

    has_temperature_alert = bool(
        filtered_dataframe["TemperatureAlert"].fillna(False).any()
    )

    alert_text = (
        "Temperature alert active"
        if has_temperature_alert
        else "Temperature within the acceptable range"
    )

    alert_color = (
        "danger"
        if has_temperature_alert
        else "success"
    )

    records_card = create_kpi_card(
        "Processed register",
        str(total_records),
        (
            f"{len(filtered_dataframe)} "
            "Grouped by a range of 5 minutes"
        ),
    )

    current_card = create_kpi_card(
        "Average current now",
        (
            f"{average_current:.2f} A"
            if pd.notna(average_current)
            else "--"
        ),
        "Latest processed window",
    )

    voltage_card = create_kpi_card(
        "Voltage Average",
        (
            f"{average_voltage:.2f} V"
            if pd.notna(average_voltage)
            else "--"
        ),
        "Latest processed window",
    )

    temperature_card = dbc.Card(
        dbc.CardBody(
            [
                html.H6(
                    "Max Temperature",
                    className="text-uppercase text-muted",
                ),
                html.H3(
                    (
                        f"{maximum_temperature:.0f} °C"
                        if pd.notna(maximum_temperature)
                        else "--"
                    ),
                    className="mb-1",
                ),
                dbc.Badge(
                    alert_text,
                    color=alert_color,
                ),
            ]
        ),
        className="h-100 shadow-sm",
    )

    connection_message = dbc.Alert(
        (
            f"Showing metrics from machine "
            f"{selected_machine}."
        ),
        color="success",
        className="py-2",
    )

    last_processing = latest_row["ProcessingDate"]

    if pd.notna(last_processing):
        last_processing_text = last_processing.strftime(
            "%d/%m/%Y %H:%M:%S"
        )
    else:
        last_processing_text = "Not informed"

    last_update = (
        f"Last update dashboard: "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | "
        f"Last processing: {last_processing_text}"
    )

    return (
        machine_options,
        selected_machine,
        current_figure,
        voltage_figure,
        temperature_figure,
        records_card,
        current_card,
        voltage_card,
        temperature_card,
        connection_message,
        last_update,
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8050,
        debug=False,
    )