from pathlib import Path
path = Path('app/routes/admin_coverage_routes.py')
for i,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
    if 1 <= i <= 200:
        print(f"{i:04d}: {line}")
