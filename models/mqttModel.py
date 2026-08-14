import paho.mqtt.client as mqtt

class MqttModel:
    def __init__(self, broker, port, topic, qos = 0, tls = False):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.qos = qos
        self.tls = tls
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def connect(self):
        self.client.connect(host=self.broker, port = self.port, keepalive= 60)

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, message):
        self.client.publish(self.topic, message)

    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code:" + str(rc))
        self.client.subscribe(self.topic)

    def on_message(self, client, userdata, msg):
        return msg.payload.decode()
