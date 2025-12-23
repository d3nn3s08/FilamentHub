from pathlib import Path
path = Path('tests/conftest.py')
for i,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
    if i <= 220:
        print(f"{i:04d}: {line}")
