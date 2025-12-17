import sqlite3, json
con = sqlite3.connect('data/filamenthub.db')
cur = con.cursor()
cur.execute("SELECT id, name FROM printer WHERE printer_type='bambu' LIMIT 1")
r = cur.fetchone()
if r:
    print(json.dumps({'id': r[0], 'name': r[1]}))
else:
    print('null')
cur.close()
con.close()
