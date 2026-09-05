import hashlib
import hmac
import json
import os
import time
import uuid

from fastapi import Cookie, FastAPI, File, Form, Header, HTTPException, Query, Response, UploadFile
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
SECRET = os.getenv("LM_COMPLY_SECRET", "change-me-in-production").encode()
INSPECTOR_PASSWORD = os.getenv("LM_COMPLY_PASSWORD", "inspector123")
os.makedirs(UP, exist_ok=True)
app = FastAPI(title="LM Comply", version="4.0")
db.init()


def _token(role_name: str) -> str:
    payload = f"{role_name}:{int(time.time())}"
    sig = hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def _verify_token(token: str | None):
    if not token:
        return None
    parts = token.split(":")
    if len(parts) != 3:
        return None
    role_name, issued, sig = parts
    if role_name not in {"inspector", "admin"}:
        return None
    try:
        if time.time() - int(issued) > 12 * 3600:
            return None
    except ValueError:
        return None
    expected = hmac.new(SECRET, f"{role_name}:{issued}".encode(), hashlib.sha256).hexdigest()
    return role_name if hmac.compare_digest(sig, expected) else None


def role(x_role: str = Header(default=""), lm_session: str | None = Cookie(default=None)):
    authenticated = _verify_token(lm_session)
    if authenticated:
        return authenticated
    if x_role in {"inspector", "admin"} and os.getenv("LM_COMPLY_ALLOW_HEADER_ROLE", "0") == "1":
        return x_role
    raise HTTPException(401, "Authentication required")


@app.post("/api/auth/login")
def login(password: str = Form(...), requested_role: str = Form("inspector"), response: Response = None):
    if requested_role not in {"inspector", "admin"} or not hmac.compare_digest(password, INSPECTOR_PASSWORD):
        raise HTTPException(401, "Invalid credentials")
    token = _token(requested_role)
    response.set_cookie("lm_session", token, httponly=True, samesite="lax", secure=os.getenv("COOKIE_SECURE", "0") == "1", max_age=12 * 3600)
    return {"ok": True, "role": requested_role, "expires_in": 12 * 3600}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("lm_session")
    return {"ok": True}


@app.get("/api/auth/me")
def me(lm_session: str | None = Cookie(default=None)):
    r = _verify_token(lm_session)
    return {"authenticated": bool(r), "role": r}


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
    return {"status": "ok", "service": "LM Comply", "version": "4.0"}


@app.post("/api/scan")
async def scan(file: UploadFile = File(...), px_per_mm: float | None = Form(None), demo_text: str = Form(""), client_ocr: str = Form(""), category: str = Form("general"), x_role: str = Header(default=""), lm_session: str | None = Cookie(default=None)):
    role(x_role, lm_session)
    if px_per_mm is not None and not (0 < px_per_mm < 10000):
        raise HTTPException(400, "px_per_mm must be between 0 and 10000")
    img_path = await save_upload(file)
    ocr = extract.ocr_data(img_path)
    manual_text = (demo_text or "").strip()
    browser_text = (client_ocr or "").strip()
    if manual_text:
        text, engine, ocr_confidence = manual_text, "manual/demo", 1.0
    elif ocr["text"]:
        text, engine, ocr_confidence = ocr["text"], "server-tesseract", ocr["confidence"]
    elif browser_text:
        text, engine, ocr_confidence = browser_text, "browser-tesseract", 0.65
    else:
        text, engine, ocr_confidence = "", "none", 0.0
    fields = extract.parse_fields(text)
    fields["ocr_confidence"] = round(ocr_confidence, 3)
    ppm = px_per_mm or extract.px_per_mm_from_image(img_path)
    fields["font_mm"] = extract.mrp_font_mm(fields, ocr["boxes"], ppm) if engine == "server-tesseract" else None
    violations = rules.evaluate(fields, {"px_per_mm": ppm, "font_mm": fields["font_mm"], "ocr_confidence": fields["ocr_confidence"], "boxes": ocr["boxes"]})
    hard_findings = [v for v in violations if v["severity"] in {"CRITICAL", "MAJOR"}]
    review_findings = [v for v in violations if v["severity"] == "REVIEW"]
    status = "NON_COMPLIANT" if hard_findings else ("REVIEW_REQUIRED" if review_findings else "COMPLIANT")
    product_name = (fields.get("product_name") or {}).get("value") or "Unknown product"
    brand = product_name.split()[0][:40] if product_name else "Unknown"
    pid = db.run("INSERT INTO products(name,brand,category,created_at) VALUES(?,?,?,?)", (product_name[:120], brand, category[:40], time.time()))
    sid = db.run("INSERT INTO scans(product_id,image_path,ocr_text,extracted,status,created_at) VALUES(?,?,?,?,?,?)", (pid, img_path, text, json.dumps(fields), status, time.time()))
    for v in violations:
        db.run("INSERT INTO violations(scan_id,rule_id,severity,message,evidence) VALUES(?,?,?,?,?)", (sid, v["rule_id"], v["severity"], v["message"], json.dumps(v.get("evidence")) if v.get("evidence") else None))
    return {"scan_id": sid, "product_id": pid, "status": status, "category": category, "extracted": fields, "violations": violations, "engine": engine, "evidence_boxes": ocr["boxes"] if engine == "server-tesseract" else []}


@app.get("/api/scans")
def scans(qtext: str = Query("", alias="q"), status: str = Query(""), category: str = Query(""), limit: int = Query(100, ge=1, le=500), x_role: str = Header(default=""), lm_session: str | None = Cookie(default=None)):
    role(x_role, lm_session)
    sql = "SELECT s.*, p.name product_name, p.brand, p.category FROM scans s JOIN products p ON p.id=s.product_id WHERE 1=1"
    args = []
    if qtext.strip():
        sql += " AND (p.name LIKE ? OR p.brand LIKE ? OR s.ocr_text LIKE ?)"
        like = f"%{qtext.strip()}%"
        args += [like, like, like]
    if status in {"COMPLIANT", "NON_COMPLIANT", "REVIEW_REQUIRED"}:
        sql += " AND s.status=?"
        args.append(status)
    if category.strip():
        sql += " AND p.category=?"
        args.append(category.strip())
    sql += " ORDER BY s.id DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in db.q(sql, tuple(args))]


@app.get("/api/scans/{scan_id}")
def scan_detail(scan_id: int, x_role: str = Header(default=""), lm_session: str | None = Cookie(default=None)):
    role(x_role, lm_session)
    row = db.q("SELECT s.*, p.name product_name, p.brand, p.category FROM scans s JOIN products p ON p.id=s.product_id WHERE s.id=?", (scan_id,), one=True)
    if not row:
        raise HTTPException(404, "Scan not found")
    out = dict(row)
    out["extracted"] = json.loads(out.get("extracted") or "{}")
    out["violations"] = [dict(v) for v in db.q("SELECT * FROM violations WHERE scan_id=? ORDER BY id", (scan_id,))]
    return out


@app.get("/api/dashboard")
def dashboard(x_role: str = Header(default=""), lm_session: str | None = Cookie(default=None)):
    role(x_role, lm_session)
    total = db.q("SELECT COUNT(*) c FROM scans", one=True)["c"]
    nc = db.q("SELECT COUNT(*) c FROM scans WHERE status=?", ("NON_COMPLIANT",), one=True)["c"]
    review = db.q("SELECT COUNT(*) c FROM scans WHERE status=?", ("REVIEW_REQUIRED",), one=True)["c"]
    by_rule = db.q("SELECT rule_id, COUNT(*) c FROM violations GROUP BY rule_id ORDER BY c DESC")
    by_sev = db.q("SELECT severity, COUNT(*) c FROM violations GROUP BY severity ORDER BY c DESC")
    by_category = db.q("SELECT p.category, COUNT(*) c FROM scans s JOIN products p ON p.id=s.product_id GROUP BY p.category ORDER BY c DESC")
    return {"total_scans": total, "non_compliant": nc, "review_required": review, "compliance_rate": round(100 * (total - nc - review) / total, 1) if total else 100.0, "violations_by_rule": [dict(r) for r in by_rule], "violations_by_severity": [dict(r) for r in by_sev], "scans_by_category": [dict(r) for r in by_category]}


def _report_row(scan_id: int):
    scan_row = db.q("SELECT * FROM scans WHERE id=?", (scan_id,), one=True)
    if not scan_row:
        raise HTTPException(404, "Scan not found")
    product = db.q("SELECT * FROM products WHERE id=?", (scan_row["product_id"],), one=True)
    violations = [dict(r) for r in db.q("SELECT * FROM violations WHERE scan_id=?", (scan_id,))]
    return scan_row, product, violations


@app.get("/api/report/{scan_id}.pdf")
def pdf(scan_id: int, x_role: str = Header(default=""), lm_session: str | None = Cookie(default=None)):
    role(x_role, lm_session)
    scan_row, product, violations = _report_row(scan_id)
    out = os.path.join(UP, f"report_{scan_id}.pdf")
    report.build_pdf(scan_row, product, violations, out)
    return FileResponse(out, media_type="application/pdf", filename=f"compliance_report_{scan_id}.pdf")


@app.get("/api/report/{scan_id}.docx")
def docx(scan_id: int, x_role: str = Header(default=""), lm_session: str | None = Cookie(default=None)):
    role(x_role, lm_session)
    scan_row, product, violations = _report_row(scan_id)
    out = os.path.join(UP, f"report_{scan_id}.docx")
    report.build_docx(scan_row, product, violations, out)
    return FileResponse(out, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=f"compliance_report_{scan_id}.docx")


app.mount("/", StaticFiles(directory=os.path.join(BASE, "frontend"), html=True), name="ui")
