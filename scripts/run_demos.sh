#!/bin/bash
# Corre el --demo de cada script y el smoke test; sale 1 si alguno falla.
# No depende de ninguna IA ni de Claude Code: solo de python3 y requirements.txt.
cd "$(dirname "$0")" || exit 1
PY="${PYTHON:-python3}"
fallo=0
for f in $(grep -l -- "--demo" *.py | grep -v '^smoke_test.py$'); do
  if "$PY" "$f" --demo >/dev/null 2>&1; then echo "ok    $f"; else echo "FALLA $f"; fallo=1; fi
done
if "$PY" smoke_test.py >/dev/null 2>&1; then echo "ok    smoke_test.py"; else echo "FALLA smoke_test.py"; fallo=1; fi
exit $fallo
