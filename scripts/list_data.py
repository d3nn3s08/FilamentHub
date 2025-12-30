from pathlib import Path
p=Path('data')
print('data dir exists:', p.exists())
if p.exists():
    for f in sorted(p.iterdir()):
        try:
            print(f.name, f.stat().st_size)
        except Exception as e:
            print(f.name, 'error', e)
