from sqlmodel import SQLModel
from app.models.material import Material
from app.models.spool import Spool
from app.models.printer import Printer
from app.models.job import Job
from app.database import engine

if __name__ == "__main__":
    print("Initialisiere Tabellen...")
    SQLModel.metadata.create_all(engine)
    print("Tabellen wurden erstellt.")
    # Tabellenstruktur prüfen
    import sqlite3
    conn = sqlite3.connect('data/filamenthub.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tabellen in der DB:", tables)
    cursor.execute("PRAGMA foreign_key_list('spool');")
    fk = cursor.fetchall()
    print("Foreign Keys in spool:", fk)
    conn.close()
