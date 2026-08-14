from dataclasses import dataclass

@dataclass
class SensorData:
    machine_name: str
    current: float
    voltage: float
    temperature: int
    insert_date: str