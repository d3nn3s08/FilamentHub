import os
import bcrypt
import sys
# This script expects a local .env file.
# Do NOT commit real secrets.

"""
Developer utility script.

Checks whether a plaintext password matches an
ADMIN_PASSWORD_HASH from a local .env file.

Not used by FilamentHub runtime, Docker or CI.
"""


def read_env(path='.env'):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('ADMIN_PASSWORD_HASH='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None


h = read_env()
if not h:
    print('NO_HASH')
    sys.exit(2)

print('HASH_REPR:', repr(h))

pw = 'FillamentHub'.encode('utf-8')
try:
    ok = bcrypt.checkpw(pw, h.encode('utf-8'))
    print('CHECK:', ok)
    sys.exit(0 if ok else 1)
except Exception as e:
    print('ERR:', e)
    sys.exit(3)
