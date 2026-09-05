import json
from fpdf import FPDF


def _safe(value):
    if value is None:
        return "Not detected"
    if isinstance(value, (tuple, list)):
        return " ".join(map(str, value))
    return str(value).replace("₹", "Rs.")


def build_pdf(scan, product, violations, out_path):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("helvetica", "B", 18)
    pdf.cell(0, 10, "Legal Metrology Compliance Report", ln=True, align="C")
    pdf.set_font("helvetica", "", 9)
    pdf.cell(0, 6, "Automated screening report - manual verification recommended", ln=True, align="C")
    pdf.ln(5)

    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 7, "Scan Summary", ln=True)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, f"Product: {_safe(product['name'])}", ln=True)
    pdf.cell(0, 6, f"Scan ID: {scan['id']}   Status: {scan['status']}", ln=True)
    pdf.cell(0, 6, f"Created: {scan['created_at']}", ln=True)
    pdf.ln(3)

    ex = json.loads(scan["extracted"] or "{}")
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 7, "Extracted Declarations", ln=True)
    pdf.set_font("helvetica", "", 9)
    for label, key in [
        ("MRP", "mrp"), ("Net quantity", "net_qty"), ("Manufacture/Packing date", "date"),
        ("Phone detected", "phone"), ("Email detected", "email"), ("Imported", "imported"),
        ("Country of origin", "origin"), ("Manufacturer declaration", "mfr_decl"),
        ("OCR confidence", "ocr_confidence"), ("Estimated MRP font (mm)", "font_mm"),
    ]:
        pdf.cell(0, 5, f"{label}: {_safe(ex.get(key))}", ln=True)

    pdf.ln(4)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 7, f"Findings ({len(violations)})", ln=True)
    pdf.set_font("helvetica", "", 9)
    if not violations:
        pdf.cell(0, 6, "No critical or major violations detected by the configured screening rules.", ln=True)
    for v in violations:
        pdf.multi_cell(0, 5, f"[{v['severity']}] Rule {v['rule_id']}: {_safe(v['message'])}")

    pdf.ln(4)
    pdf.set_font("helvetica", "I", 8)
    pdf.multi_cell(0, 4, "This document is an automated screening aid. It does not replace inspection, measurement, evidence collection, or adjudication under applicable Legal Metrology law and current rules. Rule thresholds must be verified against the latest applicable notification/schedule.")
    pdf.output(out_path)
