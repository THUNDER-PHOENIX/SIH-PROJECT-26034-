
import re, shutil
try:
    import pytesseract
    HAS_TESS = shutil.which("tesseract") is not None
except Exception:
    HAS_TESS = False

from PIL import Image

def ocr_text(path):
    if not HAS_TESS: return ""
    return pytesseract.image_to_string(Image.open(path))

def word_boxes(path):
    """Return list of {text, h(px)} for font-size estimation."""
    if not HAS_TESS: return []
    data = pytesseract.image_to_data(Image.open(path), output_type=pytesseract.Output.DICT)
    out = []
    for i in range(len(data["text"])):
        if data["text"][i].strip():
            out.append({"text": data["text"][i], "h": data["height"][i]})
    return out

def px_per_mm_from_image(path):
    try:
        dpi = Image.open(path).info.get("dpi", (96, 96))[0]
    except Exception:
        dpi = 96
    return dpi / 25.4

def parse_fields(text):
    t = " ".join(text.replace("\n", " ").split())
    low = t.lower()
    f = {"raw": t}
    m = re.search(r"(?:mrp[^\d]{0,15})(?:rs\.?|₹|inr)?\s*([\d,]+(?:\.[0-9]{1,2})?)", low)
    f["mrp"] = m.group(1) if m else None
    m = re.search(r"([\d.,]+)\s?(kg|g|mg|l|ml|cl|m|cm|mm|pcs|piece|unit|u)s?\b", low)
    f["net_qty"] = (m.group(1), m.group(2)) if m else None
    m = re.search(r"(mfg|pkd|manufactured|packed|imported)[^\d]{0,8}([01]?[0-9]/)?(20\d{2})", low)
    f["date"] = (m.group(0)[:40] if m else None)
    f["phone"] = bool(re.search(r"(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}", t)) or bool(re.search(r"1?800[-\s]?\d{3}[-\s]?\d{4}", t.replace(" ", "")))
    f["email"] = bool(re.search(r"[\w.]+@[\w.]+", t))
    f["imported"] = ("import" in low) or ("country of origin" in low)
    f["origin"] = re.search(r"country of origin[:\s]+([a-z ]{2,20})", low)
    f["importer_addr"] = ("imported by" in low) or ("imported & marketed by" in low) or ("marketer" in low)
    f["mfr_decl"] = any(k in low for k in ("manufactured by", "packed by", "marketed by", "mfg by", "mfg:"))
    m = re.search(r"best before[^a-z]{0,25}([0-9].{0,20})", low)
    f["best_before"] = m.group(1) if m else None
    return f

def mrp_font_mm(fields, boxes, px_per_mm):
    """Estimate physical height of the MRP numerals via OCR box height."""
    if not boxes or not px_per_mm: return None
    mrp = (fields.get("mrp") or "").replace(",", "")
    cands = [b["h"] for b in boxes if mrp and mrp in b["text"].replace(",", "")]
    if not cands:  # fallback: smallest-height digit token on the label
        digs = [b["h"] for b in boxes if re.search(r"\d", b["text"])]
        cands = [min(digs)] if digs else []
    return round(min(cands) / px_per_mm, 2) if cands else None
