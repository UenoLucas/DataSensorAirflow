import sys
import os
current_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir,"scripts"))
sys.path.append(os.path.join(current_dir,"controllers"))
sys.path.append(os.path.join(current_dir,"models"))
import argparse
from controllers.mqttPublisherController import MqttPublisherController
import json
import datetime
import time
import math
import random
from pathlib import Path

class PowerMachineSimulation:
    def __init__(self):
        self.base_voltage = 220.0
        self.base_current = 10.0
        self.temperature = 70.0
        self.start_time = time.monotonic()

    def voltage_function(self, elapsed_seconds):
        voltage = (
            self.base_voltage
            + 4 * math.sin(2 * math.pi * 0.05 * elapsed_seconds)
            + random.uniform(-1.0, 1.0)
        )

        return round(voltage, 2)

    def current_function(self, elapsed_seconds):
        current = (
            self.base_current
            + 3 * math.sin(2 * math.pi * 0.1 * elapsed_seconds)
            + random.uniform(-0.5, 0.5)
        )

        return round(max(current, 0), 2)

    def temperature_function(self, current):
        target_temperature = 65 + current * 1.2

        # aproxima lentamente a temperatura do valor esperado para a carga
        self.temperature += (
            target_temperature - self.temperature
        ) * 0.05

        # representa uma pequena variação natural do sensor
        self.temperature += random.uniform(-0.2, 0.2)

        return round(self.temperature, 2)

class Publish_Data():
    def __init__(self, machine_name= ""):
        BASE_DIR = Path(__file__).resolve().parent.parent
        CONFIG_FILE = BASE_DIR / 'config' / "config.json"
        with open(CONFIG_FILE, "r") as file:
            json_file = json.load(file)
        try:
            object_mqtt = json_file["mqtt"]
            self.adress_broker = os.getenv(
                "MQTT_HOST",
                object_mqtt["address"],
            )
            self.port = int(os.getenv(
                "MQTT_PORT",
                object_mqtt["port"],
            ))
            self.topic = os.getenv(
                "MQTT_TOPIC",
                object_mqtt["topic"],
            )
            self.machine_name = machine_name
        except Exception as e:
            print("problem to read json:"+e.args)
        self.mqtt_object = MqttPublisherController(self.adress_broker,self.port,self.topic)
        self.power_data = PowerMachineSimulation()
        pass


    def send_data(self,):
        self.mqtt_object.connect()
        i = 1
        char = "/"
        original_char=char
        while(True):
            # usa o mesmo instante para calcular todas as grandezas da leitura
            elapsed_seconds = (
                time.monotonic() - self.power_data.start_time
            )
            current = self.power_data.current_function(elapsed_seconds)
            tension = self.power_data.voltage_function(elapsed_seconds)
            temperature = self.power_data.temperature_function(current)
            datetime_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            obj = {"strMachineName":self.machine_name,"fA":current,"fV":tension,"nTemperature":temperature,"dtNow":datetime_now}
            self.mqtt_object.publish_message(json.dumps(obj))
            sys.stdout.write(f"\rData rows sent: {i} {char}")
            sys.stdout.flush()
            i += 1
            if i%2==0:
                char="\\"
            else:
                char="/"
            time.sleep(2)

if __name__=="__main__":
    parser = argparse.ArgumentParser(description="Publish data script")
    parser.add_argument("--machine", type=str, help="Machine name")
    args = parser.parse_args()
    obj = Publish_Data(machine_name=args.machine)
    try:
        obj.send_data()
    except Exception as ex:
        print(f"Error: {ex}")
    pass
