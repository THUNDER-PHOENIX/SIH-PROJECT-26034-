"""Deterministic screening rules for packaged-commodity labels.

These checks are intended as an auditable screening layer, not legal adjudication.
Verify rule thresholds against the current applicable Legal Metrology schedule.
"""

MIN_FONT_MM = 2.0
VALID_UNITS = {"kg", "g", "mg", "l", "ml", "cl", "m", "cm", "mm", "pcs", "piece", "unit", "u"}


def evaluate(f, ctx):
    violations = []

    def add(rule_id, severity, message, evidence=None):
        item = {"rule_id": rule_id, "severity": severity, "message": message}
        if evidence:
            item["evidence"] = evidence
        violations.append(item)

    raw = (f.get("raw") or "").lower()

    if not f.get("mrp"):
        add("R6(1)(e)", "CRITICAL", "MRP declaration could not be identified")
    else:
        if not any(x in raw for x in ("₹", "rs", "inr")):
            add("R6(1)(e)", "MAJOR", "MRP currency marker (₹/Rs./INR) could not be verified")
        try:
            if float(f["mrp"]) < 0:
                add("R6(1)(e)", "MAJOR", "MRP value is invalid")
        except (TypeError, ValueError):
            add("R6(1)(e)", "MAJOR", "MRP value could not be parsed")

    qty = f.get("net_qty")
    if not qty:
        add("R6(1)(b)", "CRITICAL", "Net quantity declaration could not be identified")
    elif qty[1].lower() not in VALID_UNITS:
        add("R6(1)(b)", "MAJOR", f"Unrecognised net-quantity unit '{qty[1]}'")

    if not f.get("date"):
        add("R6(1)(f)", "CRITICAL", "Month and year of manufacture/packing/import could not be identified")

    if not (f.get("phone") or f.get("email")):
        add("R6(1)(g)", "MAJOR", "Consumer-care contact (phone/email) could not be identified")

    if f.get("imported"):
        if not f.get("origin"):
            add("R6(1)(i)", "MAJOR", "Imported product: Country of Origin could not be identified")
        if not f.get("importer_addr"):
            add("R6(1)(a)", "MAJOR", "Imported product: importer declaration could not be identified")

    if not f.get("mfr_decl"):
        add("R6(1)(a)", "MAJOR", "Manufacturer/packer/marketer declaration could not be identified")

    font_mm = ctx.get("font_mm")
    if font_mm is not None:
        if font_mm < MIN_FONT_MM:
            add("Sch-II-font", "MAJOR", f"Estimated declaration font ~{font_mm} mm is below configured {MIN_FONT_MM} mm threshold")
    else:
        add("Sch-II-font", "INFO", "Font size was not reliably measurable; manual verification recommended")

    return violations
