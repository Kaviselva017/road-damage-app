FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc g++ libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY backend/ .
RUN mkdir -p uploads ai_model

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
