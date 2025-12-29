# Integration externer Systeme

## Bambu Cloud Integration
- API-Key und Cloud-Seriennummer im Drucker hinterlegen
- Verbindung über LAN oder Cloud möglich
- Verbrauchsdaten und AMS-Status abrufen

## Klipper/Moonraker
- Moonraker-API-URL im Drucker hinterlegen
- Token/Key eintragen
- Jobs und Spulenstatus abrufen

## MQTT
- Broker-Adresse und Zugangsdaten konfigurieren
- Topics für AMS, Drucker und Spulen abonnieren
- Status und Verbrauchsdaten empfangen

## Beispiel-Konfigurationen
```yaml
bambu:
  api_key: "..."
  cloud_serial: "..."
klipper:
  moonraker_url: "http://192.168.1.100:7125"
  token: "..."
mqtt:
  broker: "mqtt://192.168.1.10"
  user: "user"
  password: "pass"
```

## Hinweise
- Integration ist optional und kann schrittweise aktiviert werden.
- Für Tests können Dummy-Daten genutzt werden.

