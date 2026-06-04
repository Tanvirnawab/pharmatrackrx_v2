FROM python:3.11-slim

WORKDIR /app

# Tesseract for OCR (optional V2 feature)
RUN apt-get update && apt-get install -y \
    curl \
    libpq-dev \
    gcc \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

CMD ["/bin/bash", "/app/entrypoint.sh"]
