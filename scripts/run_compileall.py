import compileall
import sys

ok = compileall.compile_dir('app', maxlevels=10, quiet=0)
if ok:
    print('compileall: ok')
    sys.exit(0)
else:
    print('compileall: errors')
    sys.exit(2)
