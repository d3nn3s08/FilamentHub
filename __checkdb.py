import sqlite3, json
conn = sqlite3.connect('data/filamenthub.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print('Tables:', tables)
wanted = ['job_spool_usage','job','spool','material','printer']
missing = [t for t in wanted if t not in tables]
print('Missing:', missing)
if 'job_spool_usage' in tables:
    cur.execute('PRAGMA table_info(job_spool_usage)')
    print('job_spool_usage cols:', cur.fetchall())
cur.close(); conn.close()
