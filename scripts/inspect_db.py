import sqlite3, sys
p='.test_filamenthub.db'
try:
    conn=sqlite3.connect(p)
    cur=conn.cursor()
    cur.execute('SELECT name, brand, id FROM material')
    rows=cur.fetchall()
    print('ROWS:', rows)
    conn.close()
except Exception as e:
    print('ERR', e)
    sys.exit(1)
