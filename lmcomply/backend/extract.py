import re
import shutil
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:
    import pytesseract
    HAS_TESS = shutil.which("tesseract") is not None
except Exception:
    HAS_TESS = False

PHONE_RE = re.compile(r"(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
DATE_RE = re.compile(r"(?:mfg|mfd|pkd|packed|manufactured|manufacture|imported|date)[^\d]{0,20}(\d{1,2}[/-])?(20\d{2})", re.I)
QTY_RE = re.compile(r"(?:net\s*(?:qty|quantity|wt|weight)\s*[:\-]?\s*)?([\d.,]+)\s*(kg|g|mg|l|ml|cl|pcs|pieces?|units?)\b", re.I)
MRP_RE = re.compile(r"(?:mrp|maximum\s+retail\s+price)[^\d₹]{0,20}(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d{1,2})?)", re.I)
ORIGIN_RE = re.compile(r"country\s+of\s+origin\s*[:\-]?\s*([a-z][a-z .,&'-]{1,40})", re.I)


def _normalise(text: str) -> str:
    return " ".join((text or "").replace("\n", " ").split())


def _preprocess(image: Image.Image) -> list[Image.Image]:
    image = ImageOps.exif_transpose(image).convert("RGB")
    # Upscaling and contrast/sharpening materially improve small declarations.
    scale = 2.0 if max(image.size) < 2200 else 1.35
    up = image.resize((int(image.width * scale), int(image.height * scale)))
    gray = ImageOps.grayscale(up)
    gray = ImageEnhance.Contrast(gray).enhance(1.6)
    gray = ImageEnhance.Sharpness(gray).enhance(1.8)
    gray = gray.filter(ImageFilter.MedianFilter(size=3))
    return [up, gray]


def ocr_data(path: str) -> dict[str, Any]:
    if not HAS_TESS:
        return {"text": "", "confidence": 0.0, "boxes": []}
    try:
        source = Image.open(path)
        best = {"text": "", "confidence": -1.0, "boxes": []}
        for image in _preprocess(source):
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config="--psm 6")
            words, confs = [], []
            for i, raw in enumerate(data["text"]):
                text = raw.strip()
                try:
                    conf = float(data["conf"][i])
                except (ValueError, TypeError):
                    conf = -1
                if text:
                    item = {
                        "text": text,
                        "left": int(data["left"][i]), "top": int(data["top"][i]),
                        "width": int(data["width"][i]), "height": int(data["height"][i]),
                        "conf": max(0.0, conf),
                    }
                    words.append(item)
                    if conf >= 0:
                        confs.append(conf)
            avg = (sum(confs) / len(confs) / 100) if confs else 0.0
            if avg > best["confidence"]:
                best = {"text": " ".join(w["text"] for w in words), "confidence": avg, "boxes": words}
        best["confidence"] = round(max(0.0, best["confidence"]), 3)
        return best
    except Exception:
        return {"text": "", "confidence": 0.0, "boxes": []}


def ocr_text(path):
    return ocr_data(path)["text"]


def word_boxes(path):
    return ocr_data(path)["boxes"]


def px_per_mm_from_image(path):
    try:
        image = Image.open(path)
        dpi = image.info.get("dpi", (96, 96))[0] or 96
        return float(dpi) / 25.4
    except Exception:
        return 96 / 25.4


def _value(value, confidence=0.0, evidence=None):
    out = {"value": value, "confidence": round(max(0.0, min(1.0, confidence)), 2)}
    if evidence:
        out["evidence"] = evidence
    return out


def _match(pattern, text, confidence=0.9):
    m = pattern.search(text)
    return _value(m.group(1).strip(" .,") if m and m.lastindex else (m.group(0) if m else None), confidence if m else 0.0) if m else _value(None)


def parse_fields(text: str):
    t = _normalise(text)
    low = t.lower()
    f = {"raw": t}

    m = MRP_RE.search(t)
    f["mrp"] = _value(m.group(1).replace(",", "") if m else None, 0.95 if m else 0.0)
    m = QTY_RE.search(t)
    f["net_qty"] = _value([m.group(1), m.group(2).lower().rstrip("s")] if m else None, 0.9 if m else 0.0)
    m = DATE_RE.search(t)
    f["date"] = _value(m.group(0)[:60] if m else None, 0.9 if m else 0.0)

    phone = PHONE_RE.search(t) or re.search(r"1?800[-\s]?\d{3}[-\s]?\d{4}", t)
    email = EMAIL_RE.search(t)
    f["consumer_care"] = _value(phone.group(0) if phone else (email.group(0) if email else None), 0.95 if phone or email else 0.0)
    f["phone"] = bool(phone)
    f["email"] = bool(email)

    f["imported"] = bool(re.search(r"\bimported\b|country\s+of\s+origin", low))
    m = ORIGIN_RE.search(t)
    f["origin"] = _value(m.group(1).strip(" .,") if m else None, 0.9 if m else 0.0)

    manufacturer = re.search(r"(?:manufactured|manufactured/packed|packed|marketed|manufactured\s*&\s*packed)\s+by\s*[:\-]?\s*(.{3,100})", t, re.I)
    importer = re.search(r"(?:imported\s+by|importer\s*[:\-])\s*(.{3,100})", t, re.I)
    f["manufacturer"] = _value(manufacturer.group(1).strip(" .,-") if manufacturer else None, 0.9 if manufacturer else 0.0)
    f["importer"] = _value(importer.group(1).strip(" .,-") if importer else None, 0.9 if importer else 0.0)
    f["mfr_decl"] = bool(manufacturer or re.search(r"\bmfg\s+by\b", low))

    product = re.search(r"(?:product\s*name|name\s+of\s+product)\s*[:\-]\s*([^,;]+)", t, re.I)
    f["product_name"] = _value(product.group(1).strip() if product else None, 0.85 if product else 0.0)

    m = re.search(r"best\s+before\s*[:\-]?\s*([^;]{1,30})", t, re.I)
    f["best_before"] = _value(m.group(1).strip() if m else None, 0.85 if m else 0.0)
    return f


def mrp_font_mm(fields, boxes, px_per_mm):
    if not boxes or not px_per_mm or not fields.get("mrp", {}).get("value"):
        return None
    target = str(fields["mrp"]["value"]).replace(",", "")
    candidates = []
    for b in boxes:
        token = b["text"].replace(",", "")
        if any(ch.isdigit() for ch in token) and target in token:
            candidates.append(b["height"])
    if not candidates:
        return None
    return round(max(candidates) / float(px_per_mm), 2)
