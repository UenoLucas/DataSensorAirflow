import sqlite3


class SQLiteModel:
    def __init__(self, db_name):
        self.db_name = db_name
        self.connection = None
        self.cursor = None
        self.connect()

    def connect(self):
        try:
            self.connection = sqlite3.connect(self.db_name)
            # modo para não dar lock
            self.connection.execute(
                "PRAGMA journal_mode=WAL;"
            )

            self.connection.execute(
                "PRAGMA busy_timeout=10000;"
            )

            self.cursor = self.connection.cursor()
            print(f"Connected with the database: {self.db_name}")

        except sqlite3.Error as error:
            self.connection = None
            self.cursor = None
            raise RuntimeError(
                f"Error connecting to database '{self.db_name}': {error}"
            ) from error

    def disconnect(self):
        if self.cursor is not None:
            self.cursor.close()

        if self.connection is not None:
            self.connection.close()

        self.cursor = None
        self.connection = None

    def execute_query(self, query, parameters=None):
        if self.cursor is None or self.connection is None:
            raise RuntimeError("SQLite connection is not initialized.")

        try:
            if parameters is not None:
                self.cursor.execute(query, parameters)
            else:
                self.cursor.execute(query)

            if query.lstrip().lower().startswith("select"):
                return self.cursor.fetchall()

            self.connection.commit()
            return []

        except sqlite3.Error as error:
            raise RuntimeError(
                f"Error executing SQLite query: {error}"
            ) from error

    def fetch_all_rows(self):
        if self.cursor is None:
            raise RuntimeError("SQLite cursor is not initialized.")

        return self.cursor.fetchall()

    def fetch_one_row(self):
        if self.cursor is None:
            raise RuntimeError("SQLite cursor is not initialized.")

        return self.cursor.fetchone()