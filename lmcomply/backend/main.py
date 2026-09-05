import json
import os
import time
import uuid

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from . import db
from . import extract
from . import report
from . import rules

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UP = os.path.join(BASE, "uploads")
MAX_UPLOAD = 10 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}

os.makedirs(UP, exist_ok=True)
app = FastAPI(title="LM Comply", version="2.0")
db.init()


def role(x_role: str = Header(default="inspector")):
    if x_role not in {"inspector", "admin"}:
        raise HTTPException(status_code=403, detail="Invalid role")
    return x_role


async def save_upload(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if file.content_type not in ALLOWED_TYPES or ext not in ALLOWED_EXT:
        raise HTTPException(400, "Only JPG, PNG and WEBP images are accepted")

    data = await file.read()
    if not data or len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Image must be between 1 byte and 10 MB")

    path = os.path.join(UP, uuid.uuid4().hex + ext)
    try:
        with open(path, "wb") as f:
            f.write(data)
        with Image.open(path) as image:
            image.verify()
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        raise HTTPException(400, "Uploaded file is not a valid image")
    return path


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "LM Comply"}


@app.post("/api/scan")
async def scan(
    file: UploadFile = File(...),
    px_per_mm: float | None = Form(None),
    demo_text: str = Form(""),
    x_role: str = Header(default="inspector"),
):
    role(x_role)
    if px_per_mm is not None and not (0 < px_per_mm < 10000):
        raise HTTPException(400, "px_per_mm must be between 0 and 10000")

    img_path = await save_upload(file)
    ocr = extract.ocr_data(img_path)
    manual_text = (demo_text or "").strip()
    text = manual_text or ocr["text"]
    engine = "manual/demo" if manual_text else ("tesseract" if ocr["text"] else "none")

    fields = extract.parse_fields(text)
    fields["ocr_confidence"] = ocr["confidence"] if not manual_text else 1.0
    ppm = px_per_mm or extract.px_per_mm_from_image(img_path)
    fields["font_mm"] = extract.mrp_font_mm(fields, ocr["boxes"], ppm) if not manual_text else None
    violations = rules.evaluate(fields, {"px_per_mm": ppm, "font_mm": fields["font_mm"]})
    status = "NON_COMPLIANT" if any(v["severity"] in {"CRITICAL", "MAJOR"} for v in violations) else "COMPLIANT"

    words = fields["raw"].split()
    brand = words[:3] or ["Unknown"]
    pid = db.run(
        "INSERT INTO products(name,brand,category,created_at) VALUES(?,?,?,?)",
        (" ".join(brand)[:80], brand[0][:40], "general", time.time()),
    )
    sid = db.run(
        "INSERT INTO scans(product_id,image_path,ocr_text,extracted,status,created_at) VALUES(?,?,?,?,?,?)",
        (pid, img_path, text, json.dumps(fields), status, time.time()),
    )
    for v in violations:
        db.run(
            "INSERT INTO violations(scan_id,rule_id,severity,message) VALUES(?,?,?,?)",
            (sid, v["rule_id"], v["severity"], v["message"]),
        )

    return {
        "scan_id": sid,
        "product_id": pid,
        "status": status,
        "extracted": fields,
        "violations": violations,
        "engine": engine,
    }


@app.get("/api/scans")
def scans(x_role: str = Header(default="inspector")):
    role(x_role)
    rows = db.q(
        "SELECT s.*, p.name product_name FROM scans s "
        "JOIN products p ON p.id=s.product_id ORDER BY s.id DESC LIMIT 100"
    )
    return [dict(r) for r in rows]


@app.get("/api/dashboard")
def dashboard(x_role: str = Header(default="inspector")):
    role(x_role)
    total = db.q("SELECT COUNT(*) c FROM scans", one=True)["c"]
    nc = db.q("SELECT COUNT(*) c FROM scans WHERE status=?", ("NON_COMPLIANT",), one=True)["c"]
    by_rule = db.q("SELECT rule_id, COUNT(*) c FROM violations GROUP BY rule_id ORDER BY c DESC")
    by_sev = db.q("SELECT severity, COUNT(*) c FROM violations GROUP BY severity ORDER BY c DESC")
    recent = [dict(r) for r in db.q("SELECT id,status,created_at FROM scans ORDER BY id DESC LIMIT 5")]
    return {
        "total_scans": total,
        "non_compliant": nc,
        "compliance_rate": round(100 * (total - nc) / total, 1) if total else 100.0,
        "violations_by_rule": [dict(r) for r in by_rule],
        "violations_by_severity": [dict(r) for r in by_sev],
        "recent": recent,
    }


@app.get("/api/report/{scan_id}.pdf")
def pdf(scan_id: int, x_role: str = Header(default="inspector")):
    role(x_role)
    scan_row = db.q("SELECT * FROM scans WHERE id=?", (scan_id,), one=True)
    if not scan_row:
        raise HTTPException(404, "Scan not found")
    product = db.q("SELECT * FROM products WHERE id=?", (scan_row["product_id"],), one=True)
    violations = [dict(r) for r in db.q("SELECT * FROM violations WHERE scan_id=?", (scan_id,))]
    out = os.path.join(UP, f"report_{scan_id}.pdf")
    report.build_pdf(scan_row, product, violations, out)
    return FileResponse(out, media_type="application/pdf", filename=f"compliance_report_{scan_id}.pdf")


app.mount("/", StaticFiles(directory=os.path.join(BASE, "frontend"), html=True), name="ui")
