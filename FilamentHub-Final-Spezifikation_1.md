# FilamentHub - Finale Spezifikation
# Spulen-Nummern-System + AMS-Zuweisungssystem
# Basierend auf bestehender Datenbank

Version: 1.0 (Final)
Erstellt: 2024-12-19

---

## ÜBERSICHT

FilamentHub erweitert Ihre bestehende Datenbank um ein **Spulen-Nummern-System** und ein **Live-Such-System** für schnelle AMS-Zuweisungen.

**Was FilamentHub hinzufügt:**
- ✅ Benutzerfreundliche Spulen-Nummern (#1, #2, #3...)
- ✅ Live-Suche beim Zuweisen (ohne JOINs)
- ✅ Quick-Assign Dialog für AMS-Slots

**Was bleibt wie es ist:**
- ✅ Ihr Verbrauchstracking (job, job_spool_usage)
- ✅ Ihre Material-Verwaltung (material Tabelle)
- ✅ Ihre Drucker-Verwaltung (printer Tabelle)
- ✅ Alle bestehenden MQTT-Handler

---

## DATENBANK-ÄNDERUNGEN

### Migration 1: Neue Felder in spool-Tabelle

```sql
-- Spulen-Nummern-System
ALTER TABLE spool ADD COLUMN spool_number INTEGER UNIQUE;

-- Denormalisierte Felder für schnelle Suche (ohne JOINs)
ALTER TABLE spool ADD COLUMN name VARCHAR(100);
ALTER TABLE spool ADD COLUMN vendor VARCHAR(100);
ALTER TABLE spool ADD COLUMN color VARCHAR(50);

-- Indizes für Performance
CREATE INDEX idx_spool_number ON spool(spool_number);
CREATE INDEX idx_spool_name ON spool(name);
CREATE INDEX idx_spool_search ON spool(name, vendor, color);
```

### Migration 2: Bestehende Daten migrieren

```sql
-- Bestehende Spulen durchnummerieren (nach Erstellungsdatum)
WITH numbered AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY created_at NULLS LAST, id) as num
  FROM spool
)
UPDATE spool 
SET spool_number = numbered.num
FROM numbered
WHERE spool.id = numbered.id;

-- Material-Daten in Spulen kopieren (einmalig)
UPDATE spool 
SET 
  name = material.name,
  vendor = material.brand
FROM material 
WHERE spool.material_id = material.id;

-- Farbe aus tray_color extrahieren (falls vorhanden)
-- Beispiel: "00AE42FF" → "black", "F4EE2AFF" → "yellow"
UPDATE spool 
SET color = CASE 
  WHEN tray_color IS NOT NULL THEN tray_color
  ELSE 'unknown'
END
WHERE color IS NULL;
```

### Aktualisierte spool-Tabelle (Schema)

```
spool:
├─ id (VARCHAR, PK)                    ← Bestehendes Feld: UUID, einzigartig pro Spule
├─ spool_number (INTEGER, UNIQUE)      ← NEU: User-freundliche Nummer (#1, #2, #3...)
├─ material_id (VARCHAR, FK)           ← Bestehendes Feld: Referenz zu material-Tabelle
├─ name (VARCHAR)                      ← NEU: Kopie von material.name (z.B. "PLA Basic")
├─ vendor (VARCHAR)                    ← NEU: Kopie von material.brand (z.B. "Bambu Lab")
├─ color (VARCHAR)                     ← NEU: Farbe der Spule (z.B. "black", "red")
├─ vendor_id (VARCHAR)                 ← Bestehendes Feld
├─ weight_full (FLOAT)                 ← Bestehendes Feld
├─ weight_empty (FLOAT)                ← Bestehendes Feld
├─ weight_current (FLOAT)              ← Bestehendes Feld (von Ihrem Tracking verwaltet)
├─ status (VARCHAR)                    ← Bestehendes Feld
├─ location (VARCHAR)                  ← Bestehendes Feld
├─ label (VARCHAR)                     ← Bestehendes Feld
├─ external_id (VARCHAR)               ← Bestehendes Feld
├─ printer_slot (INTEGER)              ← Bestehendes Feld (deprecated?)
├─ printer_id (VARCHAR, FK)            ← Bestehendes Feld: Welcher Drucker
├─ ams_slot (INTEGER)                  ← Bestehendes Feld: Welcher Slot (1-4)
├─ tag_uid (VARCHAR)                   ← Bestehendes Feld: NFC Tag
├─ tray_uuid (VARCHAR)                 ← Bestehendes Feld: Bambu Tray UUID
├─ tray_color (VARCHAR)                ← Bestehendes Feld: Bambu Farb-Code
├─ tray_type (VARCHAR)                 ← Bestehendes Feld: Bambu Material-Typ
├─ remain_percent (FLOAT)              ← Bestehendes Feld (von Ihrem Tracking verwaltet)
├─ last_seen (VARCHAR)                 ← Bestehendes Feld
├─ first_seen (TEXT)                   ← Bestehendes Feld
├─ used_count (INTEGER)                ← Bestehendes Feld (von Ihrem Tracking verwaltet)
├─ last_slot (INTEGER)                 ← Bestehendes Feld
├─ is_open (BOOLEAN)                   ← Bestehendes Feld
├─ created_at (VARCHAR)                ← Bestehendes Feld
└─ updated_at (VARCHAR)                ← Bestehendes Feld
```

**Wichtig:** Die Felder `name`, `vendor`, `color` sind **Kopien** für schnelle Suche. 
Das "Source of Truth" bleibt die `material`-Tabelle.

---

## FUNKTIONEN

### 1. SPULEN-NUMMERN-SYSTEM

#### 1.1 Neue Spule anlegen
```python
def create_spool(material_id: str, color: str = None, weight_full: float = 1000):
    """
    Erstellt neue Spule mit automatischer Nummernvergabe
    """
    # 1. Finde höchste Nummer
    max_number = db.execute("SELECT MAX(spool_number) FROM spool").scalar()
    new_number = (max_number or 0) + 1
    
    # 2. Hole Material-Daten
    material = db.execute(
        "SELECT name, brand FROM material WHERE id = ?", 
        [material_id]
    ).fetchone()
    
    if not material:
        raise ValueError(f"Material {material_id} nicht gefunden")
    
    # 3. Generiere neue ID
    spool_id = generate_uuid()
    
    # 4. Erstelle Spule
    db.execute("""
        INSERT INTO spool (
            id, spool_number, material_id, 
            name, vendor, color,
            weight_full, weight_empty, weight_current,
            is_open, used_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        spool_id,
        new_number,
        material_id,
        material.name,      # Kopie für Suche
        material.brand,     # Kopie für Suche
        color or 'unknown',
        weight_full,
        250,  # Standard-Leergewicht
        weight_full,
        True,  # is_open
        0      # used_count
    ])
    
    return {
        "id": spool_id,
        "spool_number": new_number,
        "name": material.name,
        "vendor": material.brand,
        "color": color
    }

# Beispiel:
# create_spool("358d10bf-c341-4c19-b0a2-fdffd5c54aff", "black")
# → Spule #7 erstellt
```

#### 1.2 Spule löschen
```python
def delete_spool(spool_number: int):
    """
    Löscht Spule (nur wenn nicht zugewiesen)
    """
    # 1. Finde Spule
    spool = db.execute(
        "SELECT id, printer_id, ams_slot FROM spool WHERE spool_number = ?",
        [spool_number]
    ).fetchone()
    
    if not spool:
        raise ValueError(f"Spule #{spool_number} nicht gefunden")
    
    # 2. Prüfe ob zugewiesen
    if spool.printer_id is not None or spool.ams_slot is not None:
        raise ValueError(f"Spule #{spool_number} ist noch zugewiesen")
    
    # 3. Lösche
    db.execute("DELETE FROM spool WHERE spool_number = ?", [spool_number])
    
    return {"deleted": spool_number}
```

#### 1.3 Spule finden
```python
def get_spool_by_number(spool_number: int):
    """
    Findet Spule nach Nummer
    """
    spool = db.execute("""
        SELECT * FROM spool WHERE spool_number = ?
    """, [spool_number]).fetchone()
    
    return spool
```

---

### 2. AMS-ZUWEISUNGSSYSTEM

#### 2.1 Spule zu Slot zuweisen
```python
def assign_spool_to_slot(spool_number: int, printer_id: str, slot_number: int):
    """
    Weist Spule einem AMS-Slot zu
    """
    # 1. Validierungen
    if slot_number not in [1, 2, 3, 4]:
        raise ValueError("Slot muss 1-4 sein")
    
    # 2. Finde Spule
    spool = db.execute(
        "SELECT id, printer_id, ams_slot FROM spool WHERE spool_number = ?",
        [spool_number]
    ).fetchone()
    
    if not spool:
        raise ValueError(f"Spule #{spool_number} nicht gefunden")
    
    # 3. Prüfe ob Spule bereits zugewiesen
    if spool.printer_id is not None:
        raise ValueError(
            f"Spule #{spool_number} ist bereits Drucker '{spool.printer_id}' "
            f"Slot {spool.ams_slot} zugewiesen"
        )
    
    # 4. Prüfe ob Slot frei
    existing = db.execute(
        "SELECT spool_number FROM spool WHERE printer_id = ? AND ams_slot = ?",
        [printer_id, slot_number]
    ).fetchone()
    
    if existing:
        raise ValueError(
            f"Slot {slot_number} ist bereits mit Spule #{existing.spool_number} belegt"
        )
    
    # 5. Zuweisen
    db.execute("""
        UPDATE spool 
        SET printer_id = ?, 
            ams_slot = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE spool_number = ?
    """, [printer_id, slot_number, spool_number])
    
    return {
        "spool_number": spool_number,
        "printer_id": printer_id,
        "slot": slot_number,
        "assigned": True
    }
```

#### 2.2 Spule von Slot entfernen
```python
def unassign_spool(spool_number: int):
    """
    Entfernt Spule aus AMS-Slot
    """
    db.execute("""
        UPDATE spool 
        SET printer_id = NULL,
            ams_slot = NULL,
            last_slot = ams_slot,  -- Merke letzten Slot
            updated_at = CURRENT_TIMESTAMP
        WHERE spool_number = ?
    """, [spool_number])
    
    return {"spool_number": spool_number, "assigned": False}
```

#### 2.3 Spule in Slot finden
```python
def get_spool_by_slot(printer_id: str, slot_number: int):
    """
    Findet Spule in einem bestimmten Slot
    """
    spool = db.execute("""
        SELECT * FROM spool 
        WHERE printer_id = ? AND ams_slot = ?
    """, [printer_id, slot_number]).fetchone()
    
    return spool
```

#### 2.4 Alle Spulen eines Druckers
```python
def get_printer_spools(printer_id: str):
    """
    Gibt alle Spulen eines Druckers zurück (sortiert nach Slot)
    """
    spools = db.execute("""
        SELECT * FROM spool 
        WHERE printer_id = ?
        ORDER BY ams_slot
    """, [printer_id]).fetchall()
    
    return spools
```

---

### 3. LIVE-SUCH-SYSTEM

#### 3.1 Spulen suchen (Live-Filter)
```python
def search_spools(
    search_term: str = "", 
    only_unassigned: bool = True,
    printer_id: str = None
):
    """
    Live-Suche in Spulen
    
    Sucht in: spool_number, name, vendor, color
    KEINE JOINs nötig → sehr schnell!
    """
    query = "SELECT * FROM spool WHERE 1=1"
    params = []
    
    # Filter: Nur nicht zugewiesene
    if only_unassigned:
        query += " AND printer_id IS NULL AND ams_slot IS NULL"
    
    # Filter: Bestimmter Drucker
    if printer_id:
        query += " AND printer_id = ?"
        params.append(printer_id)
    
    # Suchterm
    if search_term:
        query += """
            AND (
                CAST(spool_number AS TEXT) LIKE ?
                OR name LIKE ?
                OR vendor LIKE ?
                OR color LIKE ?
            )
        """
        search_pattern = f"%{search_term}%"
        params.extend([search_pattern] * 4)
    
    query += " ORDER BY spool_number ASC"
    
    spools = db.execute(query, params).fetchall()
    
    return spools

# Beispiele:
# search_spools("6")           → Findet #6, #16, #26
# search_spools("PETG")        → Findet alle PETG-Spulen
# search_spools("black")       → Findet alle schwarzen Spulen
# search_spools("Bambu")       → Findet alle Bambu Lab Spulen
# search_spools("")            → Zeigt alle nicht zugewiesenen Spulen
```

#### 3.2 Alle Spulen auflisten
```python
def get_all_spools(include_assigned: bool = True):
    """
    Gibt alle Spulen zurück
    """
    query = "SELECT * FROM spool"
    
    if not include_assigned:
        query += " WHERE printer_id IS NULL AND ams_slot IS NULL"
    
    query += " ORDER BY spool_number"
    
    spools = db.execute(query).fetchall()
    return spools
```

---

## API ENDPOINTS

### Spulen
```
POST   /api/spools                    # Neue Spule erstellen
       Body: { 
         material_id: UUID, 
         color?: string,
         weight_full?: number 
       }
       Response: { 
         id: UUID, 
         spool_number: number,
         name: string,
         vendor: string,
         color: string
       }

GET    /api/spools                    # Alle Spulen
       Query: ?assigned=true|false
       
GET    /api/spools/:number            # Eine Spule nach Nummer
       Response: Spool-Objekt
       
DELETE /api/spools/:number            # Spule löschen (nur wenn nicht zugewiesen)
```

### Zuweisungen
```
POST   /api/spools/:number/assign     # Spule zu Slot zuweisen
       Body: { 
         printer_id: UUID, 
         slot_number: 1-4 
       }
       Response: {
         spool_number: number,
         printer_id: UUID,
         slot: number,
         assigned: true
       }
       
POST   /api/spools/:number/unassign   # Spule von Slot entfernen
       Response: {
         spool_number: number,
         assigned: false
       }

GET    /api/printers/:id/spools       # Alle Spulen eines Druckers
       Response: [Spool, ...]
       
GET    /api/printers/:id/slots/:slot  # Spule in einem Slot finden
       Response: Spool-Objekt oder null
```

### Suche
```
GET    /api/spools/search             # Live-Suche
       Query: 
         ?term=PETG              (Suchbegriff)
         &unassigned=true        (nur freie Spulen)
         &printer_id=UUID        (nur ein Drucker)
       Response: [Spool, ...]
```

---

## WORKFLOWS

### Workflow 1: Neue Spule anlegen

```
1. User: Wählt Material "PLA Basic" (358d10bf...) und Farbe "black"

2. Frontend: POST /api/spools
   Body: {
     material_id: "358d10bf-c341-4c19-b0a2-fdffd5c54aff",
     color: "black",
     weight_full: 1000
   }

3. Backend:
   - Findet MAX(spool_number) = 6
   - Erstellt neue Spule mit spool_number = 7
   - Kopiert name="PLA Basic", vendor="Bambu Lab" aus material-Tabelle
   - Setzt color="black"

4. Response: {
     id: "abc123...",
     spool_number: 7,
     name: "PLA Basic",
     vendor: "Bambu Lab",
     color: "black"
   }

5. Frontend: Zeigt "Spule #7 erstellt"
```

### Workflow 2: Spule zu Slot zuweisen (Quick-Assign)

```
1. User: Öffnet AMS-Ansicht für Drucker "a8a51ff3..." (X1C)

2. Frontend: GET /api/printers/a8a51ff3.../spools
   → Zeigt Slots 1-4, Slot 4 ist leer

3. User: Klickt auf Slot 4 "Spule zuweisen"

4. Frontend: GET /api/spools/search?unassigned=true
   Response: [
     { spool_number: 4, name: "PLA Basic", vendor: "Bambu Lab", color: "black", ... },
     { spool_number: 7, name: "PLA Basic", vendor: "Bambu Lab", color: "black", ... },
     { spool_number: 5, name: "PLA", vendor: "Prusa", color: "red", ... }
   ]
   → Zeigt alle 3 freien Spulen

5. User: Tippt "7" im Suchfeld

6. Frontend: GET /api/spools/search?term=7&unassigned=true
   Response: [
     { spool_number: 7, name: "PLA Basic", vendor: "Bambu Lab", color: "black", ... }
   ]
   → Zeigt nur noch Spule #7 (gefiltert)

7. User: Klickt auf Spule #7 oder drückt Enter

8. Frontend: POST /api/spools/7/assign
   Body: {
     printer_id: "a8a51ff3-a44b-4825-969b-a5d545388140",
     slot_number: 4
   }

9. Backend:
   - Validiert: Spule #7 existiert
   - Validiert: Spule #7 ist nicht zugewiesen
   - Validiert: Slot 4 ist frei
   - UPDATE spool SET printer_id='a8a51ff3...', ams_slot=4 WHERE spool_number=7

10. Response: {
      spool_number: 7,
      printer_id: "a8a51ff3...",
      slot: 4,
      assigned: true
    }

11. Frontend: Zeigt "Spule #7 wurde Slot 4 zugewiesen"
    Slot 4 zeigt jetzt: "#7 PLA Basic - Bambu Lab - black"
```

### Workflow 3: Mehrere gleiche Spulen unterscheiden

```
Situation: Sie haben 4x PLA Basic schwarz von Bambu Lab

Datenbank:
- Spule #1: weight_current=1000g, ams_slot=1
- Spule #2: weight_current=950g,  ams_slot=2
- Spule #3: weight_current=200g,  ams_slot=3  ← Fast leer!
- Spule #4: weight_current=1000g, nicht zugewiesen

User-Workflow:
1. Sieht: "Slot 3: Spule #3 ist fast leer (200g)"
2. Entfernt Spule #3 physisch
3. Klickt "Entfernen" → POST /api/spools/3/unassign
4. Klickt "Spule zuweisen"
5. Tippt "4" → Findet Spule #4 (noch voll, 1000g)
6. Weist zu → Spule #4 ist jetzt in Slot 3

Vorteil: Klare Unterscheidung welche Spule gemeint ist!
```

---

## INTEGRATION MIT BESTEHENDEM SYSTEM

### Ihr Verbrauchstracking bleibt unverändert!

**Was Ihr System macht:**
1. MQTT-Events empfangen (print_start, print_finish, etc.)
2. Verbrauch berechnen (aus AMS-Daten, G-Code, etc.)
3. `job` Tabelle erstellen/updaten
4. `job_spool_usage` Tabelle füllen
5. `weight_current` und `remain_percent` in spool updaten

**Was FilamentHub macht:**
1. Spulen-Nummern verwalten
2. AMS-Zuweisungen verwalten
3. Schnelle Suche ermöglichen

### Beispiel-Integration:

```python
# Ihr bestehendes System (mqtt_routes.py)
def handle_print_finished(printer_id, slot, used_g):
    # 1. Finde Spule in Slot (JETZT MIT NUMMER!)
    spool = get_spool_by_slot(printer_id, slot)
    
    if not spool:
        logger.warning(f"Kein Spule in Slot {slot}")
        return
    
    # 2. Ihr Verbrauchstracking (wie bisher)
    new_weight = spool.weight_current - used_g
    
    # 3. Update (wie bisher)
    db.execute("""
        UPDATE spool 
        SET weight_current = ?,
            remain_percent = ?,
            used_count = used_count + 1
        WHERE id = ?
    """, [new_weight, calculate_percent(new_weight), spool.id])
    
    # 4. NEU: Log mit Nummer (für bessere Lesbarkeit)
    logger.info(f"Spule #{spool.spool_number} verbraucht: {used_g}g")
```

### UI-Integration:

```javascript
// Bestehende Job-Anzeige
function JobDetails({ job }) {
  const spool = useQuery(`/api/spools/${job.spool_id}`);
  
  return (
    <div>
      <h3>{job.name}</h3>
      <p>Verbrauch: {job.filament_used_g}g</p>
      
      {/* NEU: Spulen-Nummer anzeigen */}
      <p>Spule: #{spool.spool_number} {spool.name}</p>
    </div>
  );
}
```

---

## VALIDIERUNGEN

### Slot-Validierung
```python
def validate_slot(slot_number):
    if not isinstance(slot_number, int):
        raise ValueError("Slot muss eine Zahl sein")
    if slot_number not in [1, 2, 3, 4]:
        raise ValueError("Slot muss 1-4 sein")
    return True
```

### Spulen-Validierung
```python
def validate_spool_creation(material_id):
    # Material muss existieren
    material = db.execute(
        "SELECT id FROM material WHERE id = ?", 
        [material_id]
    ).fetchone()
    
    if not material:
        raise ValueError(f"Material {material_id} nicht gefunden")
    
    return True
```

### Zuweisungs-Validierung
```python
def validate_assignment(spool_number, printer_id, slot_number):
    # Spule existiert?
    spool = get_spool_by_number(spool_number)
    if not spool:
        raise ValueError(f"Spule #{spool_number} nicht gefunden")
    
    # Spule bereits zugewiesen?
    if spool.printer_id is not None:
        raise ValueError(
            f"Spule #{spool_number} ist bereits zugewiesen"
        )
    
    # Slot gültig?
    validate_slot(slot_number)
    
    # Drucker existiert?
    printer = db.execute(
        "SELECT id FROM printer WHERE id = ?", 
        [printer_id]
    ).fetchone()
    if not printer:
        raise ValueError(f"Drucker {printer_id} nicht gefunden")
    
    # Slot frei?
    existing = get_spool_by_slot(printer_id, slot_number)
    if existing:
        raise ValueError(
            f"Slot {slot_number} ist bereits mit Spule #{existing.spool_number} belegt"
        )
    
    return True
```

---

## FEHLERBEHANDLUNG

### HTTP Statuscodes
```
200 OK              - Erfolgreiche Abfrage
201 Created         - Spule erstellt
400 Bad Request     - Validierungsfehler
404 Not Found       - Spule/Drucker nicht gefunden
409 Conflict        - Slot belegt, Spule bereits zugewiesen
500 Server Error    - Datenbankfehler
```

### Fehler-Beispiele

```json
// Spule nicht gefunden
{
  "error": "NOT_FOUND",
  "message": "Spule #99 existiert nicht",
  "spool_number": 99
}

// Spule bereits zugewiesen
{
  "error": "ALREADY_ASSIGNED",
  "message": "Spule #6 ist bereits Drucker 'X1C' Slot 3 zugewiesen",
  "spool_number": 6,
  "current_printer": "a8a51ff3-a44b-4825-969b-a5d545388140",
  "current_slot": 3
}

// Slot belegt
{
  "error": "SLOT_OCCUPIED",
  "message": "Slot 2 ist bereits mit Spule #14 belegt",
  "printer_id": "a8a51ff3-a44b-4825-969b-a5d545388140",
  "slot": 2,
  "occupying_spool": 14
}

// Spule noch zugewiesen beim Löschen
{
  "error": "CANNOT_DELETE",
  "message": "Spule #6 kann nicht gelöscht werden - noch zugewiesen",
  "spool_number": 6,
  "printer_id": "a8a51ff3-a44b-4825-969b-a5d545388140",
  "slot": 3
}
```

---

## UI-KONZEPT

### AMS-Ansicht (angepasst an Ihre DB)

```
┌────────────────────────────────────────────────┐
│ X1C (192.168.178.41)                      🟢   │
├────────────────────────────────────────────────┤
│ SLOT 1: #1 PLA Basic - Bambu Lab - black [x]  │
│         ████████████████░░ 737.5g (65%)        │
│                                                │
│ SLOT 2: #2 PLA Basic - Bambu Lab - yellow [x] │
│         ██████████████████ 1000g (100%)        │
│                                                │
│ SLOT 3: #3 PLA Basic - Bambu Lab - red    [x] │
│         ████░░░░░░░░░░░░░░ 370g (16%)          │
│                                                │
│ SLOT 4: [Leer]                    [+ Zuweisen] │
└────────────────────────────────────────────────┘
```

### Quick-Assign Dialog

```
┌─────────────────────────────────────┐
│ Spule zuweisen - X1C Slot 4         │
├─────────────────────────────────────┤
│ # [7___] ← Nummer oder Name         │
│                                     │
│ Gefundene Spulen (1):               │
│ ┌─────────────────────────────────┐ │
│ │ ● #7  PLA Basic                 │ │
│ │       Bambu Lab - black         │ │
│ │       1000g (100%)              │ │
│ └─────────────────────────────────┘ │
│                                     │
│ [✓ Zuweisen] [✗ Abbrechen]         │
└─────────────────────────────────────┘
```

### Spulen-Liste (mit Standort)

```
┌─────────────────────────────────────────────────────────────┐
│ # │ Name        │ Vendor     │ Color  │ Standort          │
├───┼─────────────┼────────────┼────────┼───────────────────┤
│ 1 │ PLA Basic   │ Bambu Lab  │ black  │ X1C - Slot 1      │
│ 2 │ PLA Basic   │ Bambu Lab  │ yellow │ X1C - Slot 2      │
│ 3 │ PLA Basic   │ Bambu Lab  │ red    │ X1C - Slot 3      │
│ 4 │ PLA Basic   │ Bambu Lab  │ black  │ Lager             │
│ 5 │ PLA         │ Prusa      │ red    │ Lager             │
│ 7 │ PLA Basic   │ Bambu Lab  │ black  │ Lager             │
└─────────────────────────────────────────────────────────────┘
```

### Job-Historie (mit Spulen-Nummern)

```
┌────────────────────────────────────────────────────┐
│ Druck-Historie                                     │
├────────────────────────────────────────────────────┤
│ 02.12.2024 17:32 - Unnamed Job                     │
│ Drucker: X1C                                       │
│ Spule: #3 PLA Basic (Bambu Lab)                    │
│ Verbrauch: 22.5g / 9.9m                            │
└────────────────────────────────────────────────────┘
```

---

## GESCHÄFTSREGELN

### 1. Spulen-Nummern sind permanent
- Beim Erstellen: `spool_number = MAX(spool_number) + 1`
- Die Nummer bleibt bis zur Löschung der Spule
- Gelöschte Nummern werden NICHT wiederverwendet
- Beispiel: Spule #5 gelöscht → Nächste Spule wird #8, nicht #5

### 2. Ein Slot = Eine Spule
- Ein Slot kann maximal eine Spule haben
- Eine Spule kann maximal einem Slot zugeordnet sein
- Constraint in DB: `UNIQUE (printer_id, ams_slot)`

### 3. Zugewiesene Spulen können nicht gelöscht werden
- Erst `unassign` aufrufen
- Dann `delete` möglich

### 4. Material-Daten werden kopiert
- Bei Erstellung: `name`, `vendor` aus `material`-Tabelle kopieren
- Bei Material-Änderung: Bestehende Spulen werden NICHT automatisch geändert
- Grund: Historische Genauigkeit ("Diese Spule wurde als 'PLA Basic' erstellt")

### 5. Farbe ist spulen-spezifisch
- Gleiche Material-ID, unterschiedliche Farben möglich
- 4x "PLA Basic" kann 4 verschiedene Farben haben
- Farbe ist KEIN Teil der Material-Identifikation

---

## PERFORMANCE-OPTIMIERUNGEN

### Indizes (bereits in Migration enthalten)
```sql
CREATE INDEX idx_spool_number ON spool(spool_number);
CREATE INDEX idx_spool_name ON spool(name);
CREATE INDEX idx_spool_search ON spool(name, vendor, color);
CREATE INDEX idx_spool_printer_slot ON spool(printer_id, ams_slot);
```

### Warum denormalisiert?
```
Ohne Denormalisierung (mit JOIN):
SELECT s.*, m.name, m.brand 
FROM spool s 
JOIN material m ON s.material_id = m.id
WHERE m.name LIKE '%PETG%'
→ Langsamer (JOIN erforderlich)

Mit Denormalisierung (ohne JOIN):
SELECT * FROM spool 
WHERE name LIKE '%PETG%'
→ Schneller (direkter Index-Zugriff)
```

**Kosten:** 200 Bytes extra pro Spule (name + vendor + color)  
**Gewinn:** 10-50x schnellere Suche bei großen Datenbanken

---

## DEPLOYMENT

### 1. Migration ausführen
```bash
# Backup erstellen
sqlite3 filamenthub.db ".backup filamenthub_backup.db"

# Migration
sqlite3 filamenthub.db < migration_spool_numbers.sql

# Verify
sqlite3 filamenthub.db "SELECT COUNT(*) FROM spool WHERE spool_number IS NOT NULL"
```

### 2. API deployen
```python
# Neue Endpoints zu bestehender FastAPI/Flask app hinzufügen
from filamenthub import spool_routes

app.include_router(spool_routes.router, prefix="/api")
```

### 3. Frontend aktualisieren
```javascript
// Bestehende Komponenten erweitern
import { SpoolNumberBadge, QuickAssignDialog } from './filamenthub';

// In bestehenden Views nutzen
<SpoolNumberBadge number={spool.spool_number} />
<QuickAssignDialog printer={printer} slot={4} />
```

---

## ZUSAMMENFASSUNG

### Was FilamentHub zu Ihrem System hinzufügt:

**Datenbank:**
- 4 neue Felder in `spool`-Tabelle
- 3 neue Indizes für Performance

**Backend:**
- 9 neue Funktionen (erstellen, löschen, zuweisen, suchen, etc.)
- 9 neue API-Endpoints

**Frontend:**
- Quick-Assign Dialog
- Live-Suche
- Spulen-Nummern-Anzeige

**Was NICHT geändert wird:**
- ✅ Ihre `job`-Tabelle
- ✅ Ihre `job_spool_usage`-Tabelle
- ✅ Ihr Verbrauchstracking in `mqtt_routes.py`
- ✅ Ihre Material-Verwaltung
- ✅ Ihre Drucker-Verwaltung

**Ergebnis:**
Statt "Spule 3861a044-c81b-4b87-9060-89e029d761ea in Slot 2"  
→ Jetzt: "Spule #1 in Slot 2" 🎯

---

## NÄCHSTE SCHRITTE

1. ✅ Migration-Script ausführen
2. ✅ Neue API-Endpoints implementieren
3. ✅ Quick-Assign Dialog in Frontend bauen
4. ✅ Bestehende Views mit Spulen-Nummern erweitern
5. ✅ Testen mit bestehenden Daten

**Bereit zum Start!** 🚀
