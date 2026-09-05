"""One-command local launcher for the SIH demo."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

def run(command):
    subprocess.run(command, check=True)


# Seed only when the local database has no scans; normal launches are non-destructive.
try:
    sys.path.insert(0, os.path.join(ROOT, "backend"))
    import db
    db.init()
    count = db.q("SELECT COUNT(*) c FROM scans", one=True)["c"]
    if count == 0:
        run([sys.executable, "backend/seed.py"])
except Exception as exc:
    print("Demo seed skipped:", exc)

try:
    run([sys.executable, "backend/make_labels.py"])
except Exception as exc:
    print("Label generation skipped:", exc)

run([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"])
