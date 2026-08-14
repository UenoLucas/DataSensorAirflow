# code to create database sqlite environment
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATABASE_PATH = Path(
    os.getenv(
        "SQLITE_DATABASE",
        PROJECT_ROOT / "database" / "LocalData.db",
    )
)

# script sql to create the main table from project
INIT_SQL_PATH = Path(
    os.getenv(
        "SQLITE_INIT_SQL",
        PROJECT_ROOT / "docker" / "sqlite" / "init.sql",
    )
)


def initialize_sqlite() -> None:
    if not INIT_SQL_PATH.exists():
        raise FileNotFoundError(
            f"SQLite initialization script not found: "
            f"{INIT_SQL_PATH}"
        )

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    init_script = INIT_SQL_PATH.read_text(
        encoding="utf-8",
    )

    print(
        f"Initializing SQLite database: {DATABASE_PATH}",
        flush=True,
    )

    with sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    ) as connection:
        connection.executescript(init_script)
        connection.commit()

        cursor = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        )

        tables = [
            row[0]
            for row in cursor.fetchall()
        ]

    print(
        "SQLite initialization completed. "
        f"Tables: {', '.join(tables)}",
        flush=True,
    )


if __name__ == "__main__":
    initialize_sqlite()