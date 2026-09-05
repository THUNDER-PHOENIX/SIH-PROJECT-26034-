# LM Comply — Packaged Commodity Compliance Screening

**SIH prototype:** photograph a packaged-product label, extract declarations with OCR, apply deterministic compliance checks, store the inspection, visualize trends, and generate an auditable PDF report.

> **Pitch:** AI/OCR extracts the evidence; deterministic rules decide the screening result.

## Architecture

```text
Label photo
   ↓
OCR (browser Tesseract.js / server Tesseract)
   ↓
Field extraction + confidence
   ↓
Deterministic compliance rules
   ↓
COMPLIANT / NON_COMPLIANT + findings
   ↓
SQLite inspection history
   ↓
Dashboard + PDF report
```

## Quick start

```bash
cd lmcomply
pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:8000`.

The launcher seeds demo records only when the database is empty and generates test labels before starting FastAPI/Uvicorn.

## OCR modes

1. **Browser OCR:** Tesseract.js is used from the frontend when available.
2. **Server OCR:** Python `pytesseract` is used when the Tesseract executable is installed.
3. **Demo/manual text:** useful for offline judging or OCR failure recovery.

For server OCR on Windows, install a Tesseract build and add its executable to PATH. The application remains usable with browser OCR/manual text when server Tesseract is unavailable.

## SIH judge demo

1. Open **Dashboard** and show seeded inspection history.
2. Open **New Scan** and upload a clear label image.
3. Show extracted MRP, quantity, date, manufacturer/contact and OCR confidence.
4. Demonstrate a compliant and a deliberately incomplete label.
5. Explain each finding using its rule ID and severity.
6. Open the generated PDF report.

## Safety and accuracy

This is an **automated screening aid**, not an adjudication engine. OCR errors, image quality, packaging geometry and legal-rule updates can affect results. Font measurement is only an estimate unless a reliable physical calibration is supplied. Verify the configured legal thresholds and applicable current notifications/schedules before presenting a number as legally definitive.

## Project structure

```text
lmcomply/
├── backend/
│   ├── main.py          # FastAPI API and upload validation
│   ├── db.py            # SQLite access and schema
│   ├── extract.py       # OCR + field extraction + confidence
│   ├── rules.py         # deterministic compliance checks
│   ├── report.py        # PDF report generation
│   ├── make_labels.py   # synthetic demo labels
│   └── seed.py          # demo database records
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── uploads/             # runtime images/reports
├── requirements.txt
└── run.py
```

## Production roadmap

- Real authentication/JWT instead of demo `X-Role` headers.
- Signed audit logs and immutable inspection evidence.
- Better label-region detection and calibrated physical measurements.
- More comprehensive, versioned legal-rule datasets.
- Automated unit/integration tests and CI.
- Object storage instead of local uploads for multi-user deployment.
