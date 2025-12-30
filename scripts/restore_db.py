from pathlib import Path
import shutil
src = Path('backups/pre_change_20251229_231028/filamenthub_test.db')
dst = Path('data/filamenthub.db')
backup = Path('data/filamenthub.db.corrupt.bak')
if dst.exists():
    shutil.copy(dst, backup)
    print('backed up current data/filamenthub.db ->', backup)
else:
    print('no existing data/filamenthub.db to backup')
if src.exists():
    shutil.copy(src, dst)
    print('restored', src, '->', dst)
else:
    print('source backup not found:', src)
