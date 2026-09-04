
"""One-command launcher: seed demo data + generate labels + start server."""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.run([sys.executable, "backend/seed.py"])
try:
    subprocess.run([sys.executable, "backend/make_labels.py"])
except Exception as e:
    print("label gen skipped:", e)
subprocess.run([sys.executable, "-m", "uvicorn", "backend.main:app", "--port", "8000"])
