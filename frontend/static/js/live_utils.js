// FilamentHub Utility-Funktionen für Live-Daten und Fallback
// Diese Seite zeigt, wie du Live-Daten und Fallbacks einfach und robust nutzen kannst.

/**
 * Gibt den Wert aus den Live-Daten zurück, oder (bei Fehlen) aus der Datenbank, oder einen Fallback.
 * @param {object} printer - Das Druckerobjekt (enthält .live und DB-Felder)
 * @param {string[]} keys - Array von Schlüsseln, die nacheinander geprüft werden (zuerst live, dann DB)
 * @param {any} fallback - Wert, falls nichts gefunden wird (Standard: "-")
 * @returns {any}
 */
function getLiveOrDb(printer, keys, fallback = "-") {
    for (const key of keys) {
        if (printer.live && printer.live[key] !== undefined && printer.live[key] !== null) return printer.live[key];
        if (printer[key] !== undefined && printer[key] !== null) return printer[key];
    }
    return fallback;
}

// Beispiel-Nutzung:
// const nozzle = getLiveOrDb(printer, ["nozzle_temper", "nozzle_temp"]);
// const bed = getLiveOrDb(printer, ["bed_temper", "bed_temp"]);
// const filament = getLiveOrDb(printer, ["tray_type", "filament_material", "printer_type"]);

// Du kannst beliebig viele Fallbacks angeben:
// const foo = getLiveOrDb(printer, ["live_key1", "db_key1", "db_key2"], "(unbekannt)");

// Diese Funktion kannst du in allen deinen JS-Dateien importieren oder direkt einfügen.

// Für komplexere Fälle (z.B. AMS/Tray) kannst du eigene Hilfsfunktionen nach diesem Muster bauen.

// ---
// Tipp: Schreibe dir eigene kleine Hilfsfunktionen für wiederkehrende Spezialfälle (z.B. Filamentanzeige, Statusanzeige, ...)
// und halte deinen Code so übersichtlich und wartbar!
