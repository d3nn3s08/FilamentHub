import os, sys, json, ssl
import paho.mqtt.client as mqtt

# Projektroot einbinden
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from app.services.universal_mapper import UniversalMapper

# ==== HIER DEINE DRUCKERDATEN EINTRAGEN ====
PRINTER_IP = "192.168.178.41"       # <- deine X1C IP
USERNAME   = "bblp"               # <- fest
API_KEY    = "<ACCESS_CODE>"   # <- dein Key
MODEL      = "X1C"
# ===========================================
# Datei, in die wir die erste Payload speichern
OUTPUT_FILE = os.path.join("tests", "fixtures", "x1c_idle.json")

mapper = UniversalMapper(MODEL)
_received_once = False


def on_connect(client, userdata, flags, rc):
    print("[MQTT] Verbunden, rc =", rc)
    client.subscribe("device/+/report")
    print("[MQTT] Warte auf erste Live-Daten...")


def on_message(client, userdata, msg):
    global _received_once
    if _received_once:
        return  # nur erste Message interessiert uns

    _received_once = True

    print("\n=== ERSTE RAW PAYLOAD ===")
    try:
        raw = json.loads(msg.payload.decode("utf-8"))
    except Exception as e:
        print("[ERROR] JSON decode:", e)
        client.disconnect()
        return

    # Schön anzeigen
    print(json.dumps(raw, indent=2, ensure_ascii=False))

    # In Datei speichern
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
    print(f"\n[INFO] Payload in {OUTPUT_FILE} gespeichert.")

    # Direkt auch gemappte Daten anzeigen
    mapped = mapper.map(raw).to_dict()
    print("\n=== GEMAPPTE DATEN (PrinterData) ===")
    print(json.dumps(mapped, indent=2, ensure_ascii=False))

    # Verbindung beenden – wir haben, was wir brauchen
    client.disconnect()
    print("[MQTT] Beende nach erster Nachricht.")


def main():
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.username_pw_set(USERNAME, API_KEY)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)

    client.on_connect = on_connect
    client.on_message = on_message

    print(f"[CONNECT] Verbinde zu {PRINTER_IP}:8883 ...")
    client.connect(PRINTER_IP, 8883, 60)
    client.loop_forever()


if __name__ == "__main__":
    main()
