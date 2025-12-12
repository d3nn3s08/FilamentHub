import ssl
import paho.mqtt.client as mqtt

BROKER = "192.168.178.42"
PORT = 8883
USERNAME = "bblp"
PASSWORD = "28376525"
TOPIC = "#"

# Falls du ein Zertifikat brauchst, gib hier den Pfad an
CAFILE = None  # z.B. "ca.crt" oder None


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Verbunden mit Broker!")
        client.subscribe(TOPIC)
    else:
        print(f"Verbindung fehlgeschlagen, Code: {rc}")

def on_message(client, userdata, msg):
    print(f"Nachricht empfangen: {msg.topic}: {msg.payload}")

client = mqtt.Client(protocol=mqtt.MQTTv311)
client.username_pw_set(USERNAME, PASSWORD)

# TLS-Setup: Falls kein CA-File vorhanden ist, nutze einen permissiven Kontext (nur zu Testzwecken!)
if CAFILE:
    client.tls_set(CAFILE)
else:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    client.tls_set_context(ctx)
    client.tls_insecure_set(True)

client.on_connect = on_connect
client.on_message = on_message

print("Verbinde zu MQTT Broker...")
client.connect(BROKER, PORT)
client.loop_forever()
