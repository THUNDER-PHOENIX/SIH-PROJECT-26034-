
import json, time, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import db

SAMPLES = [
    ("Aloo Bhujia 400g (compliant)",
     {"mrp": "72", "net_qty": ("400", "g"), "date": "mfg: 03/2026", "phone": True, "email": False, "imported": False, "mfr_decl": True, "raw": "haldiram aloo bhujia mrp rs. 72 net qty 400g mfg: 03/2026 manufactured by haldiram foods"},
     []),
    ("Imported Cookies - no origin",
     {"mrp": "145", "net_qty": ("300", "g"), "date": None, "phone": False, "email": True, "imported": True, "origin": None, "importer_addr": False, "mfr_decl": False, "raw": "imported butter cookies mrp 145 net wt 300g best before 9 months"},
     [("R6(1)(f)","CRITICAL","Month & year of manufacture/packing/import missing"),
      ("R6(1)(i)","MAJOR","Imported product: Country of Origin missing"),
      ("R6(1)(a)","MAJOR","Imported product: importer name & address missing")]),
    ("Water bottle - tiny MRP font",
     {"mrp": "20", "net_qty": ("1", "l"), "date": "pkd: 01/2026", "phone": True, "email": True, "imported": False, "mfr_decl": True, "font_mm": 1.2, "raw": "packaged drinking water mrp rs. 20 net qty 1l pkd: 01/2026"},
     [("Sch-II-font","MAJOR","Declaration font ~1.2mm is below prescribed minimum 2.0mm")]),
]
db.init()
for name, fields, vs in SAMPLES:
    pid = db.run("INSERT INTO products(name,brand,category,created_at) VALUES(?,?,?,?)",
                 (name, name.split()[0], "snacks", time.time()))
    sid = db.run("INSERT INTO scans(product_id,image_path,ocr_text,extracted,status,created_at) VALUES(?,?,?,?,?,?)",
                 (pid, "", "", json.dumps(fields),
                  "NON_COMPLIANT" if vs else "COMPLIANT", time.time()))
    for rid, sev, msg in vs:
        db.run("INSERT INTO violations(scan_id,rule_id,severity,message) VALUES(?,?,?,?)", (sid, rid, sev, msg))
print("seeded", len(SAMPLES), "demo scans")
