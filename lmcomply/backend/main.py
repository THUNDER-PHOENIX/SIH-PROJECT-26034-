
import os, json, time, uuid
from fastapi import FastAPI, UploadFile, Form, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import db, extract, rules, report

UP = os.path.join(os.path.dirname(__file__), "..", "uploads")
app = FastAPI(title="LM Comply - Packaged Commodities Compliance Checker")
db.init()

# --- tiny RBAC: send header X-Role: admin | inspector (default inspector) ---
def role(x_role: str = Header(default="inspector")):
    if x_role not in ("inspector", "admin"): raise HTTPException(403, "bad role")
    return x_role

@app.post("/api/scan")
async def scan(file: UploadFile, px_per_mm: float = Form(None),
               demo_text: str = Form(""), x_role: str = Header(default="inspector")):
    role(x_role)
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    img_path = os.path.join(UP, uuid.uuid4().hex + ext)
    with open(img_path, "wb") as f: f.write(await file.read())
    srv = extract.ocr_text(img_path)
    text = (demo_text or "").strip() or srv
    engine = "browser-ocr" if (demo_text.strip() and not srv) else ("tesseract" if srv else "none")
    fields = extract.parse_fields(text)
    ppm = px_per_mm or extract.px_per_mm_from_image(img_path)
    fields["font_mm"] = extract.mrp_font_mm(fields, extract.word_boxes(img_path), ppm)
    violations = rules.evaluate(fields, {"px_per_mm": ppm, "font_mm": fields["font_mm"]})
    status = "NON_COMPLIANT" if any(v["severity"] in ("CRITICAL","MAJOR") for v in violations) else "COMPLIANT"
    brand = (fields["raw"].split()[:3] or ["Unknown"])
    pid = db.run("INSERT INTO products(name,brand,category,created_at) VALUES(?,?,?,?)",
                 (" ".join(brand)[:40], brand[0], "general", time.time()))
    sid = db.run("INSERT INTO scans(product_id,image_path,ocr_text,extracted,status,created_at) VALUES(?,?,?,?,?,?)",
                 (pid, img_path, text, json.dumps(fields), status, time.time()))
    for v in violations:
        db.run("INSERT INTO violations(scan_id,rule_id,severity,message) VALUES(?,?,?,?)",
               (sid, v["rule_id"], v["severity"], v["message"]))
    return {"scan_id": sid, "product_id": pid, "status": status,
            "extracted": fields, "violations": violations, "engine": engine}

@app.get("/api/scans")
def scans():
    return [dict(r) for r in db.q("SELECT s.*, p.name product_name FROM scans s "
             "JOIN products p ON p.id=s.product_id ORDER BY s.id DESC LIMIT 50")]

@app.get("/api/dashboard")
def dashboard(x_role: str = Header(default="inspector")):
    role(x_role)
    total = db.q("SELECT COUNT(*) c FROM scans", one=True)["c"]
    nc = db.q("SELECT COUNT(*) c FROM scans WHERE status=NON_COMPLIANT".replace("NON_COMPLIANT", "'NON_COMPLIANT'"), one=True)["c"]
    by_rule = db.q("SELECT rule_id, COUNT(*) c FROM violations GROUP BY rule_id ORDER BY c DESC")
    by_sev = db.q("SELECT severity, COUNT(*) c FROM violations GROUP BY severity")
    recent = [dict(r) for r in db.q("SELECT id,status,created_at FROM scans ORDER BY id DESC LIMIT 5")]
    return {"total_scans": total, "non_compliant": nc,
            "compliance_rate": round(100*(total-nc)/total, 1) if total else 100,
            "violations_by_rule": [dict(r) for r in by_rule],
            "violations_by_severity": [dict(r) for r in by_sev], "recent": recent}

@app.get("/api/report/{scan_id}.pdf")
def pdf(scan_id: int):
    s = db.q("SELECT * FROM scans WHERE id=?", (scan_id,), one=True)
    if not s: raise HTTPException(404)
    p = db.q("SELECT * FROM products WHERE id=?", (s["product_id"],), one=True)
    vs = [dict(r) for r in db.q("SELECT * FROM violations WHERE scan_id=?", (scan_id,))]
    out = os.path.join(UP, "report_%d.pdf" % scan_id)
    report.build_pdf(s, p, vs, out)
    return FileResponse(out, media_type="application/pdf", filename="compliance_report_%d.pdf" % scan_id)

app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "frontend"), html=True), name="ui")
