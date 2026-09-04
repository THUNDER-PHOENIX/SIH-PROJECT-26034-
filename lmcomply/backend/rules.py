
# Minimum declaration letter height (mm) for small packs. VERIFY against the
# current Schedule of LM(PC) Rules 2011 before claiming exact values in pitch.
MIN_FONT_MM = 2.0

def evaluate(f, ctx):
    v = []
    def add(rid, sev, msg): v.append({"rule_id": rid, "severity": sev, "message": msg})

    if not f.get("mrp"):
        add("R6(1)(e)", "CRITICAL", "MRP declaration missing on label")
    else:
        if not any(sym in f["raw"].lower() for sym in ("₹", "rs", "inr")):
            add("R6(1)(e)", "MAJOR", "MRP not prefixed with ₹ / Rs. as required")
        if "." in f["mrp"] and len(f["mrp"].split(".")[1]) > 2:
            add("R6(1)(e)", "MINOR", "MRP shows more than 2 decimal places")
    if not f.get("net_qty"):
        add("R6(1)(b)", "CRITICAL", "Net quantity declaration missing")
    else:
        if f["net_qty"][1] not in ("kg","g","mg","l","ml","cl","m","cm","mm","pcs"):
            add("R6(1)(b)", "MAJOR", f"Non-standard unit '{f['net_qty'][1]}' for net quantity")
    if not f.get("date"):
        add("R6(1)(f)", "CRITICAL", "Month & year of manufacture/packing/import missing")
    if not (f.get("phone") or f.get("email")):
        add("R6(1)(g)", "MAJOR", "Consumer care contact (phone/email) not found")
    if f.get("imported"):
        if not f.get("origin"):
            add("R6(1)(i)", "MAJOR", "Imported product: 'Country of Origin' missing")
        if not f.get("importer_addr"):
            add("R6(1)(a)", "MAJOR", "Imported product: importer name & address missing")
    if not f.get("mfr_decl"):
        add("R6(1)(a)", "MAJOR", "Manufacturer / packer / marketer declaration not identifiable")
    fm = ctx.get("font_mm")
    if fm is not None and fm < MIN_FONT_MM:
        add("Sch-II-font", "MAJOR", f"Declaration font ~{fm}mm is below prescribed minimum {MIN_FONT_MM}mm")
    elif fm is None:
        add("Sch-II-font", "INFO", "Font size could not be measured (low OCR confidence) - flagged for manual review")
    return v
