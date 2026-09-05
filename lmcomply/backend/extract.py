import re
import shutil
from typing import Any

from PIL import Image, ImageOps

try:
    import pytesseract
    HAS_TESS = shutil.which("tesseract") is not None
except Exception:
    HAS_TESS = False

PHONE_RE = re.compile(r"(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
DATE_RE = re.compile(r"(?:mfg|mfd|pkd|packed|manufactured|imported)[^\d]{0,15}(\d{1,2}[/-])?(20\d{2})", re.I)
QTY_RE = re.compile(r"(?:net\s*(?:qty|quantity|wt|weight))?\s*([\d.,]+)\s*(kg|g|mg|l|ml|cl|m|cm|mm|pcs|pieces?|units?)\b", re.I)
MRP_RE = re.compile(r"(?:mrp|maximum\s+retail\s+price)[^\d₹]{0,15}(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d{1,2})?)", re.I)
ORIGIN_RE = re.compile(r"country\s+of\s+origin\s*[:\-]?\s*([a-z][a-z .,&'-]{1,40})", re.I)


def _normalise(text: str) -> str:
    return " ".join((text or "").replace("\n", " ").split())


def ocr_data(path: str) -> dict[str, Any]:
    if not HAS_TESS:
        return {"text": "", "confidence": 0.0, "boxes": []}
    try:
        image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config="--psm 6")
        words, confs = [], []
        for i, raw in enumerate(data["text"]):
            text = raw.strip()
            try:
                conf = float(data["conf"][i])
            except (ValueError, TypeError):
                conf = -1
            if text:
                words.append({"text": text, "h": int(data["height"][i]), "conf": max(0.0, conf)})
                if conf >= 0:
                    confs.append(conf)
        return {"text": " ".join(w["text"] for w in words), "confidence": round(sum(confs) / len(confs) / 100, 3) if confs else 0.0, "boxes": words}
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


def _field(value, confidence):
    return {"value": value, "confidence": round(max(0.0, min(1.0, confidence)), 2)} if value is not None else {"value": None, "confidence": 0.0}


def parse_fields(text: str):
    t = _normalise(text)
    low = t.lower()
    f = {"raw": t}

    m = MRP_RE.search(t)
    f["mrp"] = m.group(1).replace(",", "") if m else None
    f["mrp_confidence"] = 0.95 if m else 0.0

    m = QTY_RE.search(t)
    f["net_qty"] = (m.group(1), m.group(2).lower().rstrip("s")) if m else None
    f["net_qty_confidence"] = 0.9 if m else 0.0

    m = DATE_RE.search(t)
    f["date"] = m.group(0)[:60] if m else None
    f["date_confidence"] = 0.9 if m else 0.0

    f["phone"] = bool(PHONE_RE.search(t) or re.search(r"1?800[-\s]?\d{3}[-\s]?\d{4}", t))
    f["email"] = bool(EMAIL_RE.search(t))
    f["contact_confidence"] = 0.95 if (f["phone"] or f["email"]) else 0.0

    f["imported"] = bool(re.search(r"\bimported\b|country\s+of\s+origin", low))
    m = ORIGIN_RE.search(t)
    f["origin"] = m.group(1).strip(" .,") if m else None
    f["importer_addr"] = bool(re.search(r"imported\s+(?:by|&\s*marketed\s+by)", low))
    f["mfr_decl"] = bool(re.search(r"(?:manufactured|packed|marketed)\s+by\s*[:\-]", low) or re.search(r"mfg\s+by\s*[:\-]", low))

    m = re.search(r"best\s+before\s*[:\-]?\s*([^;]{1,30})", t, re.I)
    f["best_before"] = m.group(1).strip() if m else None
    return f


def mrp_font_mm(fields, boxes, px_per_mm):
    if not boxes or not px_per_mm or not fields.get("mrp"):
        return None
    target = fields["mrp"].replace(",", "")
    candidates = []
    for b in boxes:
        token = b["text"].replace(",", "")
        if any(ch.isdigit() for ch in token) and target in token:
            candidates.append(b["h"])
    if not candidates:
        return None
    return round(max(candidates) / float(px_per_mm), 2)
