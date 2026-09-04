
import sqlite3, json, time, os
DB = os.path.join(os.path.dirname(__file__), "..", "lmcomply.db")

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    c = conn(); c.executescript("""
    CREATE TABLE IF NOT EXISTS products(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT, brand TEXT, category TEXT, created_at REAL);
    CREATE TABLE IF NOT EXISTS scans(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      product_id INTEGER, image_path TEXT, ocr_text TEXT,
      extracted TEXT, status TEXT, created_at REAL);
    CREATE TABLE IF NOT EXISTS violations(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      scan_id INTEGER, rule_id TEXT, severity TEXT, message TEXT);
    """)
    c.commit(); c.close()

def q(sql, args=(), one=False):
    c = conn(); r = c.execute(sql, args)
    rows = r.fetchall(); c.close()
    return (rows[0] if rows else None) if one else rows

def run(sql, args=()):
    c = conn(); cur = c.execute(sql, args); c.commit()
    last = cur.lastrowid; c.close(); return last
