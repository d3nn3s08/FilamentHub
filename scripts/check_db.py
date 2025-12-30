import sqlite3
import subprocess
from pathlib import Path
p = Path('data/filamenthub.db')
print('DB path:', p.resolve())
conn = sqlite3.connect(p)
cur = conn.cursor()
try:
    cur.execute('SELECT version_num FROM alembic_version')
    rows = cur.fetchall()
    print('alembic_version rows:', rows)
except Exception as e:
    print('alembic_version error:', e)

try:
    cur.execute("PRAGMA table_info('spool')")
    cols = cur.fetchall()
    print('spool columns:', [c[1] for c in cols])
except Exception as e:
    print('spool pragma error:', e)
try:
    cur.execute("PRAGMA table_info('printer')")
    cols = cur.fetchall()
    print('printer columns:', [c[1] for c in cols])
except Exception as e:
    print('printer pragma error:', e)

try:
    cur.execute("PRAGMA table_info('material')")
    cols = cur.fetchall()
    print('material columns:', [c[1] for c in cols])
except Exception as e:
    print('material pragma error:', e)

conn.close()

print('\n--- alembic heads ---')
try:
    out = subprocess.check_output([".venv\\Scripts\\python.exe","-m","alembic","heads"], stderr=subprocess.STDOUT, text=True)
    print(out)
except subprocess.CalledProcessError as e:
    print('alembic heads error:')
    print(e.output)

print('\n--- alembic current ---')
try:
    out = subprocess.check_output([".venv\\Scripts\\python.exe","-m","alembic","current"], stderr=subprocess.STDOUT, text=True)
    print(out)
except subprocess.CalledProcessError as e:
    print('alembic current error:')
    print(e.output)

print('\n--- alembic history (verbose) ---')
try:
    out = subprocess.check_output([".venv\\Scripts\\python.exe","-m","alembic","history","--verbose"], stderr=subprocess.STDOUT, text=True)
    print(out)
except subprocess.CalledProcessError as e:
    print('alembic history error:')
    print(e.output)
