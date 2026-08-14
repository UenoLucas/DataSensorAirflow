import os
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))
from controllers.mqttSubscriberController import MqttSubscriberController


def load_config() -> dict:
    config_path = Path(__file__).resolve().parent.parent / 'config' / "config.json"

    with config_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main():
    try:
        config = load_config()

        mqtt_config = config["mqtt"]
        db_config = config["db"]
        broker = os.getenv(
            "MQTT_HOST",
            mqtt_config["address"],
        )
        port = int(os.getenv(
            "MQTT_PORT",
            mqtt_config["port"],
        ))
        topic = os.getenv(
            "MQTT_TOPIC",
            mqtt_config["topic"],
        )
        database_path = Path(os.getenv(
            "SQLITE_DATABASE",
            db_config["filepath_db"],
        ))

        if not database_path.is_absolute():
            database_path = PROJECT_ROOT / database_path

        database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        subscriber = MqttSubscriberController(
            broker=broker,
            port=port,
            topic=topic,
            database_path=str(database_path),
            table_name=db_config["table_name"],
        )

        subscriber.run()

    except FileNotFoundError as error:
        print(f"Arquivo de configuração não encontrado: {error}")

    except json.JSONDecodeError as error:
        print(f"Arquivo config.json inválido: {error}")

    except KeyError as error:
        print(f"Configuração ausente no config.json: {error}")

    except Exception as error:
        print(f"Erro ao iniciar subscriber: {error}")


if __name__ == "__main__":
    main()
