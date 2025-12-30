#!/usr/bin/env python3
import sqlite3
from pathlib import Path
from datetime import datetime
import sys

p = Path('data/filamenthub.db')
if not p.exists():
    print('DB not found at', p)
    sys.exit(1)

conn = sqlite3.connect(p)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
if not cur.fetchone():
    print('No alembic_version table found.')
    conn.close()
    sys.exit(1)

cur.execute('SELECT version_num FROM alembic_version')
rows = [r[0] for r in cur.fetchall()]
print('Current alembic_version rows:', rows)
backup = Path('data') / f"alembic_version_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
backup.write_text('\n'.join(rows))
print('Backed up existing alembic_version rows to', backup)

# Choose target: prefer first row that looks like a short hex id (length <= 14 and contains hex), else first row
import re
hex_like = [r for r in rows if re.fullmatch(r'[0-9a-fA-F]{7,40}', r)]
if hex_like:
    target = hex_like[0]
else:
    target = rows[0] if rows else None

if not target:
    print('No target revision could be determined; aborting.')
    conn.close()
    sys.exit(1)

print('Setting alembic_version to', target)
cur.execute('DELETE FROM alembic_version')
cur.execute('INSERT INTO alembic_version(version_num) VALUES(?)', (target,))
conn.commit()
print('Done.')
conn.close()
