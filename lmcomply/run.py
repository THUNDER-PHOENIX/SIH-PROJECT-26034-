"""One-command local launcher for the SIH demo."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)


def run(command):
    subprocess.run(command, check=True)


# Initialize database and seed demo data if needed.
try:
    from backend import db

    db.init()
    count = db.q("SELECT COUNT(*) c FROM scans", one=True)["c"]
    if count == 0:
        run([sys.executable, "-m", "backend.seed"])
except Exception as exc:
    print("Demo seed skipped:", exc)


# Generate sample labels if possible.
try:
    run([sys.executable, "-m", "backend.make_labels"])
except Exception as exc:
    print("Label generation skipped:", exc)


# Start FastAPI.
run([
    sys.executable,
    "-m",
    "uvicorn",
    "backend.main:app",
    "--host",
    "127.0.0.1",
    "--port",
    "8000",
])
