import os
import sqlite3
from contextlib import contextmanager

DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lmcomply.db"))


def conn():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


@contextmanager
def connection():
    c = conn()
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init():
    with connection() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS products(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              brand TEXT,
              category TEXT,
              created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scans(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              product_id INTEGER NOT NULL,
              image_path TEXT,
              ocr_text TEXT,
              extracted TEXT,
              status TEXT NOT NULL,
              created_at REAL NOT NULL,
              FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS violations(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              scan_id INTEGER NOT NULL,
              rule_id TEXT NOT NULL,
              severity TEXT NOT NULL,
              message TEXT NOT NULL,
              FOREIGN KEY(scan_id) REFERENCES scans(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_scans_status ON scans(status);
            CREATE INDEX IF NOT EXISTS idx_violations_scan ON violations(scan_id);
            CREATE INDEX IF NOT EXISTS idx_violations_rule ON violations(rule_id);
            """
        )


def q(sql, args=(), one=False):
    with connection() as c:
        rows = c.execute(sql, args).fetchall()
    return (rows[0] if rows else None) if one else rows


def run(sql, args=()):
    with connection() as c:
        cur = c.execute(sql, args)
        return cur.lastrowid
