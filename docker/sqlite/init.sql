PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 30000;

CREATE TABLE IF NOT EXISTS SensorData
(
    nId INTEGER PRIMARY KEY AUTOINCREMENT,
    strMachineName TEXT NOT NULL,
    fA REAL NOT NULL,
    fV REAL NOT NULL,
    nTemperature INTEGER NOT NULL,
    dtInsert TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS IX_SensorData_MachineDate
ON SensorData
(
    strMachineName,
    dtInsert
);