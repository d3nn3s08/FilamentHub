# FilamentHub - Kurzanleitung

## 1. Drucker hinzufügen

1. Öffne das Webinterface (z. B. http://localhost:8085).
2. Navigiere zur Seite "Drucker".
3. Klicke auf "Neuen Drucker hinzufügen".
4. Trage die Drucker-Daten ein:
   - Name
   - Typ (Bambu, Klipper, Manual)
   - IP-Adresse und Port (optional)
   - Cloud-Seriennummer/API-Key (optional)
5. Speichere den Drucker. Er erscheint nun in der Druckerliste.

## 2. Filament/Material verwalten

1. Gehe zur Seite "Materialien".
2. Klicke auf "Neues Material hinzufügen".
3. Gib die Materialdaten ein:
   - Name, Typ, Farbe, Hersteller, Dichte, Durchmesser
4. Speichere das Material. Es erscheint in der Materialliste.

## 3. Spulen verwalten

1. Gehe zur Seite "Spulen".
2. Klicke auf "Neue Spule hinzufügen".
3. Wähle das Material aus und gib die Spulendaten ein:
   - Gewicht, Farbe, Hersteller, AMS-Slot (optional)
4. Speichere die Spule. Sie erscheint in der Spulenliste.

## 4. Material/Spule einem Drucker zuordnen

- Beim Start eines Drucks wird das Material und die passende Spule automatisch vorgeschlagen.
- Du kannst die Zuordnung manuell ändern, falls mehrere Spulen passen.

## 5. Status und Verbrauch überwachen

- Im Dashboard siehst du den aktuellen Verbrauch, Restgewicht und Warnungen (z. B. "Spule fast leer").
- Die Historie zeigt, wann und auf welchem Drucker eine Spule zuletzt genutzt wurde.

## 6. Debugcenter nutzen

- Über die Seite "Debug" kannst du Logs und Systemstatus einsehen.
- Live-Logs werden per Websocket gestreamt.

