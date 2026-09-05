"""Auditable screening rules for Legal Metrology packaged commodities.

This is an AI-assisted screening layer. It flags potential non-compliance for
inspector verification; it does not replace legal adjudication. Thresholds and
applicability must be reviewed against the current notified Rules/Schedules.
"""

MIN_FONT_MM = 2.0
VALID_UNITS = {"kg", "g", "mg", "l", "ml", "cl", "pcs", "piece", "unit", "u"}


def _val(f, key):
    item = f.get(key)
    return item.get("value") if isinstance(item, dict) else item


def evaluate(f, ctx):
    violations = []

    def add(rule_id, severity, message, field=None):
        item = {"rule_id": rule_id, "severity": severity, "message": message}
        if field and isinstance(f.get(field), dict) and f[field].get("evidence"):
            item["evidence"] = f[field]["evidence"]
        violations.append(item)

    raw = (f.get("raw") or "").lower()
    mrp = _val(f, "mrp")
    qty = _val(f, "net_qty")
    date = _val(f, "date")
    care = _val(f, "consumer_care")
    manufacturer = _val(f, "manufacturer")

    if not mrp:
        add("RULE-MRP-001", "CRITICAL", "Maximum Retail Price (MRP) declaration could not be identified", "mrp")
    else:
        if not any(x in raw for x in ("₹", "rs", "inr")):
            add("RULE-MRP-002", "MAJOR", "MRP value found, but a currency marker could not be verified", "mrp")
        try:
            if float(mrp) <= 0:
                add("RULE-MRP-003", "MAJOR", "MRP must be a positive value", "mrp")
        except (TypeError, ValueError):
            add("RULE-MRP-003", "MAJOR", "MRP value could not be parsed", "mrp")

    if not qty:
        add("RULE-QTY-001", "CRITICAL", "Net quantity declaration could not be identified", "net_qty")
    else:
        try:
            number, unit = qty
            if float(str(number).replace(",", "")) <= 0:
                add("RULE-QTY-002", "MAJOR", "Net quantity must be positive", "net_qty")
            if str(unit).lower() not in VALID_UNITS:
                add("RULE-QTY-003", "MAJOR", f"Unrecognised net-quantity unit '{unit}'", "net_qty")
        except (TypeError, ValueError):
            add("RULE-QTY-002", "MAJOR", "Net quantity could not be parsed", "net_qty")

    if not date:
        add("RULE-DATE-001", "CRITICAL", "Month/year of manufacture, packing or import could not be identified", "date")

    if not care:
        add("RULE-CARE-001", "MAJOR", "Consumer-care contact could not be identified", "consumer_care")

    if not manufacturer:
        add("RULE-MFG-001", "MAJOR", "Manufacturer/packer/marketer declaration could not be identified", "manufacturer")

    imported = bool(f.get("imported"))
    if imported:
        if not _val(f, "origin"):
            add("RULE-ORIGIN-001", "MAJOR", "Imported product: Country of Origin could not be identified", "origin")
        if not _val(f, "importer"):
            add("RULE-IMP-001", "MAJOR", "Imported product: importer declaration could not be identified", "importer")

    font_mm = ctx.get("font_mm")
    if font_mm is not None:
        if font_mm < MIN_FONT_MM:
            add("RULE-FONT-001", "MAJOR", f"Estimated declaration font is ~{font_mm} mm; verify against the applicable schedule")
    else:
        add("RULE-FONT-002", "INFO", "Font size could not be reliably measured from image metadata; manual verification recommended")

    if ctx.get("ocr_confidence", 0) < 0.45:
        add("RULE-OCR-001", "INFO", "OCR confidence is low; recapture the label in better lighting and focus")

    # Visual-placement proxy: OCR must find declaration-like text in the image.
    if ctx.get("boxes") and not any(str(b.get("text", "")).lower() in {"mrp", "m.r.p", "maximum"} for b in ctx["boxes"]):
        add("RULE-VIS-001", "INFO", "MRP label position could not be confidently localized; inspector should verify placement/readability")

    return violations
