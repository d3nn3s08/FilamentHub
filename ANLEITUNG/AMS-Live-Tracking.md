# AMS-Live-Tracking & Verbrauch

- Verbrauch und Restbestand werden live aus AMS-Reports berechnet: Start-Stand wird gemerkt, aktuelle `remain_percent` fließt in Verbrauch (mm/g) und `weight_current` ein.
- Genauigkeit nur, wenn der Job von Beginn an gesehen wird. Steigen wir später ein, fehlt der Verbrauch vor unserem Einstieg.
- Abweichungen zur Slicer-Schätzung sind während des Drucks normal; zum Ende sollten sich die Werte annähern.
- `total_len` aus dem AMS wird verwendet, um Verbrauch/Rest in Metern zu zeigen (siehe AMS-Helper-Seite). Fehlt `total_len`, können keine m-Werte berechnet werden.

