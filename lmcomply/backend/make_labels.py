
"""Generate realistic test label PNGs into uploads/labels/ (pure PIL, no network)."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(__file__), "..", "uploads", "labels")
os.makedirs(OUT, exist_ok=True)
FONT_DIR = "/usr/share/fonts/truetype/dejavu"
def F(s): return ImageFont.truetype(os.path.join(FONT_DIR, "DejaVuSans.ttf"), s)
def FB(s): return ImageFont.truetype(os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf"), s)

def label(name, lines, fbold=FB, freg=F, base=34):
    W = 900
    H = 80 + len(lines) * int(base * 1.6)
    img = Image.new("RGB", (W, H), "#f8f4e6")
    d = ImageDraw.Draw(img)
    y = 40
    for item in lines:
        txt, b = (item[0], item[1])
        sz = item[2] if len(item) > 2 else base
        d.text((40, y), txt, font=(fbold(sz) if b else freg(sz)), fill="#1a1a1a")
        y += int(sz * 1.6)
    p = os.path.join(OUT, name)
    img.save(p, dpi=(300, 300))   # real DPI so px/mm calibration is honest
    return p

label("01_compliant.png", [
    ("GOLDEN BISCUITS  Premium Cookies", True),
    ("Manufactured by: Golden Foods Pvt Ltd, Plot 12, Pune 411001", False),
    ("Net Qty: 300 g", True),
    ("MRP: Rs. 85 (inclusive of all taxes)", True),
    ("MFG: 04/2026    Best Before: 10 months", False),
    ("Consumer Care: 1800-123-4567   care@goldenfoods.in", False)])
label("02_missing_date.png", [
    ("CRUNCHY WAVES  Potato Chips", True),
    ("Manufactured by: Crunchy Snacks Ltd, Delhi 110001", False),
    ("Net Qty: 150 g", True),
    ("MRP: Rs. 50 (inclusive of all taxes)", True),
    ("Consumer Care: 1800-555-0199", False)])
label("03_imported_no_origin.png", [
    ("BELLA PASTA  Imported from Italy", True),
    ("Net Wt: 500 g", True),
    ("MRP: 320", True),
    ("Email: support@bellapasta.com", False)])
label("04_tiny_mrp_font.png", [
    ("PURE SPRING  Packaged Drinking Water", True),
    ("Manufactured by: Pure Spring Water Co, Bengaluru 560001", False),
    ("Net Qty: 1 L", True),
    ("mrp rs. 20 inclusive of all taxes", False, 16),
    ("PKD: 02/2026     Consumer Care: 1800-777-0123", False)], fbold=F, freg=F, base=40)
print("labels generated")
