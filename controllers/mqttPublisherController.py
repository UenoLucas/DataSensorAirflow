import sys
import os
current_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.append(current_dir)

from models.mqttModel import MqttModel

class MqttPublisherController:
    def __init__(self, broker, port, topic):
        self.mqtt_model = MqttModel(broker, port, topic)

    def connect(self):
        self.mqtt_model.connect()

    def disconnect(self):
        self.mqtt_model.disconnect()

    def publish_message(self, message):
        self.mqtt_model.publish(message)
