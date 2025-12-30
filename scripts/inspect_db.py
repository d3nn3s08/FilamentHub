import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / 'data' / 'filamenthub.db'
print('DB path:', DB_PATH)
conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()

# list tables
cur.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name;")
objects = cur.fetchall()
print('\nTables and views:')
print(json.dumps(objects, indent=2))

# print schema for key tables
key_tables = ['spool', 'ams_conflict']
for t in key_tables:
    print(f"\nSchema for {t}:")
    try:
        cur.execute(f"PRAGMA table_info('{t}')")
        cols = cur.fetchall()
        for c in cols:
            # cid,name,type,notnull,dflt_value,pk
            print(' -', c)
    except Exception as e:
        print('  (error)', e)

# print all tables with columns count
print('\nAll tables with columns count:')
for name, _type in objects:
    try:
        cur.execute(f"PRAGMA table_info('{name}')")
        cols = cur.fetchall()
        print(f"{name}: {len(cols)} cols")
    except Exception as e:
        print(name, 'error', e)

conn.close()
