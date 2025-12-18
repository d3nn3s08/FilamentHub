
import paho.mqtt.client as mqtt
import ssl

broker = "192.168.178.41"

port = 8885
# Thema nach Vorgabe, Seriennummer bitte ersetzen:
serial_number = "00M09A372601070"  # <-- hier echte Seriennummer eintragen
# englisches Thema zum Testen:
topic = f"device/{serial_number}/report"
message = "Testnachricht"
username = "bblp"
password = "<ACCESS_CODE>"  # <-- Passwort aus Drucker-Netzwerkeinstellungen


client = mqtt.Client(protocol=mqtt.MQTTv311, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(username, password)
# TLS explizit ohne Zertifikatsprüfung
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.tls_insecure_set(True)

# Callback-Funktionen für Logging
def on_connect(client, userdata, flags, rc):
	print(f"Verbindung hergestellt mit Code {rc}")

def on_publish(client, userdata, mid):
	print(f"Nachricht veröffentlicht, mid={mid}")

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
	print(f"Fehler: {e}")
