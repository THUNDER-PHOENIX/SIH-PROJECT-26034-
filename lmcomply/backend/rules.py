"""Auditable screening rules for Legal Metrology packaged commodities.

This is an AI-assisted screening layer. It flags potential non-compliance for
inspector verification; it does not replace legal adjudication. Applicability
and thresholds must be reviewed against the current notified Rules/Schedules.
"""

import re

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
    mrp, qty, date = _val(f, "mrp"), _val(f, "net_qty"), _val(f, "date")
    care, manufacturer = _val(f, "consumer_care"), _val(f, "manufacturer")
    ocr_conf = float(ctx.get("ocr_confidence", 0) or 0)

    # Missing after uncertain OCR is a review finding, not proof of illegality.
    if not mrp:
        add("RULE-MRP-001", "REVIEW", "MRP declaration could not be reliably extracted; inspect the label manually", "mrp")
    else:
        if not any(x in raw for x in ("₹", "rs", "inr")):
            add("RULE-MRP-002", "REVIEW", "MRP value found, but currency marker could not be verified", "mrp")
        try:
            if float(mrp) <= 0:
                add("RULE-MRP-003", "MAJOR", "MRP must be a positive value", "mrp")
        except (TypeError, ValueError):
            add("RULE-MRP-003", "REVIEW", "MRP value could not be parsed reliably", "mrp")

    if not qty:
        add("RULE-QTY-001", "REVIEW", "Net quantity could not be reliably extracted; inspect the declaration manually", "net_qty")
    else:
        try:
            number, unit = qty
            if float(str(number).replace(",", "")) <= 0:
                add("RULE-QTY-002", "MAJOR", "Net quantity must be positive", "net_qty")
            if str(unit).lower() not in VALID_UNITS:
                add("RULE-QTY-003", "REVIEW", f"Unrecognised net-quantity unit '{unit}'", "net_qty")
        except (TypeError, ValueError):
            add("RULE-QTY-002", "REVIEW", "Net quantity could not be parsed reliably", "net_qty")

    if not date:
        add("RULE-DATE-001", "REVIEW", "Manufacture/packing/use-by date could not be reliably extracted; inspect the label", "date")

    if not care:
        add("RULE-CARE-001", "REVIEW", "Consumer-care contact could not be reliably extracted; inspect the label", "consumer_care")

    if not manufacturer:
        add("RULE-MFG-001", "REVIEW", "Manufacturer/packer/marketer declaration could not be reliably extracted", "manufacturer")

    if bool(f.get("imported")):
        if not _val(f, "origin"):
            add("RULE-ORIGIN-001", "REVIEW", "Imported product: Country of Origin could not be reliably extracted", "origin")
        if not _val(f, "importer"):
            add("RULE-IMP-001", "REVIEW", "Imported product: importer declaration could not be reliably extracted", "importer")

    font_mm = ctx.get("font_mm")
    if font_mm is not None and font_mm < MIN_FONT_MM:
        add("RULE-FONT-001", "MAJOR", f"Estimated declaration font is ~{font_mm} mm; verify against the applicable schedule")
    elif font_mm is None:
        add("RULE-FONT-002", "INFO", "Font size could not be reliably measured; manual verification recommended")

    if ocr_conf < 0.45:
        add("RULE-OCR-001", "REVIEW", "OCR confidence is low; recapture the label in better lighting and focus")
    elif ocr_conf < 0.65:
        add("RULE-OCR-002", "INFO", "Some declarations may require manual verification because OCR confidence is moderate")

    if ctx.get("boxes") and not any(re.sub(r"[^a-z]", "", str(b.get("text", "")).lower()) in {"mrp", "maximumretailprice"} for b in ctx["boxes"]):
        add("RULE-VIS-001", "INFO", "MRP label position could not be confidently localized; inspector should verify placement/readability")

    return violations
