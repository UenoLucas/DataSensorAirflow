from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from airflow.providers.postgres.hooks.postgres import PostgresHook


class PostgreSQLModel:
    def __init__(self, connection_id: str):
        self.connection_id = connection_id
        self.postgres_hook = PostgresHook(
            postgres_conn_id=connection_id
        )

    def fetch_one(self, query: str, parameters: Sequence[Any] | None = None):
        connection = self.postgres_hook.get_conn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, parameters)
                return cursor.fetchone()
        finally:
            connection.close()

    def fetch_all(self, query: str, parameters: Sequence[Any] | None = None):
        connection = self.postgres_hook.get_conn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, parameters)
                return cursor.fetchall()
        finally:
            connection.close()

    def execute(self, query: str, parameters: Sequence[Any] | None = None) -> int:
        connection = self.postgres_hook.get_conn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, parameters)
                affected_rows = cursor.rowcount

            connection.commit()
            return affected_rows

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def execute_many(self, query: str,rows: Iterable[Sequence[Any]] ) -> int:
        connection = self.postgres_hook.get_conn()

        try:
            with connection.cursor() as cursor:
                cursor.executemany(query, rows)
                affected_rows = cursor.rowcount

            connection.commit()
            return affected_rows

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def execute_returning_one(self, query: str, parameters: Sequence[Any] | None = None):
        connection = self.postgres_hook.get_conn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, parameters)
                result = cursor.fetchone()

            connection.commit()
            return result

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()