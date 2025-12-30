import sqlite3
from pathlib import Path
p = Path('data/filamenthub.db')
conn = sqlite3.connect(p)
cur = conn.cursor()
try:
    cur.execute('SELECT version_num FROM alembic_version')
    v = cur.fetchone()
    print('alembic_version in DB:', v[0] if v else None)
except Exception as e:
    print('error reading alembic_version:', e)
conn.close()
