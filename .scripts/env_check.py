import os

e = os.environ.get('ADMIN_PASSWORD_HASH')
if not e:
    print('ADMIN_PASSWORD_HASH: UNSET')
else:
    if e.startswith('$2y$'):
        p = '$2y$'
    elif e.startswith('$2b$'):
        p = '$2b$'
    else:
        p = e[:10]
    print('ADMIN_PASSWORD_HASH: SET, prefix=' + p + ', len=' + str(len(e)))

print('FILAMENTHUB_DB_PATH:', os.environ.get('FILAMENTHUB_DB_PATH'))
print('ADMIN_COOKIE_SECURE:', os.environ.get('ADMIN_COOKIE_SECURE'))
