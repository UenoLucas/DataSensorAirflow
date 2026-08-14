import json

from controllers.sqliteController import SQLiteController
from models.mqttModel import MqttModel
from models.SensorData import SensorData

class MqttSubscriberController:
    def __init__(self, broker: str, port: int, topic: str, database_path: str, table_name: str):
        self.topic = topic

        self.mqtt_model = MqttModel(
            broker=broker,
            port=port,
            topic=topic,
        )

        self.sqlite_controller = SQLiteController(
            database_path,
            table_name,
        )

    def handle_message(self, client, userdata, msg):
        try:
            message = msg.payload.decode("utf-8")
            data = json.loads(message)
            sensor = SensorData(
                machine_name=data["strMachineName"],
                current=data["fA"],
                voltage=data["fV"],
                temperature=data["nTemperature"],
                insert_date=data["dtNow"]
            )

            self.sqlite_controller.insert_sensor_data(sensor)

        except json.JSONDecodeError as error:
            print(f"Mensagem JSON inválida: {error}")

        except KeyError as error:
            print(f"Campo ausente na mensagem: {error}")

        except Exception as error:
            print(f"Erro ao processar mensagem: {error}")

    def run(self):
        self.mqtt_model.connect()

        self.mqtt_model.client.subscribe(self.topic)
        self.mqtt_model.client.on_message = self.handle_message

        try:
            self.mqtt_model.client.loop_forever()

        except KeyboardInterrupt:
            print("Subscriber interrompido.")

        finally:
            self.mqtt_model.disconnect()