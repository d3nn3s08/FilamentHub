import paho.mqtt.client as mqtt
import ssl

# Example script to publish a test message to a printer MQTT broker.
# Replace `broker`, `serial_number` and `password` with real values before use.

broker = "192.168.178.41"
port = 8885
serial_number = "00M09A372601070"  # replace with real
topic = f"device/{serial_number}/report"
message = "Testnachricht"
username = "bblp"
password = "<ACCESS_CODE>"  # replace with real

client = mqtt.Client(protocol=mqtt.MQTTv311, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(username, password)
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.tls_insecure_set(True)

# Callbacks
def on_connect(client, userdata, flags, rc):
    print(f"Connected with code {rc}")

def on_publish(client, userdata, mid):
    print(f"Published, mid={mid}")

def on_log(client, userdata, level, buf):
    print(f"LOG: {buf}")

client.on_connect = on_connect
client.on_publish = on_publish
client.on_log = on_log

try:
    client.connect(broker, port)
    client.loop_start()
    result = client.publish(topic, message)
    result.wait_for_publish()
    client.loop_stop()
    client.disconnect()
except Exception as e:
    print(f"Error: {e}")
