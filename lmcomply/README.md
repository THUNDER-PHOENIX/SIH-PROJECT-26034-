
# LM Comply — Legal Metrology (Packaged Commodities) Rules, 2011 Compliance Checker

Hackathon scaffold: scan a product label -> AI/OCR extracts declarations ->
rule engine validates against LM(PC) Rules 2011 -> violations + PDF report + dashboard.

## Run (single command)
    pip install -r requirements.txt
    python run.py        # seeds data, generates label images, starts server
    # open http://localhost:8000

## OCR — fully functional by default, no installs needed
OCR auto-fallback chain:
1. Tesseract.js in the browser (default, needs internet once for CDN) -> zero install
2. Server-side Tesseract (if binary installed) -> fully offline
3. Manual paste field as last resort
Generated test labels are in uploads/labels/ after running run.py.

## OCR
Install Tesseract binary for real OCR (pytesseract wraps it):
- Ubuntu: sudo apt install tesseract-ocr
- Windows: install from UB Mannheim build, add to PATH
Without it, use the "Demo OCR text" field in the Scan tab to drive the full pipeline.

## Demo script for judges
1. Show history + dashboard (seeded data).
2. Live-scan a real product (shiny packs may need the demo-text field as backup).
3. Scan your PRINTED violation labels (missing date / no country of origin / tiny MRP font)
   -> violations fire with rule citations -> download PDF report.

## Honest limitation
Font-size check uses OCR box height + image DPI or manual px/mm calibration.
For a rigorous measurement, photograph next to a reference card of known size and
enter px/mm in the Scan tab. Verify MIN_FONT_MM in backend/rules.py against the
current Schedule of the Rules before pitching exact numbers.

## Pitch line
"AI extracts, rules decide" — deterministic, auditable verdicts for enforcement.
Barcode scanners identify products; this system checks whether the label is LEGAL.
