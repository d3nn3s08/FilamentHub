from sqlmodel import SQLModel, Session
from app.models.material import Material, MaterialCreateSchema
from app.models.spool import Spool, SpoolCreateSchema
from app.models.printer import Printer
from app.models.job import Job
from app.database import engine
import os

# Datenbankpfad aus Environment nutzen (sonst Default)
DB_PATH = os.environ.get("FILAMENTHUB_DB_PATH", "data/filamenthub.db")

# Datenbank neu anlegen (PermissionError ignorieren falls gelockt)
try:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
except PermissionError:
    # Wenn die Datei gelockt ist (z.B. laufender Server), Tests überspringen
    raise SystemExit(f"DB-Datei {DB_PATH} ist gelockt, Testlauf abgebrochen.")

print("Tabellen werden initialisiert...")
SQLModel.metadata.create_all(engine)
print("Tabellen wurden erstellt.")

with Session(engine) as session:
    print("Test 1: Material anlegen...")
    m = Material(**MaterialCreateSchema(name='PLA', brand='Generic', color='#FFF', density=1.24, diameter=1.75).model_dump())
    session.add(m)
    session.commit()
    session.refresh(m)
    print("Material:", m)

    print("Test 2: Spool anlegen...")
    sp = Spool(**SpoolCreateSchema(material_id=m.id, weight_full=1000, weight_empty=250, label='Testspule').model_dump())
    session.add(sp)
    session.commit()
    session.refresh(sp)
    print("Spool:", sp)

    print("Test 3: Material aktualisieren und löschen...")
    m.name = 'PLA-Update'
    session.add(m)
    session.commit()
    session.refresh(m)
    print("Material nach Update:", m)
    session.delete(m)
    session.commit()
    print("Material gelöscht.")
