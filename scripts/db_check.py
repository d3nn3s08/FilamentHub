from app.database import DB_PATH
import sqlite3, os, sys

print('DB_PATH:', DB_PATH)
print('exists:', os.path.exists(DB_PATH))

try:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name, cloud_serial, api_key FROM printer LIMIT 50")
    rows = cur.fetchall()
    print('ROWS COUNT:', len(rows))
    for r in rows:
        print(r)
    conn.close()
except Exception as e:
    print('DB_ERROR:', e)
    sys.exit(1)
