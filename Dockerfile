FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY runify ./runify

# Cloud Run sets PORT.
CMD exec uvicorn runify.main:app --host 0.0.0.0 --port ${PORT:-8080}
