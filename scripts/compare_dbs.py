import sqlite3
import sys
from pathlib import Path

if len(sys.argv) < 3:
    print("Usage: compare_dbs.py <db1> <db2>")
    sys.exit(2)

p1 = Path(sys.argv[1])
p2 = Path(sys.argv[2])
print('DB1:', p1.resolve())
print('DB2:', p2.resolve())

def info(p):
    out = {}
    conn = sqlite3.connect(p)
    cur = conn.cursor()
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
    except Exception as e:
        tables = []
    out['tables'] = tables
    for t in tables:
        try:
            cur.execute(f"PRAGMA table_info('{t}')")
            cols = [r[1] for r in cur.fetchall()]
        except Exception as e:
            cols = []
        out.setdefault('columns', {})[t] = cols
    try:
        cur.execute('SELECT version_num FROM alembic_version')
        out['alembic_version'] = [r[0] for r in cur.fetchall()]
    except Exception as e:
        out['alembic_version'] = None
    conn.close()
    return out

info1 = info(p1)
info2 = info(p2)

print('\n--- Summary DB1 ---')
print('tables:', len(info1['tables']))
print('alembic_version:', info1['alembic_version'])
print('\n--- Summary DB2 ---')
print('tables:', len(info2['tables']))
print('alembic_version:', info2['alembic_version'])

print('\n--- Tables only in DB1 ---')
for t in sorted(set(info1['tables']) - set(info2['tables'])):
    print(t)
print('\n--- Tables only in DB2 ---')
for t in sorted(set(info2['tables']) - set(info1['tables'])):
    print(t)

common = set(info1['tables']).intersection(info2['tables'])
print(f'\n--- Column differences for {len(common)} common tables ---')
for t in sorted(common):
    c1 = set(info1['columns'].get(t, []))
    c2 = set(info2['columns'].get(t, []))
    only1 = c1 - c2
    only2 = c2 - c1
    if only1 or only2:
        print('\nTable:', t)
        if only1:
            print('  only in DB1:', only1)
        if only2:
            print('  only in DB2:', only2)

print('\nDone')
