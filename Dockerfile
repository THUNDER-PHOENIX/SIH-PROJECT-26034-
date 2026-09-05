FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY lmcomply/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
COPY lmcomply /app/lmcomply

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn lmcomply.backend.main:app --host 0.0.0.0 --port ${PORT}"]
