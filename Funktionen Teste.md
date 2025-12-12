## Funktionen-Teste (MQTT)

- Nach Server-Neustart im Debug-Center verbinden: Client-ID = Seriennummer (cloud_serial wird als Default-Topic genutzt), Broker = Drucker-IP, Port passend (8883 TLS / 6000 ohne TLS), Username `bblp`, Passwort = Access Code.
- Danach „Refresh Status“ klicken: erwartet `Active Connections > 0`, `Subscribed Topics` enthält `device/<seriennummer>/report`, Status-Anzeige „Verbunden“ (grün).
- Bei abgelehntem Connect (rc ≠ 0) muss der Status „Abgelehnt (rc=…)“ zeigen und Subscribed Topics/Active Connections auf 0 stehen.
- Topic-Liste prüfen: Unsubscribe-Button zeigt „×“, kein „?“ mehr.
- MQTT-Logrotation: prüfen, ob `logs/mqtt/mqtt_messages.log` sauber rotiert und keine Zugriffsfehler mehr auftreten (RotatingFileHandler aktiv).
