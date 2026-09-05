import re
import shutil
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:
    import pytesseract
    HAS_TESS = shutil.which("tesseract") is not None
except Exception:
    HAS_TESS = False

# Patterns deliberately tolerate common OCR substitutions/spaces found on packaging.
PHONE_RE = re.compile(r"(?:\+?91[\s.-]?)?[6-9]\d{4}[\s.-]?\d{5}")
TOLL_RE = re.compile(r"(?:toll\s*free|call|helpline|consumer\s*care)[^\d]{0,35}(1?800[\s.-]?\d{3}[\s.-]?\d{4})", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+\s*@\s*[\w-]+(?:\s*\.\s*[\w-]+)+")
MRP_RE = re.compile(r"(?:m\s*\.?r\s*\.?p\s*\.?|maximum\s+retail\s+price)[^\d₹]{0,35}(?:₹|rs\.?|inr)?\s*([0-9]{1,6}(?:[.,][0-9]{1,2})?)", re.I)
QTY_RE = re.compile(r"(?:net\s*(?:qty|quantity|wt|weight)|nett\s*(?:wt|weight)|net\s*contents?)\s*[:\-]?\s*([0-9]{1,7}(?:[.,][0-9]{1,3})?)\s*(kg|g|mg|l|ml|cl|pcs|pieces?|units?)\b", re.I)
QTY_FALLBACK_RE = re.compile(r"\b([0-9]{1,7}(?:[.,][0-9]{1,3})?)\s*(kg|g|mg|l|ml|cl|pcs|pieces?|units?)\b", re.I)
DATE_RE = re.compile(r"(?:mfg|mfd|mfg\.?\s*date|mfd\.?\s*date|pkd|packed|packing|manufactured|manufacture|date\s+of\s+(?:mfg|manufacture|packing)|use\s*by|best\s*before)[^\dA-Za-z]{0,30}(?:[:\-]?\s*)?((?:0?[1-9]|1[0-2])[/-]\s*(?:20)?\d{2}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s*[-./ ]?\s*\d{2,4})", re.I)
ORIGIN_RE = re.compile(r"country\s+of\s+origin\s*[:\-]?\s*([a-z][a-z .,&'\-]{1,40})", re.I)


def _normalise(text: str) -> str:
    t = (text or "").replace("\n", " ")
    t = re.sub(r"\s*@\s*", "@", t)
    t = re.sub(r"\s*\.\s*", ".", t)
    return " ".join(t.split())


def _preprocess(image: Image.Image) -> list[Image.Image]:
    image = ImageOps.exif_transpose(image).convert("RGB")
    scale = 2.4 if max(image.size) < 1800 else (1.7 if max(image.size) < 3000 else 1.25)
    up = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
    gray = ImageOps.grayscale(up)
    gray = ImageEnhance.Contrast(gray).enhance(1.8)
    gray = ImageEnhance.Sharpness(gray).enhance(2.0)
    binary = gray.point(lambda p: 255 if p > 165 else 0)
    return [up, gray, binary]


def _run_ocr(image: Image.Image, config: str) -> dict[str, Any]:
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config=config)
    words, confs = [], []
    for i, raw in enumerate(data.get("text", [])):
        text = raw.strip()
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError, KeyError):
            conf = -1
        if text:
            item = {"text": text, "left": int(data["left"][i]), "top": int(data["top"][i]),
                    "width": int(data["width"][i]), "height": int(data["height"][i]),
                    "conf": max(0.0, conf)}
            words.append(item)
            if conf >= 0:
                confs.append(conf)
    avg = sum(confs) / len(confs) / 100 if confs else 0.0
    return {"text": " ".join(w["text"] for w in words), "confidence": avg, "boxes": words}


def ocr_data(path: str) -> dict[str, Any]:
    if not HAS_TESS:
        return {"text": "", "confidence": 0.0, "boxes": []}
    try:
        source = Image.open(path)
        best = {"text": "", "confidence": -1.0, "boxes": []}
        # PSM 6 handles dense labels; PSM 11 helps scattered text such as nutrition panels.
        for image in _preprocess(source):
            for psm in (6, 11):
                result = _run_ocr(image, f"--oem 3 --psm {psm}")
                # Prefer confidence, but don't let an empty/high-confidence fragment win.
                score = result["confidence"] + (0.03 if len(result["text"]) > 80 else 0)
                if score > best["confidence"]:
                    best = result
        best["confidence"] = round(max(0.0, min(1.0, best["confidence"])), 3)
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


def _evidence(text: str, start: int, end: int):
    return text[max(0, start - 40):min(len(text), end + 40)]


def parse_fields(text: str):
    t = _normalise(text)
    low = t.lower()
    f = {"raw": t}

    m = MRP_RE.search(t)
    f["mrp"] = _value(m.group(1).replace(",", "").replace(" ", "") if m else None,
                       0.96 if m else 0.0, _evidence(t, m.start(), m.end()) if m else None)

    m = QTY_RE.search(t)
    if not m:
        # Only use the fallback when a quantity-like phrase occurs nearby; avoids grabbing nutrition values.
        near = re.search(r"(?:net|nett|quantity|contents|weight|wt)[^.;]{0,45}" + QTY_FALLBACK_RE.pattern, t, re.I)
        m = near
    if m:
        groups = m.groups()
        number, unit = groups[-2], groups[-1]
        f["net_qty"] = _value([number.replace(",", ""), unit.lower().rstrip("s")], 0.94,
                               _evidence(t, m.start(), m.end()))
    else:
        f["net_qty"] = _value(None)

    m = DATE_RE.search(t)
    f["date"] = _value(m.group(1).strip() if m else None, 0.93 if m else 0.0,
                        _evidence(t, m.start(), m.end()) if m else None)

    # Toll-free/helpline numbers get priority. Exclude likely FSSAI/licence numbers and ordinary dates.
    phone = TOLL_RE.search(t)
    if phone:
        consumer = phone.group(1)
    else:
        care_window = re.search(r"(?:consumer\s*care|feedback|queries|helpline|call)[^.;]{0,80}", t, re.I)
        candidate = PHONE_RE.search(care_window.group(0)) if care_window else None
        consumer = candidate.group(0) if candidate else None
    email = EMAIL_RE.search(t)
    if consumer:
        f["consumer_care"] = _value(consumer, 0.97)
    elif email:
        f["consumer_care"] = _value(email.group(0), 0.9)
    else:
        f["consumer_care"] = _value(None)
    f["phone"] = bool(consumer)
    f["email"] = bool(email)

    f["imported"] = bool(re.search(r"\bimported\b|country\s+of\s+origin", low))
    m = ORIGIN_RE.search(t)
    f["origin"] = _value(m.group(1).strip(" .,") if m else None, 0.9 if m else 0.0)

    # Stop manufacturer capture before address/nutrition/contact sections.
    manufacturer = re.search(r"(?:manufactured\s*&\s*packed|manufactured/packed|manufactured|packed|marketed)\s+by\s*[:\-]?\s*(.{3,90}?)(?=\s*(?:plot\s+no|address\s*:|\b(?:website|email|call|toll\s*free|ingredients|nutrition|net\s+quantity|lic\.?\s*no)\b|$))", t, re.I)
    importer = re.search(r"(?:imported\s+by|importer)\s*[:\-]?\s*(.{3,90}?)(?=\s*(?:plot\s+no|address\s*:|\b(?:website|email|call|toll\s*free|lic\.?\s*no)\b|$))", t, re.I)
    f["manufacturer"] = _value(manufacturer.group(1).strip(" .,-") if manufacturer else None, 0.93 if manufacturer else 0.0)
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
