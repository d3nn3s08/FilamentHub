import re, json, time, pathlib
root=pathlib.Path('.').resolve()
idx=root/'htmlcov'/'index.html'
if idx.exists():
    s=idx.read_text(encoding='utf-8')
    m=re.search(r'Coverage report:\s*<span[^>]*>(\d+)%</span>', s)
    if not m:
        m=re.search(r'Coverage report:\s*(\d+)%', s)
    if m:
        overall=int(m.group(1))
        p=root/'data'
        p.mkdir(exist_ok=True)
        f=p/'coverage_history.json'
        arr=[]
        if f.exists():
            try:
                arr=json.loads(f.read_text(encoding='utf-8'))
            except:
                arr=[]
        arr.append({"ts":int(time.time()),"percent":overall})
        arr=arr[-200:]
        f.write_text(json.dumps(arr),encoding='utf-8')
        print('wrote',overall)
    else:
        print('no percent')
else:
    print('no index')
